# Regiony dokumentu: odstavce se štítkem, na které agent ukazuje

Návrh a plán, verze 2 (19. 10. 2026). Navazuje na podpisy (`bbox` v `signatures.json`, volání 3 v
`openapi-validator-agent.yaml`). Verze 1 stavěla na polích (IČO, DIČ…); verze 2 stojí na **odstavcích**, pole jsou jen
zpřesnění uvnitř odstavce.

## Cíl

Dokument rozřezat na regiony = **odstavce** (u tabulek řádky). Každý region nese polohu, svůj text a štítek.
Agent pak:

1. dostane přehled regionů (id, štítek, začátek textu), **sám si vybere**, na kterou část se zaměří,
2. vybrané regiony dá vyhodnotit LLM,
3. v nálezu na ně **přímo ukáže** (jeden i víc regionů, i napříč dokumenty),

a UI po kliknutí na nález otevře dokument, odskroluje na region a zvýrazní ho.

## Zadané případy

| | Případ | Na co nález ukazuje |
|---|---|---|
| **A** | Dodavatel se liší na dvou dokumentech (např. objednávka: Hydravor Tech s.r.o., faktura: Hydravor Group s.r.o.; ilustrační) | Na **oba** regiony, kde je dodavatel uveden, každý ve svém dokumentu, s rolí „strana A / strana B“ |
| **B** | Hlavní smlouva říká, že se dodává doklad o koupi (faktura), ale v případu není | Na **odstavec smlouvy**, který doklad vyžaduje (např. položka „a) kopie daňového dokladu dodavatele…“) |
| C | Chybí hodnota (IČO kupujícího je prázdné) | Na odstavec kupujícího, zpřesněno na řádek s popiskem `IČO:` |

C je z verze 1 a funguje stejným mechanismem jako A a B, jen s jedním regionem.

## Princip: model cituje id a citát, souřadnice dodá kód

Stejně jako `be-document-processing/extraction.py` („Evidence musí obsahovat page_number a block_id, bbox dopočítá
aplikace“): LLM ani agent souřadnice nikdy nevymýšlí. Regiony a `bbox` vznikají deterministicky (textová vrstva PDF,
Textract), LLM jim jen dává štítek a agent je cituje přes `region_id` + doslovný citát. Kód citaci ověří
(id existuje, citát je v textu regionu); neprojde-li, nález spadne na úroveň strany a označí se `anchor: page_only`.

## Datový model: `analysis/<document_id>/regions.json`

```json
{
  "document_id": "febddf34-…",
  "version": 1,
  "pages": [{"page": 1, "width": 595, "height": 842, "source": "text_layer"}],
  "regions": [
    {
      "region_id": "p1-r04",
      "page": 1,
      "order": 4,
      "bbox": [0.08, 0.18, 0.92, 0.24],
      "kind": "paragraph",
      "text": "Dodavatel: Hydravor Tech s.r.o., Průmyslová 12, 301 00 Plzeň, IČO 98000128",
      "lines": [
        {"bbox": [0.08, 0.18, 0.70, 0.20], "start": 0, "end": 44},
        {"bbox": [0.08, 0.21, 0.40, 0.24], "start": 45, "end": 74}
      ],
      "label": "smluvni_strana",
      "party": "supplier",
      "summary": "Identifikace dodavatele",
      "section": "p1-r02",
      "source": "text_layer"
    }
  ]
}
```

| Pole | Význam |
|---|---|
| `region_id` | `p{strana}-r{pořadí}`, stabilní při opakovaném běhu (pořadí čtení na straně) |
| `bbox` | `[x0, y0, x1, y1]` relativně ke straně, počátek vlevo nahoře, jako u podpisů (UI to použije rovnou v %) |
| `kind` | `heading`, `paragraph`, `list_item`, `table_row`, `page_header`, `page_footer` (krok 1 hotový, viz `be-validator-agent/regions/README.md`); `signature`, `stamp` přibudou ze `signatures.json` |
| `text` | celý text regionu (strana po redakci; text podpisů v něm není) |
| `lines` | řádky s bbox a rozsahem znaků v `text`: citát z agenta se dá zúžit na konkrétní řádky (případ C) |
| `label` | štítek obsahu, viz taxonomie níže; `null`, dokud štítkování neproběhlo |
| `party` | u `smluvni_strana` a `podpisovy_blok`: `provider`, `borrower`, `buyer`, `supplier`, `guarantor`, `insurer`, `unknown` (enum jako role podpisů) |
| `refers_to` | u `povinny_podklad`: štítky dokumentů z `classify/taxonomy.yaml`, které odstavec vyžaduje (např. `[faktura]`) |
| `summary` | jedna věta od LLM, pro přehled agenta a tooltip v UI |
| `section` | `region_id` nadpisu, pod který odstavec patří (článek smlouvy) |

