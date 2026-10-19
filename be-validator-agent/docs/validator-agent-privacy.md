# Validační agent: podpisy neukládáme čitelně, ale umíme je ukázat

Stav: **návrh a knihovna, nic nenasazeno** (19. 10. 2026). KMS klíč `alias/wonderfulkb-signatures` (id `<KMS_KEY_ID>`, eu-central-1, rotace zapnutá) vytvořila nadřazená session se souhlasem uživatele; `create_key.sh` zůstává jen jako dokumentace a už se nespouští. Rozhodnutí uživatele: čitelné originály a stránky se smějí zamaskovat, pokud umíme podpis na vyžádání ukázat odšifrovaný (část 4). Kód: [infra/validator-agent/privacy](../privacy/README.md). Navazuje na [validator-agent-storage.md](validator-agent-storage.md) a [validator-agent-api.md](../../be-document-processing/VALIDATOR-AGENT.md). Moduly `signatures/` a `api/` patří jiným sessions; tento dokument jim jen navrhuje změny (část 5 a 6), nic jsem v nich nepsal. V bucketu jsem nic neměnil ani nemazal, jen vypsal klíče (`aws s3 ls`, `list-vectors`).

Pojem „hash“ je tu přesný: **hash je jednosměrný a podpis z něj zpět nevznikne.** „Ukázat podpis uživateli“ proto znamená šifrování (zpětné), ne hash. Hash (phash) slouží jen na detekci kopie.

## 1. Inventura: co dnes leží čitelně

Bucket `wonderfulkb-raw-document-storage`, prefix `cases/`, stav 19. 10. 2026 (počty z výpisu klíčů):

| Co | Klíč | Počet | Obsahuje podpis? | Čitelné pro |
|---|---|---|---|---|
| **(c) Originální PDF** | `cases/<case>/original/<document_id>.pdf` | 184 | ano, v plné kvalitě (obrázek nebo vektor) | každého s `s3:GetObject` na bucketu |
| **(c) ZIP balíky originálů** | `cases/synteticke_dokumenty_20_pripadu.zip` (33 MB), `cases/codex-tmp.zip` (446 MB) | 2 | ano, všechna PDF uvnitř | totéž |
| **(b) Vykreslené stránky** | `cases/<case>/analysis/<doc>/pages/<n>.png` | 23 | ano, kdykoli je na stránce podpis | totéž |
| **(a) Výřezy podpisů** | `cases/<case>/analysis/<doc>/signatures/<sig>.png` | 42 | ano, výřez samotného podpisu (200 dpi) | totéž |
| Text | `analysis/<doc>/text.txt`, `vision/*/N.txt`, `run.json` | 7 + ostatní | ne, jen přepis (tištěná jména a popisky u podpisu ano, podpis ne) | totéž |
| Metadata podpisů | `analysis/<doc>/signatures.json` | 28 | ne: `bbox`, `role`, `role_evidence`, `phash`, `copy_suspicion` | totéž |

Bucket je **verzovaný** (`Status: Enabled`), bez Object Lock, bez lifecycle pravidel a bez bucket policy (ověřeno jen čtením, 19. 10. 2026). To znamená, že smazání objektu čitelnou verzi neodstraní, viz migrace v části 8. Má výchozí šifrování SSE-S3 (AES256). To chrání médium na disku, **ne před čtenářem s oprávněním**: kdo smí `GetObject`, dostane čitelný soubor. Pro cíl této funkce proto SSE-S3 nic neřeší.

Další místa, kde podpis může ležet čitelně a kam bucket nedosáhne:
- `LocalCropStore` modulu podpisů zapisuje výřezy na disk vývojáře (`crops/…`), cache Textractu (`.textract-cache`) obsahuje odpovědi (bbox, ne obrázky). Lokální složky nepatří do repozitáře ani mezi sdílená data.
- Pipeline posílá vykreslené stránky a výřezy do Textractu a Bedrocku. To je přenos do služby AWS ve stejném účtu a regionu (pro hackathon přijatelné), ale znamená to, že čitelný obrázek existuje v paměti pipeline; do logu a do `/tmp` Lambdy se nesmí dostat.
- CloudWatch logy: nikdy nelogovat obsah obrázku ani bloku (knihovna to nedělá, chyby neobsahují data).

### Odvozená data: co z podpisu zůstává

| Odvozené | Kde | Co o podpisu prozradí | Zpětně na obrázek? |
|---|---|---|---|
| `phash` (64 bitů) | `signatures.json` | znaménka 63 nízkých DCT frekvencí tvaru inkoustu | **ne**, 8 bajtů nemůže nést obrázek; slouží jen k Hammingově vzdálenosti (kopie). Dá se použít jako test „je tohle ten podpis?“ nad kandidátem, ne jako zdroj obrázku. |
| `bbox` (relativní) | `signatures.json` | kde na straně podpis je | ne |
| `role`, `role_evidence` | `signatures.json` | čí je a doslovný řádek textu u něj | ne |
| ink maska 64×64 (pokud ji někdo uloží) | v kódu `ink_mask`/`phash_and_mask` jen přechodně | **binární miniatura podpisu**, hrubý tvar čitelný | **částečně ano**. Neukládat, nebo šifrovat jako výřez. V aktuálním `signatures.json` není; hlídat to u `copycheck.py`. |
| embedding výřezu (1024 floatů) | index `wonderfulkb-signatures` (teď prázdný) | viz níže | viz níže |
| embedding stránky | index `wonderfulkb-image`, `#p<n>` (2 vektory) | obsah celé stránky včetně podpisu, smíšený | viz níže |

