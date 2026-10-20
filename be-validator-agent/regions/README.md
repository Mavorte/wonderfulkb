# Regiony dokumentu (kroky 1 a 2: segmentace na odstavce a štítky)

Podklad pro [regiony-dokumentu-navrh.md](../docs/regiony-dokumentu-navrh.md): dokument se rozřeže na regiony
(odstavce, položky výčtu, řádky tabulek, nadpisy), každý s polohou na straně, textem a řádky (krok 1), a regiony
dostanou štítek, stranu smlouvy, odkazované typy dokumentů a krátký popis (krok 2).

Hotové jsou **kroky 1 až 3**, jen pro strany s textovou vrstvou PDF. Skeny (`source: no_text_layer`) zatím regiony
nemají (krok 8, Textract `LAYOUT`). Krok 3: pipeline (`../pipeline`, krok `regions`) zapisuje
`cases/<case>/analysis/<document_id>/regions.json` a `regions_s3_key` do řádku analýzy, viz pipeline README;
worker triggeru modul balí (`trigger/build.sh`). Nasazení workeru s regiony ani běh nad daty v AWS zatím neproběhly.

## Spuštění

```bash
cd be-validator-agent/regions
../pipeline/.venv/bin/python -m pytest -q tests          # 28 testů, syntetická PDF a falešný model, bez AWS
../pipeline/.venv/bin/python -m region_pipeline a.pdf b.pdf --out-dir out --render --print
../pipeline/.venv/bin/python -m region_pipeline a.pdf --label rules --print          # štítky jen regexy
AWS_PROFILE=hackathon AWS_DEFAULT_REGION=eu-central-1 \
  ../pipeline/.venv/bin/python -m region_pipeline smlouva.pdf --label llm --doc-label smlouva_o_uveru --print
```

`.venv` pipeline má PyMuPDF; jinak `pip install --only-binary :all: -r requirements.txt`. Výstup:
`out/<název>.regions.json` a s `--render` `out/png/<název>-p<n>.png` (strana s obdélníky regionů, barva podle `kind`,
nad obdélníkem pořadí `rNN`). Pozor: stejné názvy souborů z různých případů se v jednom `--out-dir` přepíšou.

Z Pythonu: `regions_for_pdf(cesta_nebo_bytes)` a `label_regions(result, backend=make_backend(), doc_label=…,
limiter=default_limiter())` (`region_pipeline.labels`, `region_pipeline.llm`). `backend=None` = jen regexy.

## Výstup

```json
{"version": 1,
 "pages": [{"page": 1, "width": 595.3, "height": 841.9, "source": "text_layer"}],
 "regions": [{"region_id": "p1-r17", "page": 1, "order": 17, "bbox": [0.0675, 0.4, 0.93, 0.425],
              "kind": "table_row", "text": "Dodavatel | Valdorin Stroje s.r.o.",
              "lines": [{"bbox": […], "start": 0, "end": 9}, {"bbox": […], "start": 12, "end": 34}],
              "source": "text_layer",
              "label": "smluvni_strana", "label_source": "llm", "party": "supplier",
              "summary": "Identifikace dodavatele stroje.", "section": "p1-r14"}]}
```

- `bbox` = `[x0, y0, x1, y1]` relativně ke straně **tak, jak se vykreslí** (s rotací), počátek vlevo nahoře; stejná
  konvence jako `bbox` podpisů a náhledy stran z `GET …/pages` (`preview_url`).
- `kind`: `paragraph`, `list_item`, `table_row`, `heading`, `page_header`, `page_footer`.
- `lines[].start/end` = rozsah znaků řádku v `text`; podle něj se citát z agenta zúží na konkrétní řádky.
- `table_row`: buňky (sloupce) dělí ` | `, popisek a jeho hodnota (`IČ: 61061344`) mezera.
- `region_id` = `p{strana}-r{pořadí}`, pořadí shora dolů a zleva doprava; stejné PDF dá vždy stejná id.
- `label` (`region_pipeline/labels.yaml`): `povinny_podklad`, `odkaz_na_dokument`, `smluvni_strana`, `predmet`,
  `cena_platba`, `zajisteni`, `predani`, `termin_misto`, `hlavicka`, `podpisovy_blok`, `obecne_ustanoveni`, `jine`.
  `label_source`: `llm` nebo `rules` (záloha).