Podpisy se nepřepočítávají: regiony `kind=signature` se převezmou ze `signatures.json` se stejným `signature_id`.

### Taxonomie štítků regionů (`regions/labels.yaml`)

Malá a pevná, aby se dala filtrovat napříč případem:

`hlavicka` (název a číslo dokumentu), `smluvni_strana`, `predmet` (co se financuje / dodává, výrobní číslo),
`cena_platba` (ceny, DPH, splátky, účty), `povinny_podklad` (co musí klient doložit, podmínky čerpání),
`odkaz_na_dokument` (číslo jiného dokumentu bez povinnosti ho doložit, přidáno v kroku 2),
`zajisteni` (ručení, zajišťovací převod, vinkulace), `termin_misto` (datum, místo, lhůty), `predani`
(převzetí, stav předmětu), `podpisovy_blok`, `obecne_ustanoveni` (VOP, právní text), `jine`.

## Jak regiony vznikají (modul `be-validator-agent/regions/`, krok `regions` v pipeline)

**1. Segmentace na odstavce (deterministicky, 0 volání modelu)**

| Strana | Zdroj |
|---|---|
| Má použitelnou textovou vrstvu (stejné rozhodnutí jako dnes v `pipeline/pdf.py`) | PyMuPDF `page.get_text("dict")` → řádky s bbox; `page.get_drawings()` pro čáry tabulek (už se používá u rolí podpisů) |
| Sken | Textract `AnalyzeDocument` `FeatureTypes=["LAYOUT"]` nad zamaskovanou PNG: bloky `LAYOUT_TEXT`, `LAYOUT_TITLE`, `LAYOUT_LIST`, `LAYOUT_TABLE` jsou přímo odstavce s geometrií |

Pravidla pro textovou vrstvu: řádky se slučují do odstavce, když se překrývají ve sloupci a mezera je menší než ~0,6
výšky řádku; odstavec se dělí na značce výčtu (`a)`, `1.`, `•`, `-`), takže položky a) až f) ve smlouvě jsou samostatné
regiony (to potřebuje případ B); tabulka z čar → jeden region na řádek (`Dodavatel | Hydravor Tech s.r.o. | IČO …`).

**2. Štítkování (LLM, 1 volání na dokument, u dlouhých dávky po ~80 regionech)**

Vstup: seznam `region_id + kind + text` (bez souřadnic) a název/štítek dokumentu. Výstup:
`{region_id: {label, party?, refers_to?, summary}}`. Model: Qwen (bez limitu týmu) nebo Haiku 4.5 (`eu.` prefix).
Neznámé `region_id` nebo štítek mimo taxonomii se zahodí. Bez LLM (`--skip label`) záloha: `section` podle nejbližšího
nadpisu a regexy (`Dodavatel|Prodávající` → `smluvni_strana/supplier`, `doložit|předložit … podklad` → `povinny_podklad`).

**3. Zápis** `regions.json` vedle `signatures.json`, odkaz `regions_s3_key` v řádku `wonderfulkb-uw-document-analysis`.
Regiony se počítají ze zamaskované kopie (`redacted/…pdf`), čitelný originál nenapájí nic dalšího (privacy, část 3).
Dedup (`dedup/reuse.py`) kopíruje `regions.json` spolu s ostatní analýzou.

## API (`be-validator-agent/api`, Lambda `wonderfulkb-agent-api`)