**Dá embedding výřezu rekonstruovat podpis?** Nezkoušel jsem to, jde o odhad, ne měření.
- Embedding (Titan Multimodal, 1024 floatů) je vzorec pro sémantickou podobnost, ne kompresní kód. Zachovává „co to je“ (rukopis, tvar celku, hustota), ne přesnou dráhu tahu. Z jednoho vektoru dostane útočník s generativním dekodérem nanejvýš věrohodný „podpisovitý“ obrázek, ne podpis, který by prošel porovnáním s originálem. Pro text jsou inverze embeddingů publikované (vec2text), pro tenké tahy rukopisu obecným modelem ne.
- Co embedding umožňuje spolehlivě: **ověřit hypotézu**. Kdo má kandidátní obrázek podpisu (z jiné smlouvy), spočítá jeho embedding stejným modelem a zjistí, jestli sedí. To je stejné riziko jako u phashe, jen jemnější. Je to i záměrná funkce (`similar_signatures`).
- Závěr: embedding je pseudonymizovaný odvozený údaj s nižším rizikem než obrázek, ale ne nulovým. Doporučení: přístup k indexu jen pro roli API a pipeline, `include_vectors=false` jako chování agenta (už v kontraktu), smazání vektorů spolu s případem. Embedding **počítat z výřezu v paměti** před zašifrováním, neukládat výřez čitelně jen kvůli embeddingu.
- Embedding stránky obsahuje i podpis, ale smíšený s textem celé strany; riziko rekonstrukce podpisu je nižší než u výřezu. Pokud ho chceme úplně vyloučit, počítat embedding z **redigované** stránky (oblast podpisu nahrazená zkresleným náhledem).

## 2. Model hrozeb

| Hrozba | Dnes | Po návrhu |
|---|---|---|
| Kdokoli s `s3:GetObject` na bucketu (jiný člen týmu ve sdíleném účtu, uniklá role) stáhne podpisy | ano, všechny tři vrstvy | (a) a (b) jen šifrované, je potřeba i `kms:Decrypt`; (c) viz doporučení |
| Podpis se objeví v odpovědi API agentovi / ve Wonderful (LLM kontext, logy) | `crop_url` je předpodepsaný odkaz na čitelný PNG | `preview_url` jen zkreslený; čitelný jen přes endpoint s auditem |
| Předpodepsaný odkaz se přepošle nebo uloží do cache prohlížeče | platí 300 s | odkaz na čitelný obrázek neexistuje; odpověď `Cache-Control: no-store` |
| Šifrovaný výřez se podstrčí jinému podpisu (záměna objektů) | – | AAD váže na `case_id`, `document_id`, `signature_id`; dešifrování se zlomí |
| Únik jednoho datového klíče | – | klíč je pro každý výřez nový, únik odhalí jeden výřez |
| Únik dumpu bucketu bez KMS | – | šifrované výřezy jsou bez klíče nepoužitelné |
| Zlý insider s právem `kms:Decrypt` | – | **neřeší se**: audit v logu Lambdy to jen zviditelní. Omezit Decrypt politikou klíče. |
| Kopie podpisu vložená do jiné smlouvy | detekuje phash/pixelové porovnání | beze změny (phash zůstává) |

Co návrh **nechrání**: kdo smí číst originální PDF (c), vidí podpis, ať děláme cokoli s odvozenými daty. To je jádro doporučení níže.

## 3. Doporučení (po rozhodnutí uživatele)

Rozhodnutí: **čitelný originál a čitelné stránky se mohou zamaskovat, pokud podpis umíme na vyžádání ukázat dešifrovaný.** Z toho:

| Vrstva | Co se ukládá | Co se přestane ukládat |
|---|---|---|
| **(a) Výřezy podpisů** | `signatures/<sig>.png.enc` (envelope AES-256-GCM + KMS) a `signatures/<sig>.preview.png` (zkreslený náhled) | čitelné `signatures/<sig>.png` (42 existujících: migrace, část 8) |
| **(b) Stránky** | stránky vykreslené **ze zamaskovaného PDF** (nebo vůbec ne trvale) | stránky vykreslené z originálu (23 existujících: migrace) |
| **(c) Originální PDF** | zamaskovaná kopie `cases/<case>/redacted/<document_id>.pdf` s metadaty `original_sha256`, `original_size`; šifrované výřezy | čitelný `original/<document_id>.pdf` a čitelné ZIP balíky: **až po schválení migrace** |
| Odvozená data | `phash`, `bbox`, `role`, `role_evidence`, `copy_suspicion`, `text.txt`; embedding výřezu z paměti, embedding stránky ze zamaskované stránky; maska 64×64 se neukládá | – |

**Co zamaskování neřeší (důležité): detekce podpisů je neúplná.** Textract podle měření týmu nalezne u generických podpisů asi 92 %, u rukopisných asi 59 %; záloha `page_images` a zóna ukotvená na popisek se teprve měří. Zamaskování jen nalezených podpisů proto **nezaručuje**, že v uložených datech žádný čitelný podpis nezůstal. Zamaskovaný soubor je „podpisy odstraněny, kde jsme je našli nebo čekali“, ne „bez podpisů“. Důsledky a zbytkové riziko jsou v části 4; do doby, než se úplnost změří, nesmí se tvrdit víc.

Pořadí v pipeline: detekce na originále (v paměti) → konzervativní oblasti → zamaskování PDF → ověření (`verify_redacted`) → výřez z **originálu** v paměti → `phash`, embedding, `distorted_preview` → `encrypt_image` → zápis `redacted/…pdf`, `.png.enc`, `.preview.png` → čitelné bajty zahodit. Další zpracování (OCR, stránky, embedding) čte jen zamaskovanou kopii.

