# dedup: stejný obsah v různých případech

Problém: `document_id = uuid5(NS, "<case_id>:<sha256>")`, takže duplicity hlídal ingest jen v rámci jednoho případu. Stejný soubor v jiném případu dostal nové ID, novou S3 kopii, pipeline ho zpracovala znovu (Bedrock, Textract) a vektory se zdvojily. Agent o tom nevěděl.

Tento modul dělá tři věci (schválil uživatel):
1. **Index hashů** (`wonderfulkb-uw-content-hashes`): kde všude leží stejný obsah. Plní ho ingest, pipeline a `backfill.py`.
2. **Pipeline znovupoužije hotovou analýzu** téhož obsahu z jiného případu místo nových volání modelů.
3. **Agent API (volání 1) vrací `duplicate_of` a `duplicate_relevant`**, z čehož Wonderful udělá pravidlo „stejný doklad použit ve dvou financováních“.

**Stav: kód a testy hotové, NIC není nasazeno ani vytvořeno v AWS.** Tabulku, backfill, nasazení ingestu a API schvaluje uživatel (viz „Nasazení“).

## Soubory

| Soubor | Obsah |
|---|---|
| `template.yaml` | CloudFormation: jen tabulka `wonderfulkb-uw-content-hashes` (PK `sha256`, SK `case_document` = `<case_id>#<document_id>`, on-demand, tag `project=wonderfulkb`). |
| `hashindex.py` | `lookup(sha256, exclude_case_id=None) -> [{case_id, document_id, label}]`, `register(sha256, case_id, document_id, label=None)` (idempotentní, jediný `UpdateItem`, `registered_at` jen poprvé, štítek se přepíše jen když je zadaný). Chyba AWS = `HashIndexError` bez hashe a id ve zprávě. |
| `policy.py` | Politika duplicit z `classify/taxonomy.yaml` a `evaluate(...)`; `python -I -m dedup.policy --write ../api/duplicate_policy.json` obnoví snapshot pro Lambdu. |
| `vectors.py` | Přečte vektory dokumentu v S3 Vectors (`#t<i>`, `#p<n>`, `#s<n>`) a zapíše je pod nové klíče s metadaty nového dokumentu. Bez Bedrocku. |
| `reuse.py` | `find_source` (hotová analýza `completed` v jiném případu) a `reuse_analysis` (kopie textu, stran, vektorů, podpisů, řádek). |
| `backfill.py` | Naplnění indexu ze `wonderfulkb-uw-documents` (štítek z analýzy). Výchozí je výpis bez zápisu, zápis `--apply`. |
| `deploy.sh` | `--plan` jen čte a vypíše plán. Bez `--plan` po napsání `deploy` vytvoří stack s tabulkou. |
| `tests/` | 55 testů bez AWS (moto, fake S3 Vectors). |

## Co se mění jinde

**Ingest** (`infra/ingest/app/main.py`, nový `content_hashes.py`, `Dockerfile` kopíruje i ten soubor, `docs/openapi-ingest.yaml`)
- Odpověď `POST /v1/cases/{case_id}/documents` má u každého dokumentu volitelné `also_in: [{case_id, document_id}]` (stejný obsah v JINÝCH případech). `duplicate` zůstává (jen v rámci případu). Prázdné pole = nikde jinde; pole **chybí**, když index nejde přečíst.
- Index nikdy neshodí nahrání: chyba čtení i zápisu se zachytí, do logu jde jen typ chyby (žádný hash, id, název souboru), timeouty 2 s / 3 s. Prázdný `HASHES_TABLE` index vypne.
- Po zápisu dokumentů se všechny dokumenty z požadavku (i existující, tím se index sám doplňuje) zaregistrují. Štítek ingest nezná; doplní ho pipeline.
- **IAM:** role `wonderfulkb-ingest-instance` potřebuje `dynamodb:Query` a `dynamodb:UpdateItem` na tabulku `wonderfulkb-uw-content-hashes`. Šablonu `infra/ingest/template.yaml` jsem neměnil (zadání: jen kód a OpenAPI). Bez oprávnění ingest funguje jako dřív, jen bez `also_in`.
- Ingest je kopie malé části `hashindex.py` (samostatný Docker obraz); test `test_ingest_copy_of_index_code_matches_the_library` hlídá, že píše a čte totéž.