| Volání | Pro koho | Vrací |
|---|---|---|
| `GET /cases/{c}/regions?label=smluvni_strana&party=supplier` | agent | regiony daného štítku **napříč všemi dokumenty případu** (porovnání, případ A) |
| `GET /cases/{c}/documents/{d}/regions?outline=true` | agent | přehled: `region_id`, `page`, `label`, `party`, `summary`, prvních ~80 znaků; levný na tokeny |
| `GET /cases/{c}/documents/{d}/regions?ids=p1-r04,p2-r11` | agent | plný text vybraných regionů (na to se agent „zaměří“) |
| `GET /cases/{c}/documents/{d}/regions?include_geometry=true` | UI | vše včetně `bbox` a `lines` |
| `GET /cases/{c}/documents/{d}/pages` (`getDocumentPages`) | UI | `pages[{page, preview_url}]`: předpodepsané PNG zamaskovaných stran (300 s), `preview_pdf_url`, `redacted`, `original_available`, `reveal_path`; bez auditu |

Náhledy stran nedělá tento návrh: endpoint `…/pages` připravuje session „dokument preview/odkrytí“ v
`be-validator-agent/api` (kontrakt v `be-document-processing/contracts/openapi-validator-agent.yaml`), nasazený ve `wonderfulkb-agent-api` a podle
té session ověřený na živých datech (19. 10.). Konvence
`bbox` je stejná jako u regionů (`[x0, y0, x1, y1]` 0–1, počátek vlevo nahoře, `page` od 1) a PNG je celá strana, takže
obdélník regionu jde nad `<img>` rovnou v %. Čitelný originál (`…/original`, `revealDocumentOriginal`, auditované) regiony
nepotřebují. Dnes má backoffice náhledy stran jen pro lokální mock `mock-solom-rec`.

**Dokumenty bez maskování** (např. `SYN-A01`) mají `redacted: false` a všechna `preview_url: null`, protože jejich
obrázky stran vznikly z čitelného originálu. UI pak ukáže zástupný obrázek strany s obdélníkem regionu a odkazem
„Otevřít originál“ (`…/original`, auditované); regiony samy na náhledu nezávisí. Pro demo případu B je to riziko:
`SYN-A01` je zatím jediný ověřený případ s chybějící fakturou, takže ho buď znovu zpracovat s maskováním, nebo pro
demo vybrat zamaskovaný případ.

## Jak agent pracuje

```
přehled případu (dokumenty + štítky)
  → pro pravidlo vybere štítek regionů      (A: smluvni_strana/supplier, B: povinny_podklad ve smlouvě)
  → načte plný text jen těch regionů        (ne celé dokumenty → méně tokenů, přesnější vyhodnocení)
  → LLM vyhodnotí a vrátí nález s evidencí  (region_id + doslovný citát + role v nálezu)
  → kód ověří citace a doplní nic víc       (bbox si vezme až UI)
```

Agent má volnost: pravidlo může říct jen „porovnej dodavatele“, agent sám najde regiony; když štítkování region netrefilo,
může projít `outline` dokumentu a vybrat jiný.

### Kontrakt evidence (rozšíření `sources` v `case_evaluation_results`, zpětně kompatibilní)

```json
{"document_id": "febddf34-…", "title": "10_Objednavka.pdf", "page": 1,
 "region_id": "p1-r04", "quote": "Hydravor Tech s.r.o.", "role": "compare_a",
 "anchor": "region"}
```

| `role` | Význam v UI |
|---|---|
| `evidence` | výchozí: tady je to, o čem nález mluví |
| `compare_a`, `compare_b` (…) | strany porovnání; UI je ukáže jako dvojici a umí mezi nimi přepínat |
| `declaration` | místo, kde dokument něco vyžaduje / slibuje (případ B) |
| `missing_value` | region, kde hodnota měla být a není (případ C) |

`anchor`: `region` (citát sedí na region), `lines` (citát zúžený na řádky), `page_only` (citace neprošla ověřením).
`bbox` agent neposílá. Staré nálezy bez `region_id` fungují dál (jen strana).

### Případ A: dodavatel se liší

1. `GET /cases/{c}/regions?label=smluvni_strana&party=supplier` → `10_Objednavka p1-r04`, `faktura p1-r03`,
   `11_Predavaci_protokol p2-r07`, `09_Dohoda p1-r05`.