## 4. Redakce podpisových oblastí (`privacy/signature_privacy/redact.py`)

### 4.1 Jak se maskuje
Nestačí překrýt obdélník: pod ním by zůstal obrázek, vektor i text, který jde z PDF vytáhnout. Používá se redakce PyMuPDF (`add_redact_annot` + `apply_redactions`), která obsah **odstraní**; po ní `scrub` (metadata, miniatury, přílohy, JavaScript) a uložení s `garbage=4` (zahodí staré objekty, takže se původní obrázek nenechá ležet v souboru).

| Úroveň | Odkud | Co se udělá |
|---|---|---|
| `full` | nález detektoru (bbox + okraj 1 % strany) | odstraní text, obrázky (přepíšou se i pixely, takže se maskuje i sken, kde je celá strana jeden obrázek), vektorové kresby, které oblast dotýkají; plocha se zaplní černě |
| `graphics` (zóna) | krátký řádek (≤ 8 slov) s popiskem „podpis“, „razítko“, „signature“ nebo „Za dlužníka/poskytovatele/…“ (i bez diakritiky): 35 mm nad řádkem, šířka aspoň 70 mm | odstraní obrázky (pixely) a kresby, které zónu dotýkají; **text zůstane** (OCR a role ho potřebují), plocha se nevybarvuje |
| `graphics` (blok) | sjednocení nálezů a zón na stránce, pokud není vyšší než 45 % strany | totéž, jednou oblastí přes celý podpisový blok |

Pro rastr (PNG vykreslené jinde) je `redact_png(png, boxes)`: černé obdélníky, u rastru to je skutečné zamazání. Doporučení je ale PNG nevytvářet z originálu, ale vykreslit ze zamaskovaného PDF.

Stránka se mění jen málo: na 16 vzorových PDF (`docs/vzorove-dokumenty`, nálezy z `signatures/examples/sample-output.json`) se mimo oblasti změnilo nejvýš 0,32 % pixelů strany (odstraněné čáry rámečků a tabulek, které zóna dotkla). Velikost souboru roste (u skenů vlivem přepsaných obrázků až 3×, např. 1,2 MB → 3,6 MB).

### 4.2 Jak se ověří, že pod oblastí nic nezbylo
`verify_redacted(original, redacted, regions)` vrací seznam problémů (prázdný = čisté):
1. žádný datový proud obrázku, který v originále zasahoval do oblasti, se v novém souboru nenachází beze změny (porovnání SHA-256 všech objektů; chytá „překryl jsem, ale obrázek tam je“);
2. v oblasti `full` není text ani kresba a vykreslená plocha je černá;
3. v zóně `graphics` po odstranění textu nezbyl žádný obsah (zóna se vykreslí bez textu a musí být jednobarevná).

`changed_outside(...)` měří kolaterální změny mimo oblasti (příliš široké zóny).

**Jediný obdélník pro redakci i ověření (oprava 19. 10. 2026, nález pilotu SYN-A03).** Redakce, ověření i měření kolaterální změny berou plochu z jedné funkce `_region_rect` (`full` = bbox + okraj `PAD` 1 % strany, zóna `graphics` bez okraje), takže ověření nemůže hlídat větší plochu než redakce maže. Příčina pádu u `11_Predavaci_protokol` ale nebyla v rozdílných obdélnících (oba už měly `PAD`): redakce MuPDF maže znaky podle vlastního kritéria glyfu a znak, který obdélník jen protíná, někdy zůstane jako úlomek (písmeno „v“ ze slova Lipová, 0,4 pt uvnitř obdélníku), zatímco ověření počítá každý znak, který obdélník protíná. Po `apply_redactions` proto `_remove_glyph_fragments` najde znaky protínající obdélník a odstraní je celé (jen ty znaky, bez další plochy a bez vybarvení; až 3 kola). Co se přesto nepodaří, zachytí ověření (dokument skončí jako neúspěšný, jako dosud).

Testy (`tests/test_redact.py`): redakce odstraní obrázek, vektor i text; ověření **umí selhat** (nezamaskovaný soubor, nebo jen černý obdélník přes obsah, ohlásí problém); nepokrytý podpis mimo nález i zóny zůstane (test to hlídá, ať se neslibuje víc); sken (celostránkový obrázek) se zamaskuje po pixelech; kolaterální změna se změří. Navíc jsem redakci s ověřením spustil na 16 vzorových PDF včetně skenů: ověření bez problémů. To je kontrola, že **oblasti jsou čisté**, nikoli že pokrývají všechny podpisy.

### 4.3 Konzervativní maskování a zbytkové riziko
Maskujeme víc než nálezy: zóny nad popisky a sjednocený podpisový blok. Tím se zachytí podpisy, které Textract vynechal nebo které jeho bbox zakryl jen zčásti (na jedné stránce vzorového `0_Form_Smlouva` jsem po redakci prohlédl vykreslení: žádný rukopisný podpis nezůstal viditelný, přestože černé boxy z nálezů ležely vedle tahů; jde o jednu stránku, ne o měření).

Co **zůstane** a co s tím:
- Podpis daleko od popisku a mimo nález (paraf na okraji, podpis jinde na straně, razítko s podpisem bez textového popisku): zůstane čitelný. Kryje to jen to, že je jich pravděpodobně málo; **míru nikdo neměří**.
- Skeny bez textové vrstvy nemají popisky v textu, takže zóny vzniknou jen s OCR bloky se souřadnicemi (zatím `bbox: null`); u skenů se spoléháme jen na detektor (59 % rukopisu). Při `bbox` z OCR doplnit `labels` na základě OCR řádků.
- Zóna „nad popiskem“ předpokládá, že podpis je nad řádkem; podpis pod popiskem nebo vedle nepokryje.
- Popisek mimo seznam (jiný jazyk, jiná formulace) zónu nezaloží.
- `graphics` neodstraní text; podpis vložený jako text/font (podpisový font) zůstane čitelný. Je to záměr kvůli OCR, ale je to díra.
- Největší vektorový tah, který zónu dotýká, se odstraní celý; rámečky a tabulky, které ji dotýkají, také (viditelné jako kolaterální změna).