**Pipeline** (`pipeline/run.py`, `adapters.py`, `__main__.py`)
- Po stažení PDF se spočítá SHA-256 a přes `lookup` se hledá jiný případ se stejným obsahem a řádkem `processing_status = completed`. Přednost má ověřený štítek, pak novější. `partial`, `failed`, chybějící řádek, chybějící text nebo neúplné vektory (chybí strana, žádný textový vektor) = nepoužije se a zpracuje se normálně (důvod je v `run.json` pod `reuse`).
- Při znovupoužití se **nevolá** Bedrock, Textract ani vizuální přepis. Kopíruje se `text.txt`, `pages/<n>.png`, štítek, popis, jistota, `page_count`, vektory (text, obraz, podpisy: přečtou se ze S3 Vectors a zapíšou pod `<nový document_id>#…` s `case_id`/`document_id` nového dokumentu a `verified=false`) a `signatures.json`. Řádek má `reused_from = {case_id, document_id}`, `pipeline_version` a `processing_status = completed`.
- Nic se nezapíše, dokud nejsou přečteny všechny zdroje; selže-li čtení, zpracuje se normálně. Selže-li zápis uprostřed, zpracuje se normálně a přepíše se (klíče jsou stejné, takže idempotentně).
- **`verified` se nedědí:** nový dokument je `predicted`, vektory `verified=false`. Už existující ověřený štítek nového dokumentu (opakovaný běh) se nepřepíše.
- **Vypnutí:** `python -I -m pipeline run_case … --no-reuse` nebo `PIPELINE_NO_REUSE=1`; v Pythonu `Options(reuse=False)`. Respektuje se `--skip` (`embed` = vektory se nekopírují, `signatures`, `classify`). Existující `signatures.json` nového dokumentu se nepřepisuje.
- Dokument se po zpracování (i znovupoužití) zapíše do indexu se štítkem. **Přímý režim** (`run_s3`, `run_prefix`, vzorky `pipeline-sample-*`) se do indexu nezapisuje (vzorky by dělaly falešné duplicity), znovupoužít smí.
- Chybí-li tabulka indexu nebo modul `dedup/`, pipeline pokračuje normálně (varování v logu). **Pro `trigger/`:** `trigger/build.sh` musí do balíčku přidat adresář `dedup/` (a `classify/taxonomy.yaml` je tam už); bez něj se znovupoužití v triggeru tiše vypne (`reuse.status = unavailable`). IAM role workeru: `dynamodb:Query`, `dynamodb:UpdateItem` na index, `s3vectors:GetVectors` a `PutVectors` na indexy `text`, `image`, `signatures`, `s3:CopyObject` je v rámci stávajících práv `cases/*`.
- `reused_from` je nový volitelný atribut řádku analýzy. Datový kontrakt `be-validator-agent/docs/validator-agent-storage.md` jsem neměnil (nebylo v zadání); je potřeba tam atribut doplnit.

**Podpisy a šifrování výřezů (předpoklad):** `signatures.json` nového dokumentu má u každého podpisu `crop_s3_key` na výřez ORIGINÁLU (`cases/<původní case>/analysis/<původní doc>/signatures/<id>.png`), nic se nekopíruje. Předpokládá se, že o šifrování výřezů rozhoduje jinde (modul `privacy`): protože je šifrování svázané s kontextem `(case_id, document_id, signature_id)` (AAD), musí odkrytí výřezu u znovupoužitého dokumentu použít `reused_from` (id původního dokumentu), ne id nového. Kdo `reveal_path` implementuje, to musí vědět; **neověřeno**. Smaže-li se původní dokument, výřezy zmizí. `copy_suspicion` se u kopie vrací na `not_checked` a spočítá ho `copy_check` v novém případu; `phash` a boxy zůstávají.

