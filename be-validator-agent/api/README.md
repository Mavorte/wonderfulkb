# Validator Agent API (skutečná implementace)

Čtecí API pro Wonderful validační agenta podle [openapi-validator-agent.yaml](../../../be-document-processing/contracts/openapi-validator-agent.yaml)
a datového kontraktu [validator-agent-storage.md](../../../be-validator-agent/docs/validator-agent-storage.md). Čte DynamoDB
`wonderfulkb-uw-document-analysis`, S3 `wonderfulkb-raw-document-storage` (`cases/<case>/analysis/<doc>/…`) a S3 Vectors
`wonderfulkb-vectors`. **Nasazeno 19. 10. 2026** (viz sekce „Nasazeno“ dole), první verze.

| Soubor | Co |
|---|---|
| `core.py` | `handle(method, path, query, headers) -> (status, body)`: směrování, autentizace, čtení z úložišť |
| `app.py` | Lambda adaptér (API Gateway HTTP API 2.0 i REST proxy 1.0), handler `app.handler` |
| `server.py` | lokální HTTP server (cesty `/v1/…`, `/healthz`) |
| `fixtures.py`, `fakes.py` | moto (DynamoDB, S3, Secrets Manager) + fake S3 Vectors; data z `validator-agent-mock/seed.py` |
| `contract_test.py` | kontraktový test (převzatý z mocku): proti mocku, proti fixturám i proti běžícímu API |
| `test_api.py`, `test_contract.py` | pytest: autentizace, chyby, stránkování, filtry vektorů, dávkování, podpisy |
| `live_smoke.py` | živý test proti skutečným úložištím; zapisuje a maže vlastní case `wonderfulkb-apitest-*` |
| `template.yaml` | SAM: Lambda `wonderfulkb-agent-api` + HTTP API stage `v1`, vlastní IAM role jen pro čtení |
| `deploy.sh`, `verify_deployed.py` | nasazení s výpisem a potvrzením (nespuštěno) a ověření nasazeného API |

## Spuštění
Python 3.14, bez PyMuPDF. Závislosti: `pip install -r requirements-dev.txt`.

```bash
FIXTURES=1 API_KEY=mock-key python3 server.py       # lokálně nad fixturami, :8080/v1 (+ /v1/_mock/cases jako mock)
AWS_PROFILE=hackathon python3 server.py             # lokálně nad skutečnými AWS; klíč ze Secrets Manageru
curl -H 'x-api-key: mock-key' localhost:8080/v1/_mock/cases
```

## Testy
```bash
python3 -m pytest -q                                              # 18 testů + kontraktový test nad fixturami (~20 s)
FIXTURES=1 python3 contract_test.py                               # jen kontraktový test, 48 kontrol + 120 odpovědí proti schématům
BASE_URL=http://localhost:8080/v1 API_KEY=mock-key python3 contract_test.py   # proti mocku nebo běžícímu serveru
AWS_PROFILE=hackathon AWS_REGION=eu-central-1 python3 live_smoke.py           # živé úložiště, vlastní testovací data
```
Test a fixtury načítají texty z `docs/vzorove-dokumenty/text` přes `validator-agent-mock/seed.py` (mock se jen čte).