Doporučení: (1) změřit zbytek: na 20 syntetických případech a vzorových PDF ručně prohlédnout zamaskované stránky a spočítat podpisy, které zůstaly (úplnost zamaskování je jiné číslo než úplnost detekce); (2) jako druhou vrstvu omezit čtení bucketu a politiku KMS klíče; (3) tvrdit jen „podpisy odstraněny, kde jsme je našli nebo čekali“.

**Změřeno (19. 10. 2026, [measure/report.md](../privacy/measure/report.md), lokálně, bez zásahu do AWS dat):** úplnost zamaskování na 323 pravdivých podpisech 129 syntetických dokumentů (skupina A, anotace balíku) a na 37 rukopisných podpisech 16 původních PDF (skupina B, ruční prohlídka všech 15 stran s podpisy). Skupiny se nesčítají.

| | skupina A (323) | skupina B (37) |
|---|---|---|
| jen zóny `v1`, bez detektoru | 4,6 % skryto (2,8 až 7,5 %) | neměřeno |
| **stávající knihovna + řetěz detekce pipeline** | **98,8 %** (96,9 až 99,5 %); 4 čitelné, všechny na skenech | **35 z 37** (94,6 %; 82,3 až 98,5 %); 2 čitelné (sken, Textract je nenašel) |
| zóny `v2` (podle role a funkce, na skenech z OCR) + detekce | 323 z 323 (98,8 až 100 %) | 37 z 37 (90,6 až 100 %), u 1 podpisu zůstal nečitelný ocas tahu |

Závěry: (a) zóny podle popisku „podpis“ v generických dokumentech samy téměř nefungují (pod podpisem je jméno a funkce, nad ním hlavička role), (b) skeny bez textové vrstvy nemají zóny vůbec, spoléhají se na detektor (96 % na skenech skupiny A) a čtyři podpisy zůstaly čitelné, (c) zóny `v2` je zachytí, ale u skenů smažou i tištěný text v zóně (průměrně čtvrtina plochy strany), proto je nutné brát text a popisky z originálu před redakcí, (d) `v2` jsem laděl na týchž datech, výsledek 100 % tedy není odhad pro cizí dokumenty, (e) přísné `verify_redacted` selhávalo v měření na okrajových úlomcích slov u 13 % dokumentů (falešný poplach, oprava `measure/verify_tolerant.py`; dry-run migrace u 91 dokumentů ale žádné selhání neukázal, rozpor je neověřený, viz report, část 5). Tvrzení zůstává „podpisy odstraněny, kde jsme je našli nebo čekali“.

Zapomenutý podpis má ještě jednu stinnou stranu: pokud originál po migraci zmizí, takový podpis zůstává čitelně jen v zamaskované kopii a **nemá šifrovaný výřez**, takže ho nejde ani „ukázat odkrytý“. Pozdější lepší detektor ho v kopii najde, zamaskuje a z kopie vyřízne, ale to je poslední čitelná podoba, ne originál.

### 4.4 Dopad na zpracování
- **OCR textu** běží nad zamaskovanou kopií. U `full` oblastí zmizí text pod rámečkem (tištěné jméno bývá mimo bbox podpisu, takže typicky zůstane), u zón text zůstane. Role a popisek podpisů se spočítají **před** redakcí a uloží do `signatures.json`; po redakci už detektor na zamaskovaném místě nic nenajde.
- **Znovuzpracování**: z zamaskovaného PDF nejde znovu vyříznout už zamaskovaný podpis (je jen v `.png.enc`). Pokud se zlepší detektor, nové nálezy jdou zamaskovat v kopii a vyříznout z ní. Pro stávající nálezy se pipeline musí umět spustit v režimu „použij uložený `signatures.json`“, ne znovu detekovat.
- **Deduplikace podle SHA-256**: ingest počítá `document_id = uuid5(case_id:sha256)` z originálu a drží `sha256` v `wonderfulkb-uw-documents`. Zamaskovaný soubor má jiný hash, proto se hash originálu **uchová**: metadata objektu a atribut `original_sha256` v řádku analýzy. Opakovaný upload téhož souboru se tak dál pozná podle řádku v tabulce dokumentů (ne podle objektu v S3). Ověření integrity originálu po smazání nejde (jen porovnat hash nově nahraného souboru).
- **Embedding stránek**: počítat ze stránek vykreslených ze zamaskované kopie. Dva dokumenty se stejně umístěnými černými obdélníky budou mírně podobnější; je to drobný šum. Dnešní 2 vektory v indexu `wonderfulkb-image` (počítané z čitelných stránek) po migraci přepočítat (klíč `#p<n>` je idempotentní, přepíše se). Embedding výřezu se počítá z čitelného výřezu v paměti a u zapomenutých podpisů nevznikne.
- **Lidská kontrola**: strana se ukáže zamaskovaná; podpis přes `GET …/signatures/{id}/image` po odkrytí. Pro zapomenutý podpis žádný odkrytý výřez neexistuje.

## 5. Návrh odkrytí v API (patch pro `docs/openapi-validator-agent.yaml`, neaplikováno)

Nová verze kontraktu 0.3.0, aditivní: `crop_url` zůstane do přechodu v odpovědi s hodnotou `null` (nikdy nevrací čitelný odkaz).