**Taxonomie** (`classify/taxonomy.yaml`): každý typ má `duplicate_policy: flag | ignore`, `settings.duplicate_template_threshold: 3`.
- `ignore`: `vop` (standardní text bez údajů o případu).
- `flag`: všechno ostatní, včetně `zajistovaci_prevod_vlastnickeho_prava`, `vinkulace_pojisteni`, `ruceni`, `smlouva_o_uveru`, `dohoda_o_zaplaceni_kupni_ceny` a `jine`. Vzorky `solom-rec` a `stavby-fiser` potvrzují, že formuláře 2_Form a 3_Form se mezi případy liší dosazenými údaji stran (diff ~180 řádků), nejde o prázdnou šablonu. `technicka_specifikace` je `flag`, ale může jít o katalogový list stejného stroje u dvou odběratelů (možný falešný poplach, záleží na rozhodnutí). Neznámý nebo chybějící štítek = `flag`.
- Navíc: stejný obsah ve `>= 3` různých případech (vlastní se počítá) je šablona, `duplicate_relevant = false`. Práh se mění v taxonomii (`duplicate_template_threshold`) a v API přepsat `DEDUP_TEMPLATE_THRESHOLD`.

**Agent API** (`api/core.py`, `api/template.yaml`, `api/duplicate_policy.json`, `be-document-processing/contracts/openapi-validator-agent.yaml`)
- Volání 1 (`ValidationDocument`) vrací `duplicate_of: [{case_id, document_id, label}]` (bez vlastního případu, prázdné pole = nikde jinde) a `duplicate_relevant: bool`: `true` jen když existuje jiný případ se stejným obsahem, politika štítku je `flag` a nejde o šablonu podle prahu. Štítek se bere z řádku analýzy dokumentu.
- SHA-256 dokumentu API čte z `wonderfulkb-uw-documents` (jen atribut `sha256`, `GetItem`), protože řádek analýzy hash nenese; pak `Query` do indexu. Chyba čtení indexu, tabulky dokumentů nebo politiky = pole se **vynechají**, odpověď zůstává 200, v logu jen typ chyby. Dokument bez známého hashe (vzorek mimo ingest) = pole chybí.
- Lambda se balí jen z `api/`, proto má politiku jako snapshot `api/duplicate_policy.json` (test `test_api_snapshot_matches_taxonomy` selže, když se rozejde s taxonomií) a vlastní kopii vyhodnocení (test `test_api_logic_agrees_with_library…` hlídá shodu s `policy.evaluate`).
- IAM (v `api/template.yaml`): `dynamodb:Query` na index, `dynamodb:GetItem` na `wonderfulkb-uw-documents`. Parametr `ContentHashesTable=""` funkci vypne. Omezení čtení jen na atribut `sha256` přes IAM podmínku jsem nezkoušel.

## Nasazení (nic z toho se nestalo)

```bash
cd infra/validator-agent/dedup
./deploy.sh --plan                    # jen čte: účet, stav tabulek, počet dokumentů, plán; nic nevytvoří
./deploy.sh                           # po napsání "deploy" vytvoří stack wonderfulkb-content-hashes (jen tabulka)
./setup.sh                            # .venv pro backfill a testy (nebo použít pipeline/.venv)
AWS_PROFILE=hackathon .venv/bin/python -I -m dedup.backfill           # výpis, nic nezapíše
AWS_PROFILE=hackathon .venv/bin/python -I -m dedup.backfill --apply   # zapíše všechny dokumenty z `wonderfulkb-uw-documents` (idempotentní; `--plan` 19. 10. napočítal 171)
```
Pořadí: tabulka → backfill → IAM (ingest, worker, API) → nový obraz ingestu → `api/deploy.sh` → `trigger/build.sh` s `dedup/`. Před nasazením API a ingestu tabulka nemusí existovat: obojí funguje bez ní (pole se vynechají).