2. LLM dostane jen tyto 4 texty: „Je to stejný subjekt? Název, IČO, adresa.“
3. Nález `conflict`: `sources = [{…objednávka p1-r04, quote "Hydravor Tech s.r.o.", role compare_a},
   {…faktura p1-r03, quote "Hydravor Group s.r.o.", role compare_b}]`, ostatní dva regiony jako `evidence` (shodují se).

### Případ B: smlouva vyžaduje doklad, který chybí

1. Ve smlouvě `GET …/regions?label=povinny_podklad` → položky a) až f), každá s `refers_to`
   (`p2-r14` „a) kopie daňového dokladu dodavatele…“ → `[faktura]`).
2. Kód porovná `refers_to` se štítky dokumentů případu: `faktura` chybí. (Dnes totéž dělá `R-COMPLETE` v ref-agentovi
   regexem nad textem; nově z regionů, takže se ví přesné místo.)
3. Nález `missing`: `sources = [{…smlouva p2-r14, quote "kopie daňového dokladu dodavatele", role declaration}]`,
   v `details` `{"type": "faktura", "document_id": null}`.
4. V UI dlaždice „Faktura – chybí“ v pásu dokumentů je klikací a otevře smlouvu na odstavci `p2-r14`.

### Případ C: chybí hodnota

Region kupujícího `p1-r03` (`smluvni_strana/buyer`), citát `IČO:` → `anchor: lines`, UI zvýrazní řádek s popiskem
a celý odstavec slabě.

## UI (dělá Wonderful, ne tento tým)

Rozhodnutí uživatele 20. 10. 2026: UI staví Wonderful. Níže je jen popis, jak regiony v UI použít (podklad pro ně).


- `Focus` rozšířit o `regionId?`, `quote?` a `group?` (všechny regiony jednoho nálezu).
- `DocumentPanel`: strany z `GET …/pages` (`pages[].preview_url`, platnost 300 s: při chybě obrázku načíst znovu),
  nad `<img>` strany absolutně umístěný obdélník v % podle `bbox` (zúžený na `lines`, když citát sedí),
  skrol na region (`page.offsetTop + y0 * výška_strany − výška_okna / 3`), krátké pulzování, tooltip se `summary`.
  Barvy podle stavu nálezu: `fail` červená, `warn` žlutá, `pass` zelená; `missing_value` čárkovaně.
- **Porovnání (A):** nález s `compare_a/b` ukáže dvojici čipů „Objednávka s. 1 · Hydravor Tech“ ↔ „Faktura s. 1 ·
  Hydravor Group“; klik přepne dokument a odskroluje, šipka přepíná mezi stranami porovnání. (Rozdělený pohled dvou
  dokumentů vedle sebe je až po freeze.)
- **Chybějící doklad (B):** dlaždice `cr-thumb--missing` dostane cíl = region `declaration`.
- Nové funkce backoffice `regions-get` a `document-pages` (jako `evaluation-get`, API klíč zůstává na serveru); náhledy
  stran z `…/pages` místo `previewFor` (mock zůstane pro lokální vývoj).
- Záloha, když agent `region_id` nepošle: UI hledá citát (`found`, `quote`) v textu regionů dané strany.

## Plán

Code freeze je **úterý 20. 10. 13:30**. Pořadí je zvolené tak, aby po kroku 5 šlo ukázat případ B a A naživo.