```yaml
  /cases/{case_id}/documents/{document_id}/signatures/{signature_id}/image:
    get:
      tags: [signatures]
      operationId: revealSignatureImage
      summary: Dešifrovaný výřez podpisu (odkrytí na vyžádání, auditováno)
      description: |
        Vrací čitelný PNG výřezu. Určeno pro lidskou kontrolu, ne pro kontext LLM: agent pracuje s `preview_url`.
        Každé volání se zapíše do logu (id API klíče, čas, podpis, výsledek). Odpověď má `Cache-Control: no-store`.
      parameters:
        - $ref: '#/components/parameters/CaseId'
        - $ref: '#/components/parameters/DocumentId'
        - name: signature_id
          in: path
          required: true
          schema: {type: string}
      responses:
        '200':
          description: PNG výřezu
          headers:
            Cache-Control: {schema: {type: string, example: no-store}}
          content:
            image/png:
              schema: {type: string, format: binary}
        '403': {$ref: '#/components/responses/Forbidden'}
        '404': {$ref: '#/components/responses/NotFound'}
        '409':
          description: Výřez není uložen šifrovaně (starý čitelný objekt) nebo chybí; odkrytí není možné
          content:
            application/json:
              schema: {$ref: '#/components/schemas/Error'}
```

Schéma `Signature`:

```yaml
        crop_url:
          type: string
          nullable: true
          deprecated: true
          description: Zrušeno. Vždy `null`, čitelný výřez se neposkytuje odkazem. Použij `reveal_path` a `preview_url`.
        reveal_path:
          type: string
          description: 'Relativní cesta, na které je čitelný výřez po odkrytí: /cases/{case_id}/documents/{document_id}/signatures/{signature_id}/image'
        preview_url:
          type: string
          nullable: true
          description: Předpodepsané URL (300 s) zkresleného náhledu výřezu. Tvar a rozložení jsou hrubé, podpis nejde přečíst.
```

Poznámky pro vlastníka `api/` (`core.py`, `get_signatures`):
- V `get_signatures` místo `s["crop_url"] = self.repo.crop_url(...)`: `s["crop_url"] = None`, `s["reveal_path"] = f"/cases/{case_id}/documents/{document_id}/signatures/{sid}/image"`, `s["preview_url"] = self.repo.crop_url(f"{base}/signatures/{sid}.preview.png")` (stejná funkce presign, jiný klíč; pokud objekt chybí, `None`).
- Nová trasa `^/cases/([^/]+)/documents/([^/]+)/signatures/([^/]+)/image$` → `reveal_signature_image(case_id, document_id, signature_id, query)`. Handler vrací bajty, ne JSON, takže `handle` musí umět vrátit tělo a hlavičky. V Lambda adaptéru `isBase64Encoded: true`, `Content-Type: image/png`, `Cache-Control: no-store`.
- Kontext pro dešifrování brát **z cesty požadavku**, nikdy z `signatures.json`. Klíč objektu: `cases/<case_id>/analysis/<document_id>/signatures/<signature_id>.png.enc` (`signature_id` předem ověřit regulárním výrazem `^sig_\d+$`, ať v cestě nejsou lomítka).
- Odkrytí: `reveal_signature(s3, bucket, key, SignatureContext(case_id, document_id, signature_id), provider, caller=api_key_id(event.requestContext, api_key), request_id=...)` z knihovny `privacy`. Funkce zapíše auditní JSON řádek (logger `wonderfulkb.privacy.audit`: `caller`, `ts`, `case_id`, `document_id`, `signature_id`, `outcome` = `revealed` / `denied` / `error`). `DecryptionError` → `500` s obecnou zprávou, `NoSuchKey` → `404`, objekt bez magic `WKBS` (starý čitelný PNG) → `409`.
- Pozor na jediný sdílený API klíč: `caller` je teď otisk (`fp:` + 12 znaků SHA-256), ne jméno. Pro rozlišení lidí je potřeba víc klíčů (API Gateway usage plan, `requestContext.identity.apiKeyId`); knihovna to přednostně použije.
- Konfigurace Lambdy: `PRIVACY_KMS_KEY_ID=alias/wonderfulkb-signatures` (nebo ARN), region `eu-central-1`.

## 6. Změny v `signatures/signature_pipeline/store.py` (návrh, neaplikováno)

`S3CropStore.save` šifruje a uloží i náhled:

```python
from signature_privacy import SignatureContext, distorted_preview, encrypt_image

class S3CropStore:
    def __init__(self, client=None, bucket=BUCKET, provider=None):
        ...                      # beze změny
        self.provider = provider  # None = default_provider() z PRIVACY_KMS_KEY_ID / WKB_LOCAL_MASTER_KEY

    def save(self, case_id, document_id, signature_id, png):
        base = f"{analysis_prefix(case_id, document_id)}signatures/{signature_id}"
        blob = encrypt_image(png, SignatureContext(case_id, document_id, signature_id), self.provider)
        self.client.put_object(Bucket=self.bucket, Key=base + ".png.enc", Body=blob,
                               ContentType="application/octet-stream",
                               Metadata={"project": "wonderfulkb", "enc": "wkbs1"}, Tagging=TAGGING)
        self.client.put_object(Bucket=self.bucket, Key=base + ".preview.png", Body=distorted_preview(png),
                               ContentType="image/png", Metadata={"project": "wonderfulkb"}, Tagging=TAGGING)
        return base + ".png.enc", None     # klíč šifrovaného výřezu, crop_url zůstává prázdné
```