## Chování
- **Autentizace:** `x-api-key` proti hodnotě ze Secrets Manageru `wonderfulkb/ingest-api-key` (čtení při prvním požadavku, cache 5 min), `hmac.compare_digest`. Klíč se nevypisuje, neloguje a není v odpovědích; selhání čtení secretu dá `500` bez detailů. `API_KEY` v prostředí je jen pro lokální vývoj a testy (v šabloně se nenastavuje). `/healthz` je bez klíče. Jiná metoda než GET je `405`.
- **Seznam (`listCaseDocuments`)**, doplněný navíc ke třem voláním ze zadání, protože je ve spec a mock ho má: Query podle `case_id`, `next_token` = base64 posledního `document_id`, filtr `processing_status` s doplňováním stránek. `404`, když case nemá žádný řádek (a nepovolíš-li parametr `CasesTable`, ani případ bez zpracovaných dokumentů nejde odlišit od neexistujícího; viz Nasazení).
- **Dokument:** řádek tabulky + `text.txt`. `404` bez řádku, `409` s `processing_status` pro vše mimo `completed`/`partial`. `pages_failed` (NS) jen u `partial`. `label`/`label_status` jsou `null`, dokud není štítek.
- **Vektory:** klíče se odvozují z kontraktu (`<document_id>#t<i>`, `#p<strana>`) a čtou se `get_vectors` po 100 (`list_vectors` neumí prefix; text se čte po blocích, dokud blok není neúplný, strany podle `page_count`). `include`, `include_values=false` (S3 Vectors se pak ptá bez dat). `similar_to_verified=N`: `query_vectors` nad `wonderfulkb-text` (s `include=image` nad obrazem; bez textu nad obrazem) s dotazem = těžiště vektorů dokumentu, `topK=100`, filtr `verified = true` a `document_id != vlastní`; části se spojí na dokument (nejlepší část), `score = 1 − kosinová vzdálenost` ořezané na 0 až 1. Nezpracovaný dokument nebo dokument bez vektorů dává `200` a prázdná pole.
- **Podpisy:** odpověď má povinné `status`: `completed` (soubor existuje a je čitelný; prázdné `signatures` pak znamená „nic nenalezeno“), `not_run` (dokument není zpracovaný nebo `signatures.json` neexistuje; prázdné pole NENÍ nález) a `failed` (existuje, ale je poškozený, má špatný tvar nebo nese `status: failed` / `error`). Klíč souboru je atribut `signatures_s3_key`, jinak konvenční `cases/<case_id>/analysis/<document_id>/signatures.json`; existence se zjišťuje `ListObjectsV2`. `signatures.json` se vrací tak, jak ho zapsala pipeline, plus `crop_url` (předpodepsaný GET na `…/signatures/<signature_id>.png`, 300 s, regionální endpoint, SigV4). `include_vectors` (výchozí true): chybí-li `vector` v souboru, dočte se z indexu `wonderfulkb-signatures`; s `false` se `vector` odstraní. `match_client=true`: `similar_signatures` z indexu (3 nejbližší, jiný dokument). 

