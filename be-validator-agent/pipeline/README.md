# pipeline: zpracování dokumentu pro validační agent

`run_document(case_id, document_id)` a `run_case(case_id)` podle [validator-agent-storage.md](../../../be-validator-agent/docs/validator-agent-storage.md):
PDF z S3 → text po stranách → stránky jako PNG → klasifikace, vektory, podpisy → jeden řádek v `wonderfulkb-uw-document-analysis`.

## Co přibylo
| Soubor | Obsah |
|---|---|
| `analysis-table.yaml` | CloudFormation šablona tabulky `wonderfulkb-uw-document-analysis` (PK `case_id`, SK `document_id`, on-demand, tag `project=wonderfulkb`). **Nasazená** jako stack `wonderfulkb-document-analysis`, nic jiného se nevytvářelo. |
| `run.py` | `run_document`, `run_case`, stavy `queued` / `processing` / `completed` / `partial` / `failed`. |
| `pdf.py` | textová vrstva po stranách (`pypdfium2`, `pypdf` jako druhý názor) a rozhodnutí, která strana jde do vizuálního přepisu; vykreslení PNG. |
| `vision.py` | Qwen3 VL přes Bedrock Mantle (SigV4), prostý přepis stránky, omezovač rychlosti, opakování při 429/5xx. |
| `adapters.py` | tenké adaptéry na `classify/`, `embed/` a `signatures/signature_pipeline`; chybějící modul = jasná chyba `StepUnavailable`. |
| `__main__.py` | CLI. `setup.sh` založí `.venv` a zpřístupní sourozenecké moduly i pro `python -I`. |

`wonderfulkb/be-document-processing` se neimportuje: jeho `rendering.py` a `pdf_first.py` importují PyMuPDF. Převzaly se jeho model (`qwen.qwen3-vl-235b-a22b-instruct`), endpoint `https://bedrock-mantle.eu-central-1.api.aws/v1/chat/completions`, podpis SigV4 pro `bedrock-mantle`, heuristika použitelné textové vrstvy (≥ 20 znaků a ≥ 3 slova, < 2 % vadných znaků, strana pokrytá obrázkem z ≥ 55 % je sken) a pravidlo, že useknutá odpověď (`finish_reason != stop`) není přepis. Rozdíl: vrací se prostý text, ne JSON s bloky (bloky a bbox pipeline nepotřebuje).

## Jak se spouští
```bash
cd infra/validator-agent/pipeline && ./setup.sh          # jednou: .venv + závislosti
export AWS_PROFILE=hackathon AWS_DEFAULT_REGION=eu-central-1   # aws sso login --profile hackathon
.venv/bin/python -I -m pipeline run_case 17794315-26                  # celý ingestovaný případ
.venv/bin/python -I -m pipeline run_document <case_id> <document_id>  # jeden dokument z tabulky dokumentů
.venv/bin/python -I -m pipeline run_s3 <case_id> "cases/solom-rec/original/10_Podklady k výlatě_objednávka.pdf" \
    [--document-id ID] [--title NÁZEV]                                # vzorové PDF mimo ingest
.venv/bin/python -I -m pipeline run_prefix <case_id> cases/unhappy_scenario/   # všechna PDF pod prefixem jako jeden případ
.venv/bin/python -I -m pipeline report <case_id> [<case_id> ...]      # tabulka stran a stavů
./run_rest.sh                                                         # zbytek datasetu, viz „Dávka“
```
Přepínače: `--skip classify,embed,signatures` (nebo `PIPELINE_SKIP`), `--no-vision` (nevolá Bedrock, skeny skončí v `pages_failed`), `--force-vision` (všechny strany vizuálně), `--json`, `--resume` (přeskočí dokumenty `completed` touto verzí), `--report soubor.json` (čas, stav a počty volání AWS/Bedrocku po dokumentu, průběžně přepisováno). Návratový kód je 1, když některý dokument skončil `failed`.