Ostatní:
- `signatures.json` se mění jen tím, že `crop_s3_key` ukazuje na `.png.enc`; můžeš přidat `"crop_encrypted": true`. Nic dalšího (náhled se hledá podle konvence názvu).
- `LocalCropStore` nechat jen pro vývoj a v README označit, že zapisuje čitelně.
- Redakce: po detekci zavolat `conservative_regions(pdf, nálezy)`, `redact_pdf`, `verify_redacted` a zamaskovanou kopii zapsat do `cases/<case>/redacted/<document_id>.pdf` s metadaty `original_sha256`. Další kroky pipeline čtou kopii (část 4.4). Výřezy se řežou z originálu v paměti.
- Embedding výřezu (`embed.write_signature_vectors(case_id, document_id, [(n, png_bytes)])`) volat **před** zahozením čitelného PNG, ze stejných bajtů, které se šifrují. Nikdy nenačítat výřez zpět z S3 jen kvůli embeddingu.
- `phash` zůstává ze stávajícího kódu. `signature_privacy.phash` dává **stejné hodnoty** (test to kontroluje proti `phash_and_mask`).

## 7. KMS klíč a IAM práva

Klíč existuje (viz hlavička). Zásada: **odkrýt (dešifrovat) smí jen API, ne pipeline.** Pipeline smí šifrovat (`GenerateDataKey`), ale nesmí číst zpět.

Role Lambdy `wonderfulkb-agent-api` (odkrytí):
```json
{ "Effect": "Allow", "Action": "kms:Decrypt",
  "Resource": "arn:aws:kms:eu-central-1:<ACCOUNT_ID>:key/<KMS_KEY_ID>",
  "Condition": { "ForAllValues:StringEquals": { "kms:EncryptionContextKeys": ["case_id", "document_id", "signature_id"] } } }
{ "Effect": "Allow", "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:::wonderfulkb-raw-document-storage/cases/*/analysis/*/signatures/*" }
```
Role pipeline (zápis, bez odkrytí):
```json
{ "Effect": "Allow", "Action": ["kms:GenerateDataKey", "kms:DescribeKey"],
  "Resource": "arn:aws:kms:eu-central-1:<ACCOUNT_ID>:key/<KMS_KEY_ID>",
  "Condition": { "ForAllValues:StringEquals": { "kms:EncryptionContextKeys": ["case_id", "document_id", "signature_id"] } } }
{ "Effect": "Allow", "Action": "s3:PutObject",
  "Resource": ["arn:aws:s3:::wonderfulkb-raw-document-storage/cases/*/analysis/*", "arn:aws:s3:::wonderfulkb-raw-document-storage/cases/*/redacted/*"] }
```
Pipeline **nedostane** `kms:Decrypt`. Další poznámky:
- `GenerateDataKey` stačí na šifrování; migrace čitelných výřezů tedy `Decrypt` nepotřebuje.
- Politika klíče je výchozí (delegace na IAM účtu), proto práva výše řídí IAM. Zpřísnění: explicitní `Deny` pro `kms:Decrypt` všem kromě role API a administrátora; pozor, ať se nezamkne správa (administrátor politiku klíče může vždy změnit, takže jde o ochranu před omylem, ne před insiderem s právy správce).
- CloudTrail zapisuje každé `Decrypt` s `EncryptionContext` (case, dokument, podpis): druhá auditní stopa nezávislá na logu Lambdy. Log Lambdy má i `caller`.
- Klíč nejde okamžitě smazat, jen naplánovat smazání na 7 až 30 dní (a vypnout). Před případným smazáním klíče je všechno šifrované jím nenávratně ztraceno.
- Konfigurace: `PRIVACY_KMS_KEY_ID`. Bez nastavení se `KmsKeyProvider()` obrací na alias `alias/wonderfulkb-signatures`; `default_provider()` ale bez `PRIVACY_KMS_KEY_ID` nebo `WKB_LOCAL_MASTER_KEY` chybu vyhodí, aby se omylem nepoužil jiný klíč.
- Živý test (19. 10. 2026, `privacy/live_check.py`, syntetická data, nic nezapsáno do bucketu): round-trip přes `GenerateDataKey`/`Decrypt` proti skutečnému klíči prošel, jiné `case_id`, `document_id` i `signature_id` odmítnuto; první volání šifrování trvalo 1,7 s (včetně navázání spojení a přihlášení), dešifrování 31 ms (jedno měření).

## 8. Migrace čitelných dat (postup ke schválení, NIC z toho se neprovedlo)

Bucket je verzovaný: `delete-object` bez `VersionId` jen přidá delete marker a čitelná verze zůstane dostupná komukoli s `s3:GetObjectVersion`. Skutečné odstranění je smazání **každé verze s `VersionId`** a je nevratné (bez Object Lock, bez replikace). Proto až po schválení a po ověření.