`python -I -m dedup.backfill` předpokládá, že `infra/validator-agent` je na cestě (`pipeline/setup.sh` ho přidá do `.pth`; v `dedup/.venv` ho přidej stejně, nebo spusť z `infra/validator-agent` s `PYTHONPATH=.`).

## Testy

Výsledky běhu 19. 10. 2026 (pipeline/.venv + `jsonschema`, `fastapi`, `python-multipart` v dočasném adresáři): `dedup/tests` 55 passed, `api` 59 passed (včetně kontraktového testu s duplicitami), `pipeline` 79 passed (včetně testů maskování z `test_redaction.py`). `./deploy.sh --plan` proběhl živě (jen čtení): tabulka ani stack neexistují, 171 dokumentů k backfillu.

```bash
cd infra/validator-agent && pipeline/.venv/bin/python -m pytest dedup/tests -q -c dedup/pytest.ini --rootdir dedup
cd infra/validator-agent/api && python3 -m pytest -q            # + kontraktový test (nyní s duplicitami)
cd infra/validator-agent/pipeline && .venv/bin/python -m pytest -q
```
Pokrytí: stejný obsah ve dvou případech; VOP ve čtyřech případech (nerelevantní, ale vypsaná); individuální doklad ve dvou případech (relevantní) a ve třech (šablona podle prahu); chybějící tabulka, poškozené položky a vypnutý index (pipeline, ingest i API); souběžný `register` (stejný i různé dokumenty) a souběžné nahrání téhož souboru do tří případů; znovupoužití bez volání klasifikace, embeddingu, Textractu i vizuálního modelu; `--no-reuse`; `partial`, chybějící řádek, text a neúplné vektory původního dokumentu; více než 100 textových částí; idempotentní opakování.

## Co není ověřené

- **Znovupoužití při zapnutém maskování (výchozí `PIPELINE_REDACT`)** pracuje se zdrojem, který má `redacted_s3_key`, a výřezy nese přes `crop_source` (část `redaction_step.finish_reuse`, kterou přidala jiná session); ověřeno jen v moto s atrapou šifrovaných výřezů, bez KMS.
- **Nic proti skutečnému AWS.** DynamoDB, S3 a (fake) S3 Vectors jen v moto. Skutečný `s3vectors:GetVectors` / `PutVectors` s kopírovanými vektory (velikost dávky, tvar `data.float32`, metadata) nezkoušen; stojí na tvaru odpovědí, který už používá `api/core.py` a `embed/vectors.py`.
- Souběh v ingestu je testován v moto (vlákna), ne při reálné latenci DynamoDB. Zápis do indexu a vlastní dokument nejsou transakční (dokument může existovat bez záznamu v indexu; opraví ho příští upload téhož souboru, pipeline po zpracování nebo backfill).
- Nasazený ingest, API, Lambda na `python3.14` a trigger s `dedup/` v balíčku. IAM oprávnění nejsou vyzkoušená.
- Souběh dvou pipeline: pokud se dva stejné soubory zpracují současně a žádný ještě není `completed`, oba se zpracují celé (dedup se projeví od třetího).
- Index hlásí duplicitu podle bajtově stejného souboru (SHA-256). Stejný doklad naskenovaný dvakrát nebo uložený jinou aplikací má jiný hash a tím se nepozná; k tomu by sloužily vektory nebo text, mimo rozsah.
- Je-li původní dokument smazán nebo se přepočítá, kopie (text, vektory) zůstává se starými hodnotami; `reused_from` na původní dokument pak může ukazovat do prázdna.