- `party` jen u `smluvni_strana` a `podpisovy_blok` (`provider`, `borrower`, `buyer`, `supplier`, `guarantor`,
  `insurer`, `unknown`); `refers_to` jen u `povinny_podklad` a `odkaz_na_dokument` (štítky z `classify/taxonomy.yaml`);
  `summary` jen od modelu; `section` = `region_id` posledního nadpisu nad regionem.

## Jak se segmentuje (`region_pipeline/segment.py`)

Z řádků PyMuPDF, ne z jeho bloků (blok občas slije dva sloupce formuláře, smlouva SOLOM):

1. **Segmenty**: řádek PyMuPDF rozdělený na velkých mezerách mezi spany; svislý text se vynechá.
2. **Popisek + hodnota** na stejném řádku: `IČ:` + `61061344`, `a)` + text položky. Hodnota dál než 3 výšky řádku =
   řádek formuláře (`table_row`).
3. **Tabulky**: skupiny v pásu mezi vodorovnými čarami kresby strany (čáry nakreslené po buňkách se spojí) tvoří
   `table_row`. Pás bez vnitřních čar s popisky pod sebou se dělí na řádky; jednosloupcový rámeček je odstavec; text
   po sloupcích, takže zalomená buňka drží pohromadě.
4. **Odstavce**: další řádek ve stejném sloupci, s podobnou výškou a mezerou do ~0,7 výšky řádku. Nový odstavec začíná
   na značce výčtu (`a)`, `1.`, `1.8`, `2.1.1`, `•`, `-`), po nadpisu a u položky výčtu vlevo od odsazení textu.
5. **Nadpis**: jeden segment, tučně a (verzálky / číslo článku / končí dvojtečkou), nebo výrazně větší písmo; částka
   `1 620 000,00 CZK` nadpis není (písmena musí převažovat).
6. **Záhlaví a zápatí**: text v horní/dolní čtvrtině strany, který se (s čísly nahrazenými) opakuje na víc stranách,
   nebo leží úplně u okraje.

## Jak se štítkuje (`region_pipeline/labels.py`)

1. **Regexová záloha** vždy: pravidla z `labels.yaml` nad textem bez diakritiky, první shoda podle `order` vyhrává.
   Strana z řádku nebo nadpisu („Dodavatel | …“) platí i pro regiony strany pod ním („IČO / DIČ | …“); položky výčtu
   pod odstavcem s podklady jsou také `povinny_podklad`.
2. **Model** (`--label llm`): Haiku 4.5 přes Converse s výstupem vynuceným nástrojem a schématem (enumy štítků, stran,
   typů dokumentů); `REGIONS_BACKEND=mantle` přepne na Qwen. Do promptu jde id, druh, hrubý sloupec (vlevo/vpravo)
   a text regionu (max. 500 znaků), bez souřadnic; text je označený jako nedůvěryhodný. Po dávkách 60 regionů,
   další dávka dostane poslední nadpis jako kontext. Záhlaví a zápatí do modelu nejdou (`jine`).
3. **Ověření odpovědi**: cizí id a štítky mimo taxonomii se zahodí; region bez platné odpovědi a dávka, jejíž volání
   selhalo, dostanou zálohu. `party` a `refers_to` se u jiných štítků zahodí, `refers_to` se omezí na typy dokumentů
   a prázdný seznam doplní regexy. `povinny_podklad` je dovolený jen v úvěrové dokumentaci (`podklady_in`), je-li
   typ dokumentu známý (`doc_label`).

Model souřadnice ani text nemění. Limit `REGIONS_MAX_RPM` (výchozí 20/min, tým sdílí 50), retry z `classify.llm`.

## Ověřeno (19. 10. 2026)

- 28 testů: 11 segmentace, 17 štítkování (`tests/test_labels.py`: dědění strany, výčet podkladů, ověření odpovědi
  modelu, záloha při chybě, dávky a kontext, prompt bez souřadnic a se sloupci, odkaz vs. podklad, omezení na
  úvěrovou dokumentaci).