1. **Zamražení rozsahu**: `aws s3api list-object-versions` pro `cases/*/original/`, `analysis/*/pages/`, `analysis/*/signatures/*.png`, ZIP balíky; seznam (klíč, VersionId, velikost) uložit mimo repozitář. Zapsat počty (dnes: 184 PDF, 23 stránek, 42 výřezů, 2 ZIP).
2. **Zálohovat do bezpečného místa**, než se cokoli smaže: nejlépe šifrovanou kopii (SSE-KMS jiným klíčem) mimo prefix `cases/`, nebo vědomě bez zálohy. Rozhodnutí uživatele.
3. **Zamaskování**: pro každé PDF stáhnout originál, načíst uložené nálezy z `signatures.json` (případně znovu detekovat), `conservative_regions` → `redact_pdf` → `verify_redacted`; zapsat `cases/<case>/redacted/<document_id>.pdf` s metadaty `original_sha256`. Neprojde-li ověření, dokument se zastaví a neřeší dál.
4. **Výřezy**: pro 42 čitelných výřezů `encrypt_image` s kontextem odvozeným z klíče, zápis `.png.enc` a `.preview.png`, ověření round-trip (dešifrovat a porovnat se zdrojem).
5. **Stránky a embeddingy**: vykreslit stránky ze zamaskovaných PDF, přepočítat `#p<n>` v `wonderfulkb-image`. Přepočítat `phash`? Ne, hash z výřezu se nemění.
6. **Ruční kontrola vzorku**: prohlédnout zamaskované stránky (aspoň po jednom dokumentu z každého případu) a zapsat, kolik podpisů zůstalo čitelných (viz zbytkové riziko). **Zastavit a nechat schválit uživatelem.**
7. **Odstranění** (po výslovném souhlasu, po skupinách, nejdřív jedna skupina na zkoušku): `delete-objects` s `VersionId` pro každou verzi čitelných objektů, včetně starších verzí a delete markerů; pak `list-object-versions` pro kontrolu, že nezbyl čitelný objekt. Samostatně ZIP balíky.
8. **Zabránit návratu**: nové nahrávky přistávají čitelně, protože ingest zapisuje originál do S3 hned při uploadu. Je potřeba krok po uploadu (S3 událost → pipeline), který originál zamaskuje a čitelnou verzi odstraní, nebo úprava ingestu. Dokud neexistuje, vzniká okno, kdy je originál čitelný; mezitím omezit čtení bucketu bucket policy.
9. Stávající odkazy: `wonderfulkb-uw-documents.s3_key` a případní další čtenáři `original/…` (ingest, `be-document-processing`) se musí přepnout na `redacted/…`; **zkontrolovat před krokem 7**.

## 8a. Záloha čitelných dat před smazáním (postup, nic se nespustilo)

Rozhodnutí uživatele (19. 10. 2026): **čitelná data se před smazáním zálohují.** Smazání samo je pozdější samostatný krok a tady se neprovádí. Skript: [measure/backup_readable.sh](../privacy/measure/backup_readable.sh) (režimy `--plan`, `--run`, `--verify`; **nespuštěno**, ani `--plan`).

Co se zálohuje (všechny verze, ne jen poslední; bucket je verzovaný):
- čitelné originály `cases/*/original/*.pdf`,
- čitelné stránky `cases/*/analysis/*/pages/*.png`,
- čitelné výřezy `cases/*/analysis/*/signatures/sig_*.png` (ne `.png.enc` ani `.preview.png`),
- volitelně ZIP balíky `cases/*.zip` (`INCLUDE_ZIPS=1`; `codex-tmp.zip` má 446 MB).

Pravidla:
1. **Cíl mimo prefix `cases/`** (skript odmítne `BACKUP_PREFIX` pod `cases/`). Bezpečnější než jiný prefix téhož bucketu je **samostatný bucket** (jiná politika, žádné čtení z role API); jeho založení schvaluje uživatel.
2. **Jiný šifrovací klíč než klíč podpisů.** Záloha je SSE-KMS klíčem `alias/wonderfulkb-backup` (navržený název, **neexistuje**; klíč ani bucket skript nevytváří). Důvod: kdo smí odkrývat podpisy (`kms:Decrypt` na `alias/wonderfulkb-signatures`, role API), nesmí tím získat i zálohu čitelných originálů. Skript před kopírováním ověří, že oba klíče nejsou totožné. Právo `kms:Decrypt` na klíč zálohy má jen správce (obnova), nikoli API ani pipeline.
3. **Seznam klíčů a VersionId** (`--plan`, jen čtení): `backup-plan/versions.tsv` (klíč, VersionId, velikost, ETag, IsLatest, skupina) a `all-versions.json`. Uložit **mimo repozitář**; je to jediný důkaz, co zálohováno bylo, a podle něj se pak maže (část 8, krok 7). Plán obsahuje i počty a velikosti po skupinách a počet starších verzí.
4. **Kopie** (`--run`, vyžaduje `BACKUP_CONFIRM=yes`): `copy-object` každé verze přímo na straně S3 (`?versionId=`) do `<BACKUP_PREFIX>/<klíč>.v-<VersionId>` se SSE-KMS klíčem zálohy; metadata nesou zdrojový klíč a verzi. Idempotentní (existující kopie se přeskočí). Nic se nemaže ani nepřepisuje.
5. **Kontrola** (`--verify`, volitelně `--deep`): pro každý řádek seznamu existuje kopie, má stejnou velikost a je zašifrovaná klíčem zálohy; `--deep` navíc porovná SHA-256 obsahu zdrojové verze a kopie. Mazat se smí až po `--verify` bez chyby (a výslovném souhlasu).
6. **Obnova**: `aws s3api copy-object` z kopie zpět pod původní klíč (vznikne nová verze); jen správce s `kms:Decrypt` na klíč zálohy.
7. Záloha je čitelná data pod jinou ochranou, ne smazání rizika: stále platí zbytkové riziko zálohy v rukou správců klíče. Po skončení hackathonu se záloha smaže (nebo se naplánuje smazání klíče, 7 až 30 dní).

Pořadí s migrací (část 8): zamražení rozsahu (`--plan`) → **záloha (`--run`, `--verify`)** → zamaskování a šifrování (`measure/migrate.py`) → ruční kontrola → teprve pak případné smazání čitelných verzí po skupinách.

## 9. Co je a není ověřeno