Z Pythonu: `from pipeline import run_document, run_case, Source, Options`; `run_document("case", None, source=Source("cases/.../x.pdf"))` je přímý režim, `document_id` se pak odvodí jako v ingestu (`uuid5` z `case_id` a SHA-256). Výstupy přímého režimu jdou do `cases/<case_id>/analysis/<document_id>/` s vaším `case_id`, originál se jen čte.

## Chování
- **Text:** strana má použitelnou textovou vrstvu → ta. Jinak (sken, jen zápatí nad celostránkovým obrázkem, rozbité kódování) → vizuální přepis. Strana bez textu a bez obrázku je `blank` a Bedrock se nevolá. `text.txt` = strany oddělené `\f`.
- **Stavy:** `queued` (`run_case` označí všechny dokumenty předem) → `processing` → `completed`. `partial` = některá strana se nepřečetla (`pages_failed`, NS) nebo selhal/chybí krok klasifikace či vektorů (podpisy stav nemění). `failed` = PDF nejde otevřít/stáhnout, nebo se nepřečetla žádná strana. Vědomě přeskočený krok (`--skip`) stav nezhorší. Neznámý dokument vyvolá `DocumentNotFound` a řádek nevznikne.
- **Idempotence:** řádek i objekty se přepisují stejnými klíči. Přepis skenu se cachuje v S3 (`vision/<model>/<n>.txt`), takže opakovaný běh nevolá Bedrock. Ověřený štítek (`label_status = verified`) se při novém běhu nepřepíše a klasifikace se pro něj nevolá.
- **Limity Bedrocku:** přepis stránek sekvenčně, výchozí 20 požadavků/min (`PIPELINE_BEDROCK_RPM`), max. 30 vizuálních stran na dokument (`PIPELINE_MAX_VISION_PAGES`), 4 pokusy s prodlevou 5/10/20 s.
- **Navíc oproti kontraktu:** `analysis/<document_id>/run.json` (způsob přepisu po stranách, výsledky kroků, chyby, počet volání vizuálního modelu) a `vision/` cache. Řádek v DynamoDB má jen atributy z kontraktu, `description` je bez klasifikace prvních ~240 znaků textu, `confidence` se ukládá jako Decimal.
- **Štítek a popis (rozhodnutí uživatele 19. 10.):** u **jednostránkového skenu** nese štítek, popis a jistotu samotné volání vizuálního přepisu (jedno volání; prompt a parser z `classify.build_label_prompt_section` / `LABEL_OUTPUT_SCHEMA` / `parse_label_output`). Odpověď je `<přepis>` + řádek `=== ŠTÍTEK ===` + JSON; rozbitý JSON o text nepřipraví a štítek se doplní voláním `classify_document`. **Vícestránkové skeny, smíšené dokumenty** (text + sken) a dokumenty s textovou vrstvou dostanou jeden `classify_document` nad celým sestaveným textem: pokus dávat štítek v posledním volání víc stránkového skenu selhal (4stránkový protokol dostal `jine`, protože model popsal jen poslední stranu). Není-li `classify` dostupné, jede se také přes `classify_document`. Dokument s ověřeným štítkem se neklasifikuje.
- **Kopie podpisů (`copy_suspicion`):** `detect_signatures` vidí jeden dokument, proto pipeline při zpracování jednoho dokumentu zapíše `copy_suspicion: {"level": "not_checked", "matches": []}`, nikdy `none`. Případový krok `copies.copy_case` (po dokumentu; v dávkách `run_case`/`run_prefix` jednou po posledním dokumentu; samostatně `python -I -m pipeline copy_case <case_id> [--dry-run]`, vyřadí se `--skip copy`) porovná podpisy všech dokumentů případu, které mají `signatures.json`: ink masky se znovu sestaví z PDF podle uložených boxů (`PrecomputedDetector` + `process_pdf`, žádný Textract, žádný výřez se nezapisuje) a `mark_copies` rozhodne. Do existujících `signatures.json` se přepíše **jen** pole `copy_suspicion` (nálezy, detektory, `crop_s3_key` zůstávají), a jen když se hodnota změnila. `none` vznikne jen když byl podpis porovnán se všemi ostatními dokumenty případu (každý má `signatures.json` a nalezené PDF) a má použitelný inkoust; jinak `not_checked`; nalezená shoda je `suspected` s `matches` vždy. Řádku tabulky se doplní chybějící `signatures_s3_key`. Idempotentní (druhé spuštění nic nezmění). Existující `signatures.json` (třeba z CLI s `--fallback`) se při běhu pipeline **nepřepíše** a nehledá se znovu, jen se na něj odkáže.
  Požadavek na modul `signatures/`: ink masky se neukládají (správně, viz privacy), takže `copy_case` pro ně musí projít `process_pdf` včetně rolí a výřezu v paměti. Stačila by veřejná funkce `masks_for(pdf, signatures)` bez rolí; do té doby to funguje, jen pomaleji. Ověřeno na `solom-rec` (`--dry-run`): přepočet reprodukuje existující úrovně `suspected`, rozdíl jen v `matches` jednoho dokumentu.