## Předpoklady nad rámec kontraktu (potvrdit s ostatními sessions)
1. **Klíč vektoru podpisu** je `<document_id>#s<n>` jako v `embed.write_signature_vectors` (n od 0 podle pořadí výřezů): `n` = číslo ze `signature_id` mínus 1 (`sig_01` → `#s0`), jinak pořadí v souboru. `signature_id` u `similar_signatures` se z klíče skládá zpět (`#s0` → `sig_01`), protože ho `embed` do metadat nezapisuje. Metadata podpisu mají obsahovat `case_id` a `document_id` (zapisuje `embed`).
2. **„Podpisy téhož klienta"** se v indexu poznají jen přes `case_id` (klient v metadatech vektoru není). Pokud má mít shoda zahrnout víc případů klienta, musí do metadat přibýt `client_id`.
3. **`copy_suspicion` a `phash` API nepočítá**: bere je ze `signatures.json`. Chybí-li `copy_suspicion`, pole se nevymýšlí (agent nesmí číst „none" jako ověřené).
4. Pole `crop_s3_key` v podpisu je volitelné (jinak `<prefix>/signatures/<signature_id>.png`) a v odpovědi se neobjeví.
5. Existenci výřezu API nekontroluje (`crop_url` u neexistujícího objektu dá člověku `404` od S3). Předpodepsaná adresa vyprší nejpozději s přihlašovacími údaji role Lambdy.

## Co je ověřeno a co ne
**Ověřeno**
- Kontraktový test (včetně `status` podpisů) a `pytest` (22 testů) zelené nad fixturami (moto + fake S3 Vectors). Proti mocku už skript neprojde: spec teď vyžaduje `status` u volání 3, který mock nevrací.
- **Živé AWS (19. 10. 2026, `live_smoke.py`, vše zelené, testovací data smazána):** skutečný S3 Vectors přijal moje `get_vectors`, `query_vectors` s filtrem `$and`/`$eq`/`$ne` a vrátil `distance`; neighbors (vyloučení vlastního dokumentu, jen `verified`), `similar_signatures`, dočtení `vector`, předpodepsaná adresa, UTF-8 text z S3, `403`/`404`. API klíč ze skutečného secretu se použil pro autentizaci a nikam se nevypsal.
- Čtení řádků zapsaných pipeline (case `17794315-26`, 3 dokumenty, `completed`): dokument i text se vrací, `vectors` a `signatures` zatím prázdné pole (pipeline je ještě nezapsala).

**Neověřeno**
- Nasazená Lambda a API Gateway (šablona prošla `cfn-lint` a `sam validate --lint`, `sam build` zabalí kód s `boto3>=1.40`; vlastní nasazení, běh na runtime `python3.14` v AWS a `deploy.sh` nezkoušeny).
- Čtení skutečných vektorů a `signatures.json` od pipeline (v čase testu v indexech nic nebylo); shoda tvaru s `embed/` a `Signature pipeline` stojí na kontraktu a bodech 1 až 3 výše.
- Výkon s mnoha chunky (text se čte po 100 klíčích, dotaz `topK=100`), Lambda cold start, limit odpovědi 6 MB u velmi dlouhých textů.

## Nasazení: checklist
Nasazení schvaluje uživatel. Provedeno 19. 10. 2026 po jeho potvrzení v chatu; checklist platí pro další nasazení.

**Před nasazením**
1. `aws sso login --profile hackathon`; `pip install aws-sam-cli` (SAM CLI), Python 3.14 na PATH (`sam build` ho potřebuje pro runtime `python3.14`).
2. Souhlas uživatele (sdílený účet <ACCOUNT_ID>, `eu-central-1`).
3. `./deploy.sh --plan`: ověří účet, existenci tabulky, bucketu, tří indexů a secretu a vypíše, co se vytvoří. Pak `./deploy.sh`: totéž a čeká na zadání slova `deploy`; `sam deploy` ještě ukáže changeset a zeptá se znovu.

**Parametry** (`sam deploy --parameter-overrides`, výchozí hodnoty jsou správné)
| Parametr | Výchozí | Poznámka |
|---|---|---|
| `AnalysisTable` | `wonderfulkb-uw-document-analysis` | |
| `RawBucket` | `wonderfulkb-raw-document-storage` | čte se jen `cases/*/analysis/*` |
| `VectorBucket` | `wonderfulkb-vectors` | indexy `wonderfulkb-text`, `-image`, `-signatures` |
| `ApiKeySecretName` | `wonderfulkb/ingest-api-key` | |
| `CasesTable` | prázdný | `wonderfulkb-uw-cases` přidá oprávnění `GetItem` a odliší prázdný case (200 `[]`) od neexistujícího (404). Zapni (`CASES_TABLE=wonderfulkb-uw-cases ./deploy.sh`), pokud agent volá seznam dřív, než pipeline zapíše první řádek |
Proměnná `ARTIFACT_BUCKET` pro `deploy.sh` použije existující bucket na balíček; jinak SAM založí spravovaný stack `aws-sam-cli-managed-default` (nový bucket ve sdíleném účtu).

**API klíč:** nenasazuje se a nikam se nekopíruje. Lambda ho čte za běhu ze Secrets Manageru `wonderfulkb/ingest-api-key` (stejný klíč jako Ingest API) a cachuje 5 minut; změna secretu se projeví do 5 minut. Wonderful dostane klíč stejnou cestou jako u ingestu, ne z tohoto repozitáře. Role má jen `GetSecretValue` na tento secret; klíč v prostředí funkce není.

**Ověření po nasazení** (`ApiUrl` je ve výstupu stacku):
```bash
AWS_PROFILE=hackathon python3 verify_deployed.py <ApiUrl> <case_id> [<document_id>]
```
Skript načte klíč ze Secrets Manageru bez výpisu a zavolá `healthz`, špatný klíč (403), seznam, tři volání (dokument, vektory s `include_values=false&similar_to_verified=3`, podpisy s `match_client=true&include_vectors=false`) a neexistující dokument (404). Prázdná pole u vektorů a podpisů jsou platná odpověď, dokud je pipeline nezapíše. Při chybě `500` zkontrolovat `/aws/lambda/wonderfulkb-agent-api` (log neobsahuje klíč ani hlavičky).

**Návrat zpět**
- Stack obsahuje jen vlastní zdroje: `aws cloudformation delete-stack --stack-name wonderfulkb-agent-api` je odstraní (Lambda, role, log skupina, API); data a indexy se nedotknou. Spravovaný bucket SAM `aws-sam-cli-managed-default` zůstává (sdílený mezi SAM nasazeními; mazat jen na pokyn uživatele).
- Chybná aktualizace se vrací CloudFormation automaticky; při pozdějším problému nasadit předchozí verzi kódu znovu (`git`/záloha adresáře `api/` a `./deploy.sh`).

**Odhad nákladů** (orientační, z paměti ceníku, neověřeno proti aktuálnímu ceníku; pro hackathonový provoz do desítek tisíc volání za den):
HTTP API řádově 1 USD za milion požadavků; Lambda arm64 512 MB při ~100 ms kolem 0,7 USD za milion volání; S3 Vectors dotazy řádově 2,5 USD za milion (při tisících vektorů zanedbatelné); Secrets Manager čtení 0,05 USD za 10 tisíc volání (cache ⇒ jednotky volání za hodinu); CloudWatch logy kolem 0,6 USD/GB. Dohromady centy za den; žádná trvalá položka kromě log skupiny (14 dní) a malého balíčku v S3.

## Kontrola šablony a IAM (19. 10. 2026)
`cfn-lint template.yaml` bez nálezů, `sam validate --lint` platná, `sam build` projde (28 MB s boto3).

| Oprávnění role `wonderfulkb-agent-api-lambda` | Rozsah | Vyhodnocení |
|---|---|---|
| `dynamodb:GetItem`, `Query` | jen tabulka `wonderfulkb-uw-document-analysis` (bez indexů, bez zápisu, bez Scan) | v pořádku |
| `dynamodb:GetItem` | `CasesTable`, jen když je parametr vyplněný (výchozí ne) | volitelné; výchozí je nejmenší oprávnění |
| `s3:GetObject` | `wonderfulkb-raw-document-storage/cases/*/analysis/*` (originály `original/` a zip nejsou čitelné) | v pořádku |
| `s3:ListBucket` | bucket, jen s `s3:prefix` = `cases/*/analysis/*`; slouží k rozlišení chybějícího `signatures.json` (`not_run`) od zamítnutí | v pořádku, vypíše se jen předpona `analysis` |
| `s3vectors:GetVectors`, `QueryVectors` | tři konkrétní indexy v `wonderfulkb-vectors` (ne `index/*`, bez `ListVectors`, `PutVectors`, `DeleteVectors`) | v pořádku; `GetVectors` je nutné i pro dotaz s metadaty |
| `secretsmanager:GetSecretValue` | `wonderfulkb/ingest-api-key-??????` (přesně 6 znaků suffixu, jiný secret s tímto prefixem nepasuje) | v pořádku; secret je šifrován výchozím klíčem `aws/secretsmanager`, `kms:Decrypt` netřeba |
| `logs:CreateLogStream`, `PutLogEvents` | jen vlastní log skupina | v pořádku, nepoužívá se `AWSLambdaBasicExecutionRole` (ta dává `logs:*` na `*`) |
Zbylá rizika: API Gateway nemá vlastní autorizaci, klíč se kontroluje v Lambdě (limit 10 req/s chrání jen proti zahlcení); `crop_url` jsou předpodepsané adresy s platností 300 s vázané na dočasné údaje role.

## Nasazeno (19. 10. 2026)
- **Base URL:** `<AGENT_API_BASE_URL>` (klíč `x-api-key` stejný jako u Ingest API, v Secrets Manageru `wonderfulkb/ingest-api-key`; nikdy se nezapisuje do repozitáře).
- **Stack** `wonderfulkb-agent-api` (eu-central-1, účet <ACCOUNT_ID>, tag `project=wonderfulkb`): Lambda `wonderfulkb-agent-api` (python3.14, arm64, 512 MB), role `wonderfulkb-agent-api-lambda`, log skupina `/aws/lambda/wonderfulkb-agent-api` (14 dní), HTTP API `<AGENT_HTTP_API_ID>` se stage `v1` a trasami `GET /{proxy+}`, `GET /healthz`. SAM navíc založil spravovaný stack `aws-sam-cli-managed-default` (bucket s balíčkem kódu).
- **Klíč:** v prostředí Lambdy je jen název secretu (`API_KEY_SECRET`), proměnná `API_KEY` neexistuje; funkce klíč čte za běhu ze Secrets Manageru (správný klíč vrací 200, špatný 403). V logu Lambdy (92 událostí) se hodnota klíče nevyskytuje.
- **Odinstalace:** `aws cloudformation delete-stack --stack-name wonderfulkb-agent-api --profile hackathon --region eu-central-1` odstraní Lambdu, roli, log skupinu a API. Data, tabulky a indexy se nedotknou. Bucket stacku `aws-sam-cli-managed-default` zůstane (smazat jen na pokyn uživatele; musí se předtím vyprázdnit).
- **Opravy při nasazení:** `deploy.sh` selhal před vytvořením čehokoli na prázdném `--parameter-overrides` (opraveno); `/v1/healthz` přes API Gateway vracel 403, protože se prefix stage odřezával až po kontrole cesty (opraveno, nasazeno druhou aktualizací stacku, test přidán).

**Ověřeno na živém API** (`verify_deployed.py`, dokumenty `17794315-26/a15b15f8…`, `pipeline-sample-solom-rec/50b0d089…`, `pipeline-sample-unhappy/ebb28695…`): healthz 200, špatný klíč 403, seznam 200, volání 1 (štítek a celý text), volání 2 a 3 jako 200, neexistující dokument 404. U `17794315-26` vrací volání 2 text=7, obraz=4 vektorů.

**Na živém API neověřeno**
- `409`: v tabulce jsou jen `completed` dokumenty; kontraktový test ho kryje jen nad fixturami.
- `partial` / `pages_failed`, `label_status: verified`, `confidence` (na živých řádcích zatím `null`).
- `neighbors` s neprázdným výsledkem (v indexech zatím není žádný vektor s `verified=true`; živý smoke test ho ověřil na vlastních dočasných datech).
- Podpisy: řádky z pipeline nemají atribut `signatures_s3_key`; API proto bere konvenční klíč `…/signatures.json` (oprava z předávací kontroly). Na živém API ověřeno (po druhé aktualizaci stacku): `17794315-26/a15b15f8…` dává `status: completed` a 2 podpisy (`sig_01` borrower, `sig_02` provider) s předpodepsaným `crop_url` na 300 s, dokumenty bez souboru dávají `not_run`, soubor s 0 nálezy `completed` s prázdným polem. Hodnotu `failed` kryjí jen testy (živý poškozený soubor nebyl). `copy_suspicion` a `similar_signatures` na živých datech nezkoušeny.
- Vektory dokumentů `pipeline-sample-*` jsou zatím prázdné (pipeline je nezapsala).
- Volání 3 se ještě změní (šifrované výřezy, `reveal_path`); toto je první verze.