- Segmentace (`tests/test_segment.py`): odstavce a prázdný řádek, výčet s oddělenou značkou a visícím odsazením, dva
  sloupce, popisek + hodnota, řádky tabulky i s čarami po buňkách, nadpis vs. tučná částka, opakované záhlaví/zápatí,
  strana bez textové vrstvy, rotace 90°, stabilní id a rozsahy řádků.
- Ručně, vykreslením obdélníků: 23 PDF (`docs/vzorove-dokumenty/solom-rec`, `stavby-fiser`,
  `downloads/zervanta-stavby-SYN-B05`), ~33 s celkem. Pro zadané případy:
  - **B (chybějící doklad)**: smlouva SOLOM má položky a) až f) jako samostatné `list_item` („a) kopii daňového dokladu
    dodavatele…“); SYN smlouva má odstavec „Před čerpáním musí být doložena faktura, …“ a v příloze řádek
    „Faktura uvedená v podkladech | FV-B-26-0005“.
  - **A (dodavatel)**: SYN smlouva i objednávka mají řádek „Dodavatel … | Valdorin Stroje s.r.o.“ a „IČO … | 98000136“;
    smlouva SOLOM má nadpis „DODAVATEL:“ a pod ním jeden odstavec s názvem, adresou, IČ a DIČ.

- Štítky živě (Haiku 4.5, eu-central-1), 4 dokumenty, celkem 4 běhy (~85 tis. vstupních a ~54 tis. výstupních tokenů, ~0,4 USD):
  - SYN-B05 smlouva (`--doc-label smlouva_o_uveru`): „Dodavatel | Valdorin Stroje s.r.o.“ a „IČO dodavatele“ =
    `smluvni_strana/supplier`; „Před čerpáním musí být doložena …“ = `povinny_podklad` → faktura, objednávka, předávací
    protokol, úhrada, vinkulace, zajišťovací převod; řádky přílohové tabulky (Objednávka, Faktura, Pojistná smlouva) =
    `povinny_podklad`; „Smlouva o úvěru č. | …“ = `odkaz_na_dokument`.
  - SYN-B05 objednávka (`--doc-label objednavka`): dodavatel na s. 1 i 9 = `supplier`, kupující = `buyer`, žádný
    `povinny_podklad`, čísla smlouvy a objednávky = `odkaz_na_dokument`.
  - Smlouva SOLOM (dva sloupce vedle sebe): po přidání sloupce do promptu jsou název, sídlo, účet, IČ a zápis v OR
    přiřazené správné straně (bez sloupce model strany střídal); položky a) až f) = `povinny_podklad` se správným
    `refers_to`.
  - Objednávka stavby-fiser: AWP s.r.o. = `supplier`, Stavby Fišer a.s. = `buyer` (bez sloupce prohozené).
  - Bez `--doc-label` dával model `povinny_podklad` i technickým parametrům a obchodním podmínkám objednávky; proto
    pojistka `podklady_in` a užší popis štítku.

## Známá omezení

- **Orámované boxy stran** ve volném formuláři (objednávka stavby-fiser: „Objednatel“, „Dodavatel“) se rozpadnou na
  několik regionů (název, IČO, DIČ, adresa). Na dodavatele jde ukázat, ale ne jedním obdélníkem. Řešení: sloučit
  regiony uvnitř jednoho nakresleného obdélníku, který není tabulkou.
- Sloupec popisků a sloupec hodnot bez dvojteček a bez čar (smlouva SOLOM, „Předběžná kupní cena / Výrobní číslo“ vs.
  „1 620 000,00 CZK / DGR240020“) zůstane jako dva odstavce vedle sebe.
- Skeny a strany bez textové vrstvy: žádné regiony (krok 8). `10_Podklady k výlatě_objednávka.pdf` (SOLOM) má jen pár
  řádků textové vrstvy a `11_…Protokol.pdf` žádnou.
- Regexová záloha je hrubá: ve dvousloupcových formulářích stranu nepozná (`unknown`) a `obecne_ustanoveni`/`jine`
  rozlišuje jen délkou. Na zadané případy (řádek dodavatele, výčet podkladů) stačí.
- Úplnost štítků se neměřila na celém datasetu, jen ručně na 4 dokumentech výše.