- **Výřezy:** pipeline nezapisuje žádné výřezy (čitelné ne podle rozhodnutí o soukromí; šifrované jen s `PIPELINE_ENCRYPT_CROPS=1`, přes `S3CropStore(encrypt=True)`, **neověřeno** proti KMS). Pilotní běh 19. 10. dopoledne ještě čitelné výřezy `signatures/sig_NN.png` zapsal, než se `S3CropStore` zpřísnil (počty viz předávací poznámka); verzovaný bucket, migrace patří privacy.
- **Podpisy:** selhání nebo nedostupnost podpisového kroku **nemění** `processing_status` (jen se zapíše do `run.json`); prázdný nález je platný a zapíše se jako `signatures: []`. Adaptér volá `signature_pipeline.detect_signatures(pdf, None, case_id=, document_id=, crop_store=S3CropStore)` a zapíše `signatures.json` bez `crop_url` plus `signatures_s3_key`. Podezření na kopii napříč dokumenty (`process_case`) pipeline nepočítá.

## Dávka: dataset 20 případů (`../dataset/mapping.json`)
**Pilot 19. 10. 2026** (SYN-A01, SYN-B01, SYN-C01; vektory Titan, podpisy, štítek podle pravidel výše; výsledky v `runs/SYN-*.json`): **20 z 20 dokumentů completed**, 79 stran, 697 s (A01 443 s / 9 dokumentů, B01 188 s / 7, C01 73 s / 4; medián 18 s, nejdéle 258 s pro 19stránkové VOP). Volání Bedrocku ~252 za 11,6 min (~22/min): Titan 232 (2 na stranu: obraz a text), klasifikace 18, vizuální přepis 2 (dva skeny v C01, štítek v témže volání); k tomu Textract 79 (1 na stranu, mimo Bedrock). Štítky všech 20 dokumentů odpovídají obsahu (`03_cerpani` je `uhrada_kupni_ceny` s jistotou 0,75, taxonomie nemá štítek pro čerpání úvěru).

**Zbytek** (17 případů SYN-*, `unhappy_scenario`, `solom-rec`, `stavby-fiser`) je připravený, ale nespuštěný: `./run_rest.sh`. Skript je idempotentní (`--resume`), drží odstup (vision 20/min, embed 25/min), loguje do `runs/run_rest-*.log`, reporty do `runs/<případ>.json`, zastaví se po `MAX_BAD` (6) dokumentech, které neskončily `completed`, a na konci vypíše souhrn. `unhappy_scenario`, `solom-rec`, `stavby-fiser` jedou s `--skip signatures`: existující `signatures.json` od session podpisů se nepřepíše, jen se doplní `signatures_s3_key`. `document_id` je u nich `uuid5(ingest namespace, "<case_id>:<sha256>")` (u `solom-rec` ověřeno: 9 z 9 shoduje s existujícími `analysis/<document_id>/`). Odhad zbytku: ~600 stran × ~9 s ≈ 1,5 až 2 h.