| # | Krok | Kde | Hotovo, když | Odhad |
|---|---|---|---|---|
| 1 | Segmentace na odstavce z textové vrstvy (řádky → odstavce, dělení na výčtu, řádky tabulek) (**hotovo 19. 10.**) | `be-validator-agent/regions/`, testy na `docs/vzorove-dokumenty` | Na `0_Form_Smlouva` jsou položky a) až f) samostatné regiony, na `10_Objednavka` je dodavatel jeden region; ověřeno vykreslením obdélníků do PNG | 2–3 h |
| 2 | Štítkování: `labels.yaml`, LLM volání + regexová záloha, ověření id a štítků (**hotovo 19. 10.**) | tamtéž | Na vzorech mají dodavatel/kupující a položky podkladů správný `label`, `party`, `refers_to` (ruční kontrola ~5 dokumentů) | 1,5 h |
| 3 | Krok `regions` v pipeline, `regions_s3_key`, dedup, dávka nad demo případy (**hotovo 20. 10.**: dávka SYN-A01 a SYN-B05 v AWS, solom-rec čeká na redakci; worker s krokem `regions` nasazen 20. 10. 06:54 UTC, nové uploady dostávají `regions.json` automaticky) | `pipeline/run.py`, `adapters.py`, `dedup/reuse.py` | `run_case` na `SYN-A01` a `solom-rec` zapíše `regions.json`; `--skip regions` funguje | 1 h |
| 4 | API: regiony případu a dokumentu (`label`, `party`, `outline`, `ids`, geometrie); OpenAPI (**nasazeno 20. 10.**, živě ověřeno jen `not_run`, regiony v bucketu ještě nejsou). Náhledy stran = hotový `…/pages` druhé session | `be-validator-agent/api`, `be-document-processing/contracts/openapi-validator-agent.yaml` | `curl` na nasazenou Lambdu vrátí dodavatele ze všech dokumentů `SYN-A01` | 1,5 h |
| 5 | UI: **dělá Wonderful** (rozhodnutí 20. 10.); náhledy z API, obdélník + skrol, čipy porovnání, klikací chybějící dlaždice | `backoffice/app/src/review`, `functions/regions-get` | Klik na nález „chybí faktura“ odskroluje na položku a) smlouvy; klik na konflikt dodavatele přepíná objednávku ↔ fakturu | 3 h |
| 6 | Ref-agent: nástroje `regions_by_label` / `get_regions`, evidence s `region_id`/`quote`/`role`, ověření citátu; `R-COMPLETE` a nové pravidlo `R-SUPPLIER` nad regiony | `ref-agent/refagent`, `rules.yaml` | Ref-agent na demo případu vrací A i B s regiony; testy bez AWS | 2 h |
| 7 | Kontrakt pro Wonderful (nástroje, `role`, `anchor`, příklady A/B/C) a jak regiony použít v jejich UI | `docs/wonderful-validator-agent.md` | Text předaný Wonderful | 0,5 h |
| 8 | Skeny: Textract `LAYOUT` na stranách bez textové vrstvy | `regions/` | Ručně psaná objednávka SOLOM má odstavce s bbox | 1,5 h |
| 9 | (po freeze) Vektory regionů do S3 Vectors („kde je výrobní číslo“ napříč případy), rozdělený pohled dvou dokumentů | `embed/`, UI | — | — |

Souběžně jdou: 6 a 7 vedle 4 (jiné soubory, kontrakt je daný tímto dokumentem); 8 vedle čehokoli po kroku 1.

**Data pro demo:** případ A potřebuje dokumenty, kde se dodavatel opravdu liší. Pokud žádný SYN případ takový není,
vygenerovat unhappy variantu (faktura s jiným názvem dodavatele) v `be-validator-agent/dataset`. Případ B pokrývá
`SYN-A01` (faktura chybí).

## Rizika a otevřené otázky

- **Segmentace** formulářů a dvousloupcových smluv: odstavec může přeteknout přes sloupce. Kontrola vykreslením
  obdélníků (krok 1) je proto podmínka hotovosti, ne volitelná.
- **Štítek je odhad.** Agent proto smí jít mimo štítky přes `outline`; pravidlo nesmí z „žádný region se štítkem X“
  usuzovat, že informace v dokumentu není (stejná zásada jako u prázdných podpisů).
- **`refers_to`** u položek podkladů mapuje volný text na štítky dokumentů; v ref-agentovi to dnes dělá tabulka regexů
  v `rules.yaml` (R-COMPLETE `items`). Použít ji jako zálohu a kontrolu LLM.
- **Wonderful agent** musí `region_id`/`quote`/`role` přijmout do kontraktu; do té doby funguje záloha v UI podle citátu.
- **Rozpočet:** štítkování je 1 volání na dokument (dávka ~20 případů ≈ 150 volání), Textract `LAYOUT` jen na skenech
  (pilot: 2 z 79 stran). Ceník Textractu ověřit před dávkou.
