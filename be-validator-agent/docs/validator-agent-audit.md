# Validační agent: nezávislý audit modulů

Stav k 19. 10. 2026, 18:00 až 18:15 místního času. Recenzent: nezávislá session, nic jsem v modulech neopravoval, do AWS jsem jen četl (DynamoDB scan a get, S3 list a get, S3 Vectors list, get a query, CloudFormation, Lambda, IAM, API Gateway, App Runner a Secrets Manager jen metadata; hodnotu žádného tajemství jsem nečetl). Jediný soubor, který jsem vytvořil v repozitáři, je tento report.

**Pozor na pohyblivý cíl.** Při auditu ostatní sessions dál upravovaly kód (`api/core.py` se změnil mezi 17:47 a 18:00, `pipeline/run.py` v 17:52, OpenAPI v 18:00, tabulka `wonderfulkb-uw-document-analysis` vyrostla ze 7 na 36 řádků, objevil se adresář `ref-agent/`). Čísla řádků níže platí pro stav z doby auditu. Testy jsem proto pustil dvakrát (první a druhý běh viz níže).

## 1. Shrnutí

- **Moduly samy o sobě drží:** všech 255 testů v čistých venv prošlo (0 selhání). Kontraktový test mocku ale **už neprojde proti aktuální specifikaci** (3 selhání, chybí `status` ve volání 3, vědí o tom).
- **Zápisy a čtení si ve struktuře odpovídají.** Atributy tabulky, S3 klíče, klíče a metadata vektorů, dimenze 1024, `document_id` (nikde `doc_id` jako metadata) a enum `detector` v reálných datech sedí. Reálná data prošla API handlerem spuštěným lokálně a odpovědi jsou validní podle OpenAPI (23 řádků tabulky v době měření × 5 volání).
- **Co end-to-end nesedí, je mezi moduly a v provozu, ne v tvaru dat:**
  1. nic nespouští pipeline po nahrání dokumentu (B1),
  2. nasazená Lambda je starší než zdroje a spec (B2),
  3. `neighbors` a `similar_signatures` nemají kdo plnit, jsou vždy prázdné (B3, B4),
  4. pipeline píše `copy_suspicion: none` i tam, kde se kopie nikdy nehledaly (V1).
- **Wonderful nevystačí s jedním API ani s jedním klíčem.** Jsou tři služby, dva klíče, a údaje o klientovi (podepisující) se z Case & Client API nedají vzít podle `client_id` (nemá `GET /clients/{id}`). Dokumentace to nepokrývá (kapitola 6).
- **Nasazená Lambda už existuje** (stack `wonderfulkb-agent-api`, `<AGENT_API_BASE_URL>`), ale `docs/wonderful-validator-agent.md` pořád říká „reálné API není nasazené".

## 2. Testy v čistých venv

Každý modul v novém `python3 -m venv` (Python 3.14.7) z vlastních `requirements*.txt`. PyMuPDF jen `pip install --only-binary :all:` a jen pro `signatures/`. Testy běžely s fiktivními AWS přihlašovacími údaji (`AWS_ACCESS_KEY_ID=testing`, bez profilu) a s `-p no:cacheprovider` a `PYTHONDONTWRITEBYTECODE=1`, aby se do modulů nic nezapsalo a nic nešlo na skutečný účet.

| Modul | 1. běh (~17:45) | 2. běh (~18:05) | README tvrdí | Pozn. |
|---|---|---|---|---|
| `api/` | 19 passed | **22 passed** | 18 a 22 (README si protiřečí) | 90 s, moto |
| `classify/` | 29 passed | **29 passed** | 29 | |
| `embed/` | 31 passed | **31 passed** | 31 | |
| `pipeline/` | 38 passed | **41 passed** | 38 | modul se mezitím rozšířil |
| `privacy/` | 53 passed, 1 skipped | **53 passed, 2 skipped** | 54 | skipy: `test_hashing` (shoda `phash` s modulem podpisů) a nový `test_redact`, oba kvůli chybějícímu PyMuPDF (smí jen `signatures/`) |
| `signatures/` | (první pokus selhal na instalaci, viz níže) 23 passed | **23 passed** | 20 | s PyMuPDF z kola |
| `eval/` | 56 passed | **56 passed** | 56 | deps: pytest, pyyaml, pypdf, boto3 |
| **Součet** | | **255 passed, 0 failed, 2 skipped** | | |