## Ověřeno
- `.venv/bin/python -m pytest -q` → 51 testů zelených, bez AWS (moto pro S3/DynamoDB, `httpx.MockTransport` pro Mantle): text/sken/smíšené PDF, sken se zápatím, selhání stránek a `partial`/`failed`, `--no-vision`, cache a idempotence, verified štítek, kontrakt atributů řádku, předání argumentů `classify`/`embed`/podpisům, chybějící sourozenecké moduly, přímý režim, `run_case` s rozbitým dokumentem a řádky `queued`, podpis SigV4 a opakování, omezovač rychlosti, tvar šablony.
- **Živě 19. 10. 2026** (profil `hackathon`, eu-central-1), `report`:

| dokument | stran | textová vrstva | vizuální přepis | prázdné | selhaly | stav |
|---|---:|---:|---:|---:|---:|---|
| `0_Form_Smlouva.pdf` (případ 17794315-26) | 4 | 4 | 0 | 0 | 0 | completed |
| `4_Form_Ruceni.pdf` (17794315-26) | 3 | 3 | 0 | 0 | 0 | completed |
| `receipt_invoice_scan_01.pdf` (17794315-26) | 1 | 1 | 0 | 0 | 0 | completed |
| `0_Form_Smlouva.pdf` (solom-rec, přímý režim) | 4 | 4 | 0 | 0 | 0 | completed |
| `10_Podklady k výlatě_objednávka.pdf` (solom-rec) | 2 | 0 | 2 | 0 | 0 | completed |
| `11_Podklady k výplatě _ Protokol.pdf` (solom-rec) | 4 | 0 | 4 | 0 | 0 | completed |
| `99_KK_systAPI.pdf` (unhappy_scenario) | 5 | 2 | 3 | 0 | 0 | completed |

  Případ 17794315-26 běžel přes `run_case` včetně `classify` a `embed` (vektory zapsány do indexů text a image; `receipt_invoice_scan_01.pdf` navzdory názvu má textovou vrstvu). Vzorky solom-rec a unhappy_scenario běžely přes `run_s3` s `--skip embed,signatures`, aby se vzorky nepsaly do produkčních vektorových indexů; jejich řádky jsou pod `case_id` `pipeline-sample-solom-rec` a `pipeline-sample-unhappy` (lze smazat). Celkem 9 volání vizuálního modelu + 2 volání poslední strany skenů znovu se štítkem v jednom volání (objednávka a protokol), druhý běh stejného dokumentu 0 volání (cache). Přepis `10_...objednávka.pdf` jsem jen prolistoval (působí věrohodně, s obrázkem stránky jsem ho nesrovnával); kvalita přepisu se neměřila (CER/WER ne).

## Neověřeno / známá omezení
- **Podpisy živě neběžely.** `signature_pipeline` vyžaduje PyMuPDF a numpy (a Textract); PyMuPDF se podle zadání neinstaloval, adaptér je ověřený jen na atrapě. Do `.venv` ho jde přidat `pip install --only-binary :all: pymupdf numpy`. Bez toho krok skončí jako `unavailable` (stav dokumentu se nezmění). Textract přehlíží část rukopisných podpisů, `signatures.json` proto není úplný seznam. Detektor z `be-document-processing` (`TextractSignatureDetector`, větev `feat-textract-signatures`) pipeline nevolá přímo, rozhraní je `signature_pipeline.detect_signatures`.
- Skrytá textová vrstva (vykreslovací režim 3) se nerozpozná, chytá se jen přes převahu rastru. Strana složená z vektorových obrysů písma (bez textové vrstvy i obrázku) by se mylně označila jako `blank`.
- Zápis řádku není transakční se zápisem S3 objektů; mezi nimi je dokument ve stavu `processing`. Dva souběžné běhy téhož dokumentu nejsou zamčené.
- Tabulky se ve vizuálním přepisu zapisují jako řádky s `|`, bez bbox a bez jistoty.
- Limit Bedrocku se hlídá jen v rámci jednoho procesu, ne mezi týmem.