Ověřeno bez AWS (68 testů): šifrování a dešifrování, vazba na kontext (každé ze tří polí), odolnost proti poškození (každý bajt bloku), formát s verzí, zkreslení náhledu (ztráta detailu, dva různé podpisy se stejným hrubým rozložením dávají shodný náhled), shoda `phash` se stávajícím kódem, `KmsKeyProvider` a odkrytí proti mocku (moto), audit, redakce PDF a PNG včetně ověření, že pod oblastí nic nezbylo (a že ověření umí selhat).
Ověřeno živě: `KmsKeyProvider` proti klíči `alias/wonderfulkb-signatures` (část 7). Redakce spuštěna lokálně na 16 vzorových PDF: ověření bez problémů, kolaterální změna do 0,32 % pixelů strany.
Neověřeno: napojení do Lambdy, `store.py` a pipeline (jen návrh); IAM politiky a politika klíče (nezkoušeno); výkon při stovkách výřezů (jedno KMS volání na výřez); čitelnost náhledu **lidským okem** na skutečných podpisech (test měří ztrátu informace na syntetických datech); odhad rizika rekonstrukce z embeddingu (úvaha, ne experiment); **úplnost zamaskování na cizích dokumentech** (změřeno jen na syntetických datech a 16 původních PDF, viz část 4.3; zóny `v2` jsou laděné na týchž datech); chování redakce na skenech s vektorovými vrstvami a na PDF s komplikovanými strukturami (formuláře, vrstvy) mimo vzorek.

## 10. Otevřené otázky pro uživatele
1. Schválit migraci (část 8), nejdřív kroky 1 až 6 bez mazání, a zálohu před krokem 7?
2. Kdo zamaskuje nové nahrávky po uploadu (S3 událost, ingest, pipeline)? Do té doby je originál po nahrání čitelný.
3. Přijmout zbytkové riziko neúplné detekce: ukládá se jen zamaskovaná kopie, tvrzení je „odstraněno, kde jsme podpis našli nebo čekali“. Chceme před migrací změřit úplnost zamaskování na 20 případech?
4. Má `preview` zůstat jako samostatný předpodepsaný objekt (návrh), nebo inline base64 v odpovědi?

## 11. Krok 3: odkrytí v Agent API (implementováno v `infra/validator-agent/api/`, v AWS NENASAZENO)

Doplněk k částem 5 a 7; kde se liší, platí tato část. Podrobnosti a konfigurace: `infra/validator-agent/api/README.md`, sekce „Podpisy: náhled a odkrytí“.

- **Volání 3**: `crop_url` se nevrací (pole není vůbec, přechodově může být `null`). Místo něj `preview_url` (předpodepsaný odkaz 300 s na samostatný zkreslený objekt `<sig>.preview.png`, `null` když neexistuje), `reveal_path` a `crop_available`. Starý `signatures.json` bez `crop_s3_key`/`crop_encrypted` (čitelné výřezy před migrací): žádný čitelný odkaz, `crop_available: false`. Přepínač `LEGACY_PLAIN_CROP_URL` (výchozí `false`) je nouzový únik, který obchází rozhodnutí z části 3; zapínat jen na výslovné rozhodnutí.
- **Endpoint** `GET /cases/{case_id}/documents/{document_id}/signatures/{signature_id}/image` (`revealSignatureImage`). Odchylky od návrhu v části 5: místo `409` pro chybějící výřez je `404` (`409` jen pro výřez, který není šifrovaný, a nikdy se nevrací čitelně); selhání dešifrování je obecné `500`, ne `403`; `signature_id` se hledá v `signatures.json`, takže neexistující podpis je `404`; kontext dešifrování je z cesty požadavku, jedinou výjimkou je `crop_source` (`{case_id, document_id, signature_id}` původního kontextu u výřezu zašifrovaného pod jiným podpisem), který mění kontext, ne klíč objektu (ten musí ležet pod `signatures/` téhož dokumentu).
- **Audit**: jeden JSON řádek na volání s platným API klíčem (`signature_reveal`, `caller`, `ts`, `case_id`, `document_id`, `signature_id`, `outcome` = `revealed|not_found|not_encrypted|denied|error`, `request_id`). `caller` je `apiKeyId` (jen REST API s usage plan) nebo otisk `fp:` + 12 hex znaků SHA-256 klíče. Ani klíč, ani obraz v logu nejsou. Neplatný API klíč se jako odkrytí nezapisuje (zamítne se dřív).
- **Kód**: dešifrování je v `api/crop_reveal.py` (formát `WKBS` v1 ze `signature_privacy/blob.py`), protože celá knihovna vyžaduje Pillow, numpy a PyMuPDF. Změna formátu v `blob.py` se tedy musí promítnout i tam; test `test_reveal.py` kontroluje, že blok zašifrovaný knihovnou (lokální provider i mock KMS) API odkryje a že špatný `case_id`, `document_id`, `signature_id`, jiný klíč nebo poškozený bajt selžou.
- **IAM Lambdy**: přibývá jen `kms:Decrypt` na klíč `<KMS_KEY_ID>` s podmínkami `ForAllValues:StringEquals` nad `kms:EncryptionContextKeys` = `case_id`, `document_id`, `signature_id` a `Null: false` (bez `Null` by `ForAllValues` u volání bez kontextu vyšlo vždy pravdivě). `s3:GetObject` na `cases/*/analysis/*/signatures/*` už role má přes `cases/*/analysis/*`, nic navíc se nepřidává. Pipeline `Decrypt` nedostává (část 7 beze změny).
- **Co se nezměnilo a zbývá**: jeden sdílený API klíč znamená v auditu jeden `caller`; čitelné staré výřezy `signatures/<sig>.png` zůstanou čitelné i pro roli API, dokud se nesmažou (část 8); skutečné KMS `Decrypt` z Lambdy ani IAM podmínky nebyly vyzkoušeny, protože nic není nasazené.