Mimo tabulku:
- `infra/validator-agent-mock/contract_test.py` proti mocku (port 18080): v prvním běhu **120 odpovědí validních**, ve druhém (po úpravě specifikace v 18:00) **43 OK, 3 FAIL**: `status is a required property` u volání 3. README api to přiznává („proti mocku už skript neprojde"). Mock ani `docs/wonderful-validator-agent.md` (příklady odpovědí volání 3) se zatím nepřizpůsobily.
- `wonderfulkb/be-document-processing/tests`: **nespuštěno.** Testy importují PyMuPDF, FastAPI, moto a další a pravidlo dovoluje PyMuPDF jen pro `signatures/`. Neověřeno.
- `ref-agent/` vznikl při auditu (bez README, bez venv): **neauditováno.** Jen jsem viděl, že má `tests/test_injection.py`.
- První pokus o venv pro `signatures` a `eval` se při souběžné instalaci zabil spolu s pozadím shellu (neselhal pip, selhal můj skript). Zopakoval jsem je samostatně, výsledky výše jsou z druhého pokusu.
- Zelené testy jsou všechny nad mockem (moto, fake S3 Vectors, `httpx.MockTransport`). Proti skutečným službám se nic z toho neověřovalo; viz „Co je ověřeno a co ne".

## 3. Shoda s kontraktem (`be-validator-agent/docs/validator-agent-storage.md`)

### 3.1 Kdo píše a kdo čte

| Prvek kontraktu | Píše | Čte | Výsledek |
|---|---|---|---|
| Tabulka `wonderfulkb-uw-document-analysis`, PK `case_id`, SK `document_id`, on-demand, tag `project=wonderfulkb` | `pipeline/analysis-table.yaml`, `pipeline/run.py` | `api/core.py` | **Sedí.** Ověřeno `describe-table` a `list-tags-of-resource`. |
| Atributy `title`, `label`, `label_status`, `description`, `confidence` (N), `page_count`, `processing_status`, `pages_failed` (NS), `text_s3_key`, `signatures_s3_key`, `pipeline_version`, `updated_at` | `run.py` (`_row`, `_mark`, `_classify`, `_signatures`) | `core.py` (`get_row`, `query_rows`, `get_document`) | **Sedí** (reálné řádky mají přesně tyto atributy, žádné další). `confidence` jako `Decimal` → API `float`. `awaiting_upload` nepíše nikdo (viz B1). |
| `text.txt`, strany oddělené `\f` | `run.py:~250` | `core.get_document` | **Sedí.** `\f` počet stran = `page_count` (4 = 4). |
| `signatures.json` | `pipeline/run.py` (`_signatures`) i `signatures` CLI (`write_signatures_json`) | `core.get_signatures` | **Sedí** tvarem; **dva zapisovatelé s různým chováním** (V1). Bez `status`, který spec od 18:00 vyžaduje (D6). |
| `signatures/<id>.png` | `signatures/store.py` | `core.crop_url` (předpodepsáno, 300 s) | **Sedí.** |
| `pages/<n>.png` | `run.py` | nikdo v API; `embed` dostává bajty přímo | Sedí. |
| Navíc mimo kontrakt: `run.json`, `vision/<model>/<n>[.labeled].txt` | `run.py` | nikdo | Pipeline to hlásí v hand-overu, kontrakt doplnit. |
| Vektory: bucket `wonderfulkb-vectors`, indexy `text`, `image`, `signatures`, 1024, cosine, ENHANCED | `embed/vectors.py` | `core.py` | **Sedí.** `get-index` potvrdil 1024, cosine, ENHANCED. |
| Klíč `<document_id>#t<i>`, `#p<page>`, `#s<n>` | `embed` | `core._chunk_no`, `_page_no`, `_sig_no` | Sedí. Pro podpisy je vazba křehká (D4). |
| Metadata `case_id`, `document_id`, `page`, `label`, `verified`, `model`, `model_version`; u textu `chunk_id`, `page_from`, `page_to` | `embed/vectors.py:_meta` | `core._vec_out`, `query_neighbors` | **Sedí.** Zkontrolováno na reálných vektorech (`a15b15f8…#t0`, `#p1`): přesně těchto 10 (text) a 7 (obraz) klíčů, `verified: false`, `model_version` `v2` a `v1`, 1024 hodnot. **`doc_id` se jako název metadat nepoužívá nikde** (`grep`; zbývá jen jako lokální proměnná). |
| Enum `detector` (`textract`, `vision_llm`, `page_images`) | `signatures/detect.py` | OpenAPI | Reálná data: 71× `textract`, 8× `page_images`, sedí. Latentní rozpor P6. |
| Enum `role`, `role_source` | `signatures/roles.py` | OpenAPI | Sedí (reálně `borrower`, `buyer`, `guarantor`, `insurer`, `provider`, `supplier`, `unknown`; `role_source` `nearest_text` nebo `null`). |

### 3.2 Reálná data, čtení naprosto bez zápisu

Vybral jsem tři řádky (dva požadované plus sken) a prošel je od DynamoDB přes S3 a S3 Vectors až po lokálně spuštěný `core.handle` (kód z pracovní kopie, AWS profil `hackathon`, API klíč jen lokální náhodný řetězec; nasazenou Lambdu jsem platným klíčem nevolal).

| Řádek | Zdroj | API (lokálně nad reálnými daty) |
|---|---|---|
| `17794315-26` / `a15b15f8-…` (smlouva, textová vrstva) | `text.txt` 8 784 B, `pages/1..4.png`, `run.json`, `signatures.json` (2 podpisy), 7 textových a 4 obrazové vektory, všechny `verified=false` | doc: 200, 4 strany, popis, `confidence 0.92`; vectors: 7 `text_vectors` (c0 až c6, správné `page_from`/`page_to`), 4 `image_vectors`, 1024 hodnot, `neighbors: []`; signatures: 2 podpisy, role `borrower` a `provider`, `crop_url` předpodepsaná |
| `pipeline-sample-solom-rec` / `a1449994-…` (objednávka, sken přes vizi) | `text.txt` 5 005 B, `vision/qwen…/1.txt`, `2.labeled.txt`; **žádné vektory, žádný `signatures_s3_key`** | doc: 200, popis z obsahu; vectors: `[]`, `[]`, `neighbors: []`; signatures: `[]` (staré API) / `status: not_run` (pracovní kopie) |
| `17794315-26` / `d2b0491c-…` (účtenka, `jine`) | `signatures.json` s 0 podpisy, vektory ano | vše validní, `signatures: []`, `status: completed` |

Všech 23 řádků tabulky v době měření × (detail, vektory s hodnotami, vektory bez hodnot + `similar_to_verified`, podpisy, seznam) validních podle `be-document-processing/contracts/openapi-validator-agent.yaml` kromě odpovědí `409`, které mají jiné schéma (`NotReady`) a byly validní. Všech 40 `signatures.json`, které v bucketu byly v době měření, bylo podle starší spec validních; podle nové (s povinným `status`) **ne** (D6). Později jich přibylo (49).

Při čtení starou verzí `core.py` (stejnou jako nasazená) vrátil řádek `17794315-26/a15b15f8` pro podpisy **`signatures: []`**, i když v S3 leží `signatures.json` se 2 podpisy: řádek nemá atribut `signatures_s3_key` (zapsal ho jen běh s `signatures: skipped`, soubor později přidala session podpisů). Pracovní kopie to opravuje (fallback na konvenční klíč a `status`), nasazená Lambda ne (B2).

## 4. Nálezy

Závažnost: **B** blokuje end-to-end, **P** pravděpodobná chyba, **D** drobnost. „Zdroj" znamená, jak jsem to zjistil.

| ID | Zav. | Modul | Soubor, řádek | Důkaz | Doporučená oprava |
|---|---|---|---|---|---|
| B1 | **B** | pipeline, ingest, API | `pipeline/__main__.py`; `infra/ingest/template.yaml`; `api/core.py:312` | Pipeline je jen CLI. `s3api get-bucket-notification-configuration` je prázdné, `events list-rules` a event source mappingy pro `wonderful*` nic nevrátily. Nový případ nahraný přes ingest nemá řádek v analýze, `GET …/documents` vrací `404 Case neexistuje` (Lambda má `CASES_TABLE=""`, takže `case_exists` hledá jen v analýze). Stavy `awaiting_upload` a `queued` slibované v `wonderful-validator-agent.md` §1 vznikají jen po ručním `run_case`. | Rozhodnout, kdo pipeline spustí (S3 event → fronta → worker, nebo ručně a pak to napsat Wonderful). Do té doby: Wonderful bere autoritativní seznam z ingestu a dokumenty chybějící v Agent API bere jako „nezpracováno". Případně list vracet z `wonderfulkb-uw-documents`. |
| B2 | **B** | api (nasazení) | `api/core.py`, `api/template.yaml`, stack `wonderfulkb-agent-api` | Stack vytvořen 15:44 UTC, Lambda 15:45 UTC. Stažený balíček (bez čtení secretu) se liší od pracovní kopie (`/healthz` před/po odříznutí `/v1`), od té doby přibyly: `status` ve volání 3, fallback na `signatures.json`, `object_exists`, `_read_signatures`. Spec od 18:00 vyžaduje `status`, nasazená Lambda ho nevrací. `docs/predani-wonderful.md` to sám zakazuje odeslat před opravou. | Po zelených testech přenasadit (potřebuje souhlas uživatele, `deploy.sh` ho ptá), pak `verify_deployed.py`. Dokumentaci srovnat. |
| B3 | **B** | embed, pipeline, API | `embed/vectors.py:142` (`set_verified`), `:40` (`"verified": False`) | Nikdo v produkčním kódu nevolá `set_verified`; `label_status` je všude `predicted` (23 řádků), nic nezapíše `verified`; `query-vectors` s filtrem `verified=true` na indexu `wonderfulkb-text` vrátil `{"vectors": []}`. `neighbors` jsou proto vždy `[]`. `wonderful-validator-agent.md` §3 popisuje `neighbors` jako hlavní způsob ověření typu. | Naplnit ověřený korpus (např. z `eval/truth.yaml` nebo z lidsky potvrzených dokumentů: `set_verified` + `label_status=verified` v řádku v jedné operaci), jinak říct Wonderful, že `neighbors` zatím nejsou. |
| B4 | **B** | embed, signatures, API | `embed/vectors.py:128` (`write_signature_vectors`), `api/core.py:502` (`_similar`) | `write_signature_vectors` nevolá nikdo mimo testy; `list-vectors` na `wonderfulkb-signatures` vrací `[]`. `match_client=true` tedy vždy dává `similar_signatures: []`. A i kdyby byl index plný, `_similar` hledá jen v rámci stejného `case_id`, ne „téhož klienta" (OpenAPI), takže nemá s čím srovnat podpis klienta (reference podepisujících z Case & Client API do indexu nikdo nezapisuje). | Buď podpisové vektory napojit a vyjasnit význam „klient", nebo `similar_signatures` ze spec vyřadit/označit jako nepodporované. |
| V1 | **P** | pipeline, signatures | `pipeline/run.py:313` (`_signatures`), `signatures/signature_pipeline/interface.py:6`, `models.py:38` | Cesta přes pipeline volá `detect_signatures`, který nikdy nepočítá `copy_suspicion` (potřebuje ostatní dokumenty případu) a zapíše literál `"level": "none"`. V reálných datech: u 21 dokumentů zpracovaných pipeline (`SYN-A01/A02/B01/C01`) je **0 × `suspected`**, zatímco u dřívějších běhů přes CLI `process_case` je 13 × `suspected`. Dokumentace Wonderful říká „chybějící `copy_suspicion` nečtěte jako `none`", ale tady je `none` napsáno, i když se nepočítalo. Znovuspuštění pipeline navíc přepíše `signatures.json` z CLI (včetně `page_images` záložní detekce) verzí jen s Textractem. | Po `run_case` spustit `process_case` nad celým případem (nebo `mark_copies` v pipeline) a zapsat `copy_suspicion: null` tam, kde se nepočítalo. Pipeline nesmí přepisovat CLI výstup bez `--fallback`. |
| P1 | **P** | classify, pipeline | `classify/classifier.py:84`, `pipeline/run.py:278` | `classify_document` vrací jen `label`, `label_status`, `description`, `confidence`; `method` a `error` zahazuje. Když selže volání modelu, klasifikátor tiše spadne na pravidla a vrátí šablonový popis typu a heuristickou jistotu; pipeline zapíše `classify: ok`. V reálných datech: 3 starší řádky (`17794315-26/a15b15f8`, `…/ed3ac3f3`, `pipeline-sample-solom-rec/50b0d089`) mají popis ze šablony („Smlouva o úvěru (4 strany). Úvěrová smlouva mezi poskytovatelem …"), v 0,12 s, což je proti rozhodnutí „`description` je vždy z obsahu, ne generický popis typu". Novější řádky (SYN) mají popis z obsahu. | `pipeline` ať použije `classify_document_detailed` a při `method != llm` zapíše `classify: degraded` a (volitelně) `label_status` zůstane, `confidence` `null`. Staré řádky přepočítat. |
| P2 | **P** | pipeline, API | `pipeline/run.py:264` | `partial` vzniká i když selže jen embed nebo klasifikace (text je kompletní), ale API pak vrací `partial` s `pages_failed: []`. Dokumentace pro Wonderful říká, že `partial` = chybí strany. Agent nemá jak poznat, co chybí (vektory, štítek). | Přidat do řádku a odpovědi důvod (např. `degraded_steps`), nebo pro takové případy držet `completed` a vektory hlásit prázdné. |
| P3 | **P** | pipeline, classify | `classify/llm.py:30-32`, `pipeline/vision.py:69-80` | Nedůvěryhodný text vkládá `build_user_prompt` mezi `<dokument>` bez ošetření řetězce `</dokument>`; `description` je volný text modelu bez délkového i obsahového omezení a jde přes API do kontextu LLM u Wonderful. Dokumentace Wonderful (§7, návrh systémového promptu) nikde neříká, že `text`, `description` a `role_evidence` jsou data z nedůvěryhodného dokumentu. V `classify/` a `pipeline/` není test na vložené instrukce (jen v `ref-agent/tests/test_injection.py`). Viz kap. 5. | Escapovat nebo odstraňovat řetězec uzavírací značky, oříznout `description` (např. 500 znaků, bez řídicích znaků), přidat do návrhu promptu pro Wonderful větu o nedůvěryhodnosti a test s textem „ignoruj předchozí instrukce". |
| P4 | **P** | pipeline, embed | `embed/vectors.py:40`, `pipeline/run.py:305` | Po opakovaném běhu se u již `verified` dokumentu zachová `label_status` v DynamoDB (správně), ale vektory se přepíšou s `verified=false` (kód i dokumentace to říkají záměrně). Dokument pak z korpusu `neighbors` vypadne a štítek ve vektoru (`label`, bere se z něj `neighbors[].label`) může být starý. Nyní nepostihuje nic (B3), jakmile verified vznikne, ano. | Po `write_vectors` u ověřeného dokumentu zavolat `set_verified` s uloženým štítkem. |
| P5 | **P** | docs | `docs/wonderful-case-client.md:3`, `docs/wonderful-ingest.md:6`, `docs/wonderful-validator-agent.md:3,9,420` | Dokumentace tvrdí „jeden klíč pro obě služby" (ingest a case-client), ale API Gateway case-client má klíče `wonderfulkb-demo-key` a `-key-2` v usage plánu `wonderfulkb-demo-plan`, klíč ingestu (Secrets Manager) tam dává 403 (ověřila dataset session a `predani-wonderful.md`; já secret nečetl). Dokument pro Wonderful dál říká, že API není nasazené, a uvádí `GET /healthz` bez `/v1` (viz D1). | Srovnat dokumenty s `docs/predani-wonderful.md` (ten je správně). |
| P6 | **P** | signatures, eval | `signatures/signature_pipeline/detect.py:205` | Třída `LabelAnchoredDetector` má `name = "label_anchored"`. Tato hodnota není v enumu `detector` (OpenAPI i storage kontrakt). Zatím se nikde nepoužívá a v datech není, ale jakmile se zapojí do `CombinedDetector`, odpověď API poruší spec a Wonderful strict parser spadne. | Přidat hodnotu do enumu před zapojením, nebo ji mapovat na `page_images`. |
| P7 | **P** | classify, pipeline | data, `pipeline/README.md` | `pipeline-sample-solom-rec/99da30aa` (čtyřstránkový Protokol, sken) má `label: jine`, `confidence: 0.95`. Pipeline README to přiznává. Vysoká jistota špatného štítku vede pravidla k nesprávnému „dokument chybí". | Dokončit klasifikaci celého skenu až po přepisu všech stran (už v plánu) a `confidence` pro `jine` omezit. |
| D1 | D | api | `api/core.py:563`, `api/template.yaml` | Na nasazené Lambdě `GET /v1/healthz` bez klíče dává **403** a `GET /healthz` dává **404** (ověřeno curlem, bez klíče). Dokumentace pro Wonderful slibuje `GET /healthz` bez `/v1` a `200`. Pracovní kopie opravuje `/v1/healthz`, ale cesta bez `/v1` nikdy do Lambdy nedojde (stage `v1`). | Do dokumentace psát `/v1/healthz`. |
| D2 | D | pipeline | `pipeline/run.py:243` | Žádný strop počtu stran u vykreslení a embeddingu (jen `max_pdf_bytes` 50 MB a `max_vision_pages` 30 u vize). Stostránkový nebo pětitisícstránkový PDF → tisíce volání Titanu proti sdílenému limitu 50 požadavků/min a všechny PNG v paměti najednou. | Strop stran (např. 200) → `partial` s `pages_failed`. |
| D3 | D | pipeline | `pipeline/aws.py:22` | Objekty `text.txt`, `pages/*.png`, `run.json`, `vision/*` se zapisují bez tagu `project=wonderfulkb` (ověřeno `get-object-tagging`: `[]`). Objekty podpisů z `signatures/store.py` tag mají. Bucket tag `project=wonderfulkb` má. | Přidat `Tagging="project=wonderfulkb"` do `put_bytes`. |
| D4 | D | api | `api/core.py:540` (`_sig_no`) | Klíč vektoru podpisu se skládá z čísla v `signature_id` (`sig_03` → `#s2`), zatímco `embed` číslo odvozuje z pořadí výřezů a neumí čistit staré klíče. Při změně počtu podpisů po opakovaném běhu zůstanou osiřelé vektory a špatné párování. Nyní bez dopadu (B4). | Při napojení psát `signature_id` do metadat a `_sig_no` nepoužívat. |
| D5 | D | signatures, be-document-processing | `be-document-processing/src/document_processing/signatures.py`, `signatures/signature_pipeline/` | Dvě nezávislé implementace Textract podpisů: jiný formát `signature_id` (`sig-<strana>-<hash>` vs `sig_NN`), jiná pravidla role (dvě sady regulárních výrazů), jiné volání Textractu (async `StartDocumentAnalysis` vs `analyze_document` po stránkách). be-dp rozlišuje `status: completed/failed`, což agent API původně nemělo. Pipeline si navíc vizuální přepis napsala znovu místo importu z be-dp (kvůli PyMuPDF). Při souběhu se Textract volá dvakrát. | Rozhodnout, který detektor je zdroj pravdy pro API. |
| D6 | D | docs | `be-validator-agent/docs/validator-agent-storage.md:31` | Storage kontrakt říká, že `signatures.json` je „přesně tělo odpovědi volání 3", ale volání 3 teď má povinné `status`, který soubory (40 v době měření) nemají; API ho dopočítává. | Upravit text: „bez `crop_url` a bez `status`". |
| D7 | D | api | `api/` (balíček Lambdy) | `sam build` zabalil celý adresář: v nasazené Lambdě jsou `test_api.py`, `fixtures.py`, `live_smoke.py` (čte Secrets Manager), `deploy.sh`, README. Role to nevyužije (nejmenší práva drží), jde o zbytečnou plochu. Template to přiznává v komentáři. | `CodeUri` na podadresář jen s `core.py` a `app.py`. |
| D8 | D | mock, docs | `infra/validator-agent-mock/`, `docs/wonderful-validator-agent.md` | Mock nevrací `status` ve volání 3 (3 FAIL kontraktového testu), příklady odpovědí v dokumentu pro Wonderful jsou z mocku. Dokument tvrdí `confidence: null` u `99_…`, reálná pipeline dává u těchto dokumentů 0.95. | Srovnat mock a příklady. |

Poznámka k B2: tuto věc session API sama vidí a řeší (`predani-wonderful.md`, „Před odesláním"); v tabulce zůstává jako B, dokud nasazená verze není nová.

## 5. Bezpečnost

### 5.1 Klíče, tajemství, logy
- **Repozitář:** `grep` na `AKIA…`, `aws_secret_access_key`, PEM bloky, `x-api-key` s hodnotou nenašel nic mimo fiktivní hodnoty v testech (`AKIATEST`, `offline-test`). Hodnota API klíče není ani v README, ani v `docs/`. V repozitáři jsou veřejné adresy služeb (`<INGEST_APP_ID>.…awsapprunner.com`, `<CASE_API_ID>.execute-api…`, `<AGENT_HTTP_API_ID>.execute-api…`) a ID účtu, což tajemství není.
- **Zdroje klíče:** `api/core.py:102` (`KeyStore`) čte klíč ze Secrets Manageru, cachuje 5 minut, porovnává `hmac.compare_digest`, nevypisuje, chyba čtení secretu loguje jen konstantní větu. `dataset/upload_cases.py` předává klíč curlu přes stdin (`-K -`), ne v argumentech. `ref-agent` bere klíče jen z prostředí (neauditováno). Lambda `Environment` obsahuje pouze názvy (`API_KEY_SECRET` je název secretu, ne hodnota).
- **Logy:** `core.py:577` loguje `log.exception("Neošetřená chyba")` (trasa bez hlaviček a parametrů, `server.py:log_message` vypisuje jen cestu, ne query). `classify/llm.py` loguje kód výjimky, `vision.py` jen kódy (`BEDROCK_HTTP_<status>`). `run.json` v S3 obsahuje `str(error)` u selhání kroků (`pipeline/run.py:_step`); text výjimek botocore může nést názvy objektů, ne tajemství.
- **`live_smoke.py` a `verify_deployed.py`** čtou secret (nepřipsují). `live_smoke.py` zapisuje a maže vlastní testovací data ve skutečném AWS, což storage kontrakt dovoluje jen u vlastních prefixů; neověřoval jsem, že po sobě uklidil všechno.
- **Jeden klíč pro Ingest a Agent API** (`wonderfulkb/ingest-api-key`): kompromitace jednoho znamená kompromitaci obou. Agent API je jen čtecí, ale vrací texty bankovních dokumentů. Pro hackathon přijatelné, doporučuji aspoň oddělený secret před ostrým provozem.
- **API Gateway před Lambdou nemá autentizaci ani WAF**, klíč kontroluje až kód Lambdy; globální limit trasy je 10 req/s (burst 20), takže hrubá síla je prakticky vyloučená jen pro dostatečně dlouhý klíč (délku jsem nezjišťoval).

### 5.2 IAM a pojmenování
- **Role `wonderfulkb-agent-api-lambda`** (zkontrolována `iam get-role-policy`): `dynamodb:GetItem` a `Query` na jedinou tabulku, `s3:GetObject` jen `cases/*/analysis/*`, `s3vectors:GetVectors` a `QueryVectors` na tři indexy, `secretsmanager:GetSecretValue` jen na `wonderfulkb/ingest-api-key-??????`, logy jen do vlastní skupiny. Žádné spravované politiky. **Nejmenší práva dodržena.** Role a stack mají `project=wonderfulkb`, Lambda `wonderfulkb-agent-api`, tag je i na tabulce, S3 Vectors bucketu a bucketu dokumentů.
- **Pipeline, embed, classify, signatures, dataset:** nemají vlastní IAM šablonu, běží pod vývojářskou rolí `AWSReservedSSO_ai-hackathon-TeamAdmin`. Nejmenší práva se u nich nedají posoudit; až poběží mimo notebook (B1), bude potřeba role. Jediná šablona je `pipeline/analysis-table.yaml` (tag ano).
- **`infra/ingest/template.yaml`:** role má `s3:PutObject/GetObject` na `cases/*`, tedy i do `analysis/`. Ingest tam nezapisuje, ale mohl by přepsat výstup pipeline; stačilo by zúžit na `cases/*/original/*`.
- **Prefix a tag:** nově vytvořené zdroje (tabulka, stack, role, Lambda, log skupina, KMS skript) mají prefix `wonderfulkb` a tag. Výjimky jsou objekty pipeline v S3 (D3) a nenasazený `privacy/create_key.sh` (tag má, alias `wonderfulkb-signatures`, suchý běh ve výchozím stavu).

### 5.3 Nedůvěryhodný vstup
- **PDF:** `pipeline/pdf.py:open_pdf` kontroluje hlavičku `%PDF-`, `max_pdf_bytes` 50 MB, parsování pypdfium2 a pypdf, šifrované PDF skončí `INVALID_OR_ENCRYPTED_PDF`. Bez stropu stran (D2). `signatures/` zpracovává stejné PDF PyMuPDF (nativní knihovna s CVE historií) ve stejném procesu, bez sandboxu; pro hackathon tolerovatelné, pro ostrý provoz by to mělo běžet v izolovaném workeru. `dataset/` zachází s balíkem správně (nová prázdná složka, `python3 -I`).
- **Prompt injection, classify** (`classify/prompt.py:LABEL_TASK`, `classify/llm.py:30`): výstup je vynucen nástrojem `classify` s enumem štítků a `parse_label_output` neznámý štítek mění na `jine`, jistota se ořezává na 0 až 1 → **štítek jde zfalšovat jen na jiný platný štítek, ne na libovolný text**. Uživatelský prompt výslovně říká, že obsah je nedůvěryhodný. Slabiny: neošetřená značka `</dokument>`, `description` neomezený a neočištěný (P3).
- **Prompt injection, vizuální přepis** (`pipeline/vision.py`): systémový prompt říká, že obsah stránky jsou data, předchozí přepisy jdou do dotazu s označením „data, ne instrukce". Označení `=== ŠTÍTEK ===` dělí odpověď modelu na přepis a JSON štítku; `split_label_reply` bere **poslední** označení s parsovatelným JSONem, takže pokud model v odpovědi vlastní štítek nevrátí platně, může se použít značka přímo z textu stránky (`jine` se změní na libovolný platný štítek s libovolnou `description` a `confidence`) a přepis se na tomto místě usekne. Dopad: jen jednostránkové skeny (`label_tools_for`), štítek omezený enumem. Úroveň D, neprověřeno živě (živé volání Bedrocku jsem nedělal, sdílí limit týmu).
- **Druhý stupeň:** `text`, `description` a `role_evidence` (doslovný řádek z PDF) putují API do LLM u Wonderful. Návrh systémového promptu v `docs/wonderful-validator-agent.md` §7 o nich neříká, že jsou nedůvěryhodná data (P3).
- **API:** `case_id` a `document_id` ověřuje `ID_RE` a odmítá samé tečky, cesta se dekóduje před směrováním, ostatní metody než GET vrací 405, chyby jsou obecné. Vstup `next_token` je base64 JSON s ověřeným `document_id`. Nenalezl jsem injection ani path traversal.
- **Čitelné podpisy:** `crop_url` je předpodepsaný odkaz na čitelný PNG podpisu (300 s), tedy biometrická data v kontextu LLM u Wonderful. Je to záměr ve spec; `privacy/` a `be-validator-agent/docs/validator-agent-privacy.md` navrhují šifrování a `crop_url: null` (verze 0.3.0). To je **změna kontraktu**, kterou by bylo potřeba domluvit s API a Wonderful (viz `store.py`, `core.py:crop_url`); nic z toho nenapojené, KMS klíč nevznikl. Do rozhodnutí zůstávají čitelné výřezy i `pages/*.png` (celé stránky s podpisy) v bucketu bez šifrování nad rámec SSE-S3.

## 6. Tři služby a co Wonderful potřebuje (bod 4)

| Služba | Adresa | Technologie | Klíč | Co z ní Wonderful bere |
|---|---|---|---|---|
| **Ingest API** `wonderfulkb-ingest` | `<INGEST_API_BASE_URL>` | App Runner (kontejner) | `x-api-key`, ověřuje služba, hodnota ze Secrets Manageru `wonderfulkb/ingest-api-key` | nahrání PDF; **`GET /cases/{case_id}/documents`**: autoritativní seznam nahraných dokumentů (`document_id`, `filename`, `size_bytes`, `received_at`, `with_urls` pro stažení originálu) |
| **Case & Client API** `wonderfulkb-case-client` | `<CASE_API_BASE_URL>` | API Gateway REST + Lambda | **vlastní** klíče v usage plánu `wonderfulkb-demo-plan` (`wonderfulkb-demo-key`, `-key-2`); klíč ingestu vrací 403 | `GET /cases/{id}` (číslo úvěrové smlouvy, předmět, `metadata` s protistranami), `GET /clients` (jméno, IČO, `signatories`, `kyc`), `GET /clients/{id}/cases` |
| **Agent API** `wonderfulkb-agent-api` | `<AGENT_API_BASE_URL>` | HTTP API + Lambda (Python 3.14) | `x-api-key`, ověřuje Lambda, **stejná hodnota** jako ingest (secret `wonderfulkb/ingest-api-key`), potvrzeno v `predani-wonderful.md` | text, štítek, popis, jistota, vektory + `neighbors`, podpisy (role, `copy_suspicion`) |

Co pravidla ve Wonderful reálně potřebují a odkud:

| Potřeba | Zdroj | Pokryto v `docs/wonderful-validator-agent.md`? |
|---|---|---|
| Seznam dokumentů případu | Ingest `GET /cases/{id}/documents` (nebo Agent API list jen pro zpracované) | **Částečně.** §1 zmiňuje seznam (0) a „nebo máte z Ingest API", ale nevysvětluje, že Agent API vrací jen zpracované dokumenty a že nezpracovaný případ dává 404 (B1). Důležitá je cesta se stejnou adresou na dvou službách. |
| Údaje o případu (číslo smlouvy, předmět, protistrany z `metadata`) | Case API `GET /cases/{id}` | **Ne.** Dokument odkazuje jen na Case API v úvodu. `predani-wonderful.md` to uvádí. |
| Údaje o klientovi vč. podepisujících | Case API `GET /clients` | **Ne** a s dírou: **neexistuje `GET /clients/{client_id}`** (v API Gateway `/clients/{client_id}` nemá žádnou metodu, handler ji nemá). Z případu se dá zjistit jen `client_id`; filtr `GET /clients` umí `ico`, `name`, `status`, ne `client_id`. Wonderful musí projít všechny klienty (21 v tabulce) a hledat podle `client_id`, nebo znát IČO. |
| Podepisující osoby a oprávnění | Case API `signatories[]` | Reálná data mají `{name, function}`, bez `authorized`, který OpenAPI case-clientu uvádí (nahlédl jsem do `wonderfulkb-uw-clients` pro `SYN-A01`). Srovnání s podpisy v dokumentu by stejně nebylo možné (role podpisu ≠ jméno osoby). |
| Obsah, štítek, podpisy | Agent API | **Ano**, podrobně (včetně pastí). |
| Klíče a které platí kde | `predani-wonderful.md` | Dokument pro Wonderful mluví jen o jednom `x-api-key`; dva klíče a různé adresy uvádí jen předávací list. |

Odpověď na otázku „postaví agent všechno na třech voláních?": **ne.** Tři volání Agent API (detail, vektory, podpisy) pokrývají jen obsah dokumentů. K tomu agent potřebuje čtvrté volání (seznam z Agent API nebo z ingestu) a nezávislé volání Case & Client API pro případ a klienta. Pro pravidla, která mají srovnat podepsané osoby s oprávněnými podepisujícími, neexistuje žádný datový most: Agent API vrací roli (`borrower`, `guarantor`…), ne jméno, a Case API vrací jména a funkce.

## 7. Co je ověřeno a co ne

**Ověřeno (vlastní spuštění nebo čtení, ne věta z README):**
- 255 testů prošlo v čistých venv, součty a rozdíly proti README viz kap. 2.
- Kontraktový test mocku prošel před úpravou spec (120 odpovědí) a neprojde po ní (3 FAIL).
- Tabulka, sloupce, tag, indexy S3 Vectors (1024, cosine, ENHANCED), reálné klíče a metadata vektorů, S3 klíče analysis (`text.txt`, `pages/`, `signatures.json`, `signatures/<id>.png`, `run.json`, `vision/`).
- API handler (pracovní kopie) nad 23 reálnými řádky: validní odpovědi všech pěti variant volání (kromě 409 s jiným schématem).
- Nasazená Lambda: existence, runtime, role, IAM politika, tagy, proměnné prostředí (hodnota secretu není v nich), rozdíl balíčku proti pracovní kopii. Veřejné HTTP: `/v1/healthz` → 403, `/healthz` → 404, `/v1/cases/17794315-26/documents` bez klíče → 403.
- Žádný S3 trigger ani EventBridge pravidlo, které by po nahrání spustilo pipeline.
- Dvě API Gateway klíče a usage plán case-clientu (jen metadata), absence `GET /clients/{id}`.
- Žádné tajemství v repozitáři (regulární výrazy), žádný klíč ve zdrojích a README.

**Neověřeno nebo ověřeno jen z čtení kódu:**
- **Nasazená Lambda se nevolala s platným klíčem** (secret jsem nečetl). Že ingest klíč projde na Agent API a ne na Case API, vím z `predani-wonderful.md` a `dataset/README.md`, ne ze svého volání.
- **Chování nasazené verze** vím z rozdílu balíčku, ne z odpovědi. Že vrací `signatures: []` pro řádek bez `signatures_s3_key`, jsem ověřil spuštěním stejného (starého) kódu lokálně nad reálnými daty.
- **Živé volání Bedrocku** (classify, vize, embed): nevolal jsem, tedy neověřeno, jak se model chová na vložených instrukcích; závěry v kap. 5.3 jsou z kódu.
- **`wonderfulkb/be-document-processing`** (testy, Textract detektor): kód jsem četl, testy nespouštěl (viz kap. 2). Souběh s `signatures/` jen z kódu.
- **`ref-agent/`**: neauditováno (vznikl při auditu).
- **`privacy/`** testy prošly, ale KMS neexistuje, nic není napojené. Zda se čitelné výřezy opravdu předají Wonderful (a zda to smí), je rozhodnutí uživatele.
- **Přesnost detekce podpisů, rolí a klasifikace**: neměřil jsem. Čísla v `predani-wonderful.md` (92 % úplnost generických, 59 % rukopis, 78 % rolí, z toho 15 % špatně) pochází z `eval/` a `signatures/`, nepřepočítal jsem je.
- **Souběh a výkon**: studený start, doba odezvy, limit odpovědi 6 MB (odpověď s hodnotami vektorů čtyřstránkové smlouvy měla 251 kB, VOP s více než 100 částmi tedy bude řádově MB), sdílený limit Bedrocku mezi třemi nezávislými omezovači (30 + 30 + 20 požadavků/min na proces).
- **Že nasazení bylo schváleno uživatelem**: stack existuje od 15:44 UTC, `deploy.sh` žádá potvrzení, ale storage kontrakt zakazuje nasazování bez souhlasu a z AWS to nepoznám. Pokud nasazení schváleno nebylo, patří to do první řady nálezů.
