# Validator Agent API (skutečná implementace)

Čtecí API pro Wonderful validační agenta podle [openapi-validator-agent.yaml](../../../be-document-processing/contracts/openapi-validator-agent.yaml)
a datového kontraktu [validator-agent-storage.md](../../../be-validator-agent/docs/validator-agent-storage.md). Čte DynamoDB
`wonderfulkb-uw-document-analysis`, S3 `wonderfulkb-raw-document-storage` (`cases/<case>/analysis/<doc>/…`) a S3 Vectors
`wonderfulkb-vectors`. **Nasazeno 19. 10. 2026** (viz sekce „Nasazeno“ dole), první verze.

| Soubor | Co |
|---|---|
| `core.py` | `handle(method, path, query, headers) -> (status, body)`: směrování, autentizace, čtení z úložišť, odkrytí podpisu a audit |
| `crop_reveal.py` | jen dešifrování výřezu (KMS Decrypt + AES-256-GCM, formát `WKBS` v1 z `privacy/`); bez Pillow, numpy a PyMuPDF |
| `app.py` | Lambda adaptér (API Gateway HTTP API 2.0 i REST proxy 1.0), handler `app.handler`; binární odpověď jako base64 |
| `server.py` | lokální HTTP server (cesty `/v1/…`, `/healthz`) |
| `fixtures.py`, `fakes.py` | moto (DynamoDB, S3, Secrets Manager) + fake S3 Vectors; data z `validator-agent-mock/seed.py` |
| `contract_test.py` | kontraktový test (převzatý z mocku): proti mocku, proti fixturám i proti běžícímu API |
| `test_api.py`, `test_contract.py` | pytest: autentizace, chyby, stránkování, filtry vektorů, dávkování, podpisy |
| `test_reveal.py` | pytest: `preview_url`/`reveal_path`/`crop_available`, odkrytí, špatný kontext, starý čitelný výřez, `crop_source`, audit, KMS (mock) |
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
python3 -m pytest -q                                              # test_api + test_reveal + kontraktový test nad fixturami
FIXTURES=1 python3 contract_test.py                               # jen kontraktový test (včetně odkrytí podpisu) + odpovědi proti schématům
BASE_URL=http://localhost:8080/v1 API_KEY=mock-key python3 contract_test.py   # proti mocku nebo běžícímu serveru
AWS_PROFILE=hackathon AWS_REGION=eu-central-1 python3 live_smoke.py           # živé úložiště, vlastní testovací data
```
Test a fixtury načítají texty z `docs/vzorove-dokumenty/text` přes `validator-agent-mock/seed.py` (mock se jen čte).
Fixtury zapisují výřezy tak, jak je zapisuje signature pipeline: `<sig>.png.enc` (šifrováno knihovnou `privacy/signature_privacy`
a `LocalKeyProvider` s klíčem jen v paměti) a `<sig>.preview.png`; proto `requirements-dev.txt` obsahuje `cryptography`, Pillow a numpy.
Lambda potřebuje jen `cryptography` (`requirements.txt`).

## Chování
- **Autentizace:** `x-api-key` proti hodnotě ze Secrets Manageru `wonderfulkb/ingest-api-key` (čtení při prvním požadavku, cache 5 min), `hmac.compare_digest`. Chybějící (nebo prázdná) hlavička `x-api-key` = `401` `{"error": "Chybí API klíč"}`, špatný klíč = `403` `{"error": "Špatný API klíč"}` (sjednoceno s ingestem, audit S7; HTTP API nemá vlastní autorizaci, oba kódy vrací Lambda). Klíč se nevypisuje, neloguje a není v odpovědích; selhání čtení secretu dá `500` bez detailů. `API_KEY` v prostředí je jen pro lokální vývoj a testy (v šabloně se nenastavuje). `/healthz` je bez klíče. Jiná metoda než GET je `405`.
- **Seznam (`listCaseDocuments`)**, doplněný navíc ke třem voláním ze zadání, protože je ve spec a mock ho má: Query podle `case_id`, `next_token` = base64 posledního `document_id`, filtr `processing_status` s doplňováním stránek. `404`, když case nemá žádný řádek (a nepovolíš-li parametr `CasesTable`, ani případ bez zpracovaných dokumentů nejde odlišit od neexistujícího; viz Nasazení).
- **Dokument:** řádek tabulky + `text.txt`. `404` bez řádku, `409` s `processing_status` pro vše mimo `completed`/`partial`. `pages_failed` (NS) jen u `partial`. `label`/`label_status` jsou `null`, dokud není štítek.
- **Vektory:** klíče se odvozují z kontraktu (`<document_id>#t<i>`, `#p<strana>`) a čtou se `get_vectors` po 100 (`list_vectors` neumí prefix; text se čte po blocích, dokud blok není neúplný, strany podle `page_count`). `include`, `include_values=false` (S3 Vectors se pak ptá bez dat). `similar_to_verified=N`: `query_vectors` nad `wonderfulkb-text` (s `include=image` nad obrazem; bez textu nad obrazem) s dotazem = těžiště vektorů dokumentu, `topK=100`, filtr `verified = true` a `document_id != vlastní`; části se spojí na dokument (nejlepší část), `score = 1 − kosinová vzdálenost` ořezané na 0 až 1. Nezpracovaný dokument nebo dokument bez vektorů dává `200` a prázdná pole.
- **Podpisy:** odpověď má povinné `status`: `completed` (soubor existuje a je čitelný; prázdné `signatures` pak znamená „nic nenalezeno“), `not_run` (dokument není zpracovaný nebo `signatures.json` neexistuje; prázdné pole NENÍ nález) a `failed` (existuje, ale je poškozený, má špatný tvar nebo nese `status: failed` / `error`). Klíč souboru je atribut `signatures_s3_key`, jinak konvenční `cases/<case_id>/analysis/<document_id>/signatures.json`; existence se zjišťuje `ListObjectsV2`. `signatures.json` se vrací tak, jak ho zapsala pipeline, plus pole výřezu popsaná níže (**`crop_url` na čitelný výřez už neexistuje**). `include_vectors` (výchozí true): chybí-li `vector` v souboru, dočte se z indexu `wonderfulkb-signatures`; s `false` se `vector` odstraní. `match_client=true`: `similar_signatures` z indexu (3 nejbližší, jiný dokument). 

## Podpisy: náhled a odkrytí (krok 3, nasazeno 19. 10. 2026)
Čitelný podpis se neukládá. Výřez leží v S3 šifrovaný (`signatures/<sig>.png.enc`, AES-256-GCM, datový klíč obalený KMS
`alias/wonderfulkb-signatures`, kontext = `case_id`, `document_id`, `signature_id`) a vedle něj zkreslený náhled
(`signatures/<sig>.preview.png`). Rozhodnutí a návrh: [validator-agent-privacy.md](../../../be-validator-agent/docs/validator-agent-privacy.md).

**Volání 3 (`getDocumentSignatures`)** vrací u každého podpisu místo `crop_url`:
| Pole | Význam |
|---|---|
| `preview_url` | předpodepsaný GET (300 s) na zkreslený `<sig>.preview.png` (`preview_s3_key`, jinak podle názvu); nečitelný, lze ukázat bez odkrytí; `null`, pokud objekt neexistuje |
| `reveal_path` | relativní cesta endpointu odkrytí `/cases/{case_id}/documents/{document_id}/signatures/{signature_id}/image` |
| `crop_available` | `true`, když existuje šifrovaný výřez; `false` u chybějícího nebo ještě nezmigrovaného (čitelného) výřezu |

Interní pole `signatures.json` (`crop_s3_key`, `crop_encrypted`, `preview_s3_key`, `crop_source`) se z odpovědi odstraňují. Existence
výřezů a náhledů se zjistí jedním `ListObjectsV2` nad `…/signatures/` (ne voláním na každý podpis). Klíč objektu mimo `…/signatures/`
téhož dokumentu se ignoruje.

**Starší `signatures.json` bez `crop_s3_key`/`crop_encrypted`** (čitelné výřezy čekající na migraci): čitelný odkaz se nevrací,
`crop_available: false`, `preview_url` jen když náhled existuje. Šifrovaný výřez se pozná podle `crop_encrypted: true`, přípony `.enc`,
nebo existence `<sig>.png.enc`.

**Odkrytí (`GET …/signatures/{signature_id}/image`)**: dešifruje `crop_s3_key` (bez něj `<sig>.png.enc`). KMS `Decrypt` s `KeyId`
(`PRIVACY_KMS_KEY_ID`, výchozí alias) a `EncryptionContext` z **cesty požadavku**; má-li podpis v `signatures.json` `crop_source`
(`{case_id, document_id, signature_id}`: výřez zašifrovaný pod jiným podpisem, např. po přesunu nebo migraci), použije se ten jako kontext
dešifrování. `crop_source` mění jen kontext, nikdy klíč objektu (ten musí ležet pod `cases/<case>/analysis/<doc>/signatures/` téhož
dokumentu). Odpověď `200 image/png`, `Cache-Control: no-store`, `Pragma: no-cache`, `Content-Disposition: inline`, `X-Content-Type-Options: nosniff`.
| Stav | Kdy |
|---|---|
| `404` | dokument není nebo není zpracovaný; `signatures.json` neexistuje; podpis tam není; výřez v S3 chybí |
| `409` | výřez není šifrovaný (starý čitelný objekt, nebo objekt bez hlavičky `WKBS`); **nikdy se nevrací čitelně** |
| `500` obecná zpráva | blok nejde dešifrovat (jiný kontext, zamítnutí KMS, poškozený blok), neplatný `crop_source`/`signatures.json`; důvod jen v auditu (`denied`/`error`) |
| `401` / `403` | chybí API klíč (`401`) / špatný API klíč (`403`), jako všude a jako ingest; neauditováno jako odkrytí |

**Audit.** Každé volání s platným klíčem zapíše jeden JSON řádek (logger `wonderfulkb.agent_api.audit`, úroveň INFO nastavená v kódu, aby
prošel i v Lambdě) do `/aws/lambda/wonderfulkb-agent-api`:
`{"event":"signature_reveal","caller":"…","ts":"…Z","case_id":"…","document_id":"…","signature_id":"…","outcome":"revealed|not_found|not_encrypted|denied|error","request_id":"…"}`.
`caller` = `apiKeyId` z API Gateway (jen REST API s usage plan), jinak otisk klíče `fp:` + prvních 12 hex znaků SHA-256; hodnota klíče ani obrázek
se nelogují (hlídá test). Při jednom sdíleném klíči je `caller` stále týž otisk; pro rozlišení lidí je třeba víc klíčů (viz privacy doc, část 5).
Druhá stopa: CloudTrail zapisuje každé KMS `Decrypt` i s kontextem.

**Konfigurace** (env Lambdy, v šabloně parametry):
| Proměnná | Výchozí | Význam |
|---|---|---|
| `PRIVACY_KMS_KEY_ID` | `alias/wonderfulkb-signatures` | klíč pro `Decrypt` (alias nebo ARN) |
| `LEGACY_PLAIN_CROP_URL` | `true` (**dočasně**, viz níže) | `true` = nezmigrovaný čitelný výřez dostane `crop_url` (300 s). Jen přechod/nouze: obchází rozhodnutí o neukládání čitelných podpisů. Šifrovaný výřez čitelný odkaz nedostane nikdy |
| `CROP_URL_COMPAT` | `false` | `true` = klíč `crop_url` zůstane v odpovědi, vždy `null` (pro klienty, kteří hodnotu čtou bez kontroly klíče) |

**Přechod z `crop_url`** (změna je nekompatibilní; Wonderful pole zatím čte). Doporučení: (1) nasadit s `CropUrlCompat=true`: odpověď má `crop_url: null`
vedle `preview_url`/`reveal_path`, starý kód nespadne na chybějícím klíči, jen nedostane obrázek; (2) Wonderful přepne zobrazení na `preview_url`
a tlačítko „odkrýt“ na `reveal_path` (volá se s `x-api-key`, odpověď je PNG); (3) po potvrzení Wonderful `CropUrlCompat=false` (stack update bez dalšího kódu).
Čitelný `crop_url` se v žádné fázi nevrací, takže „krátké období s oběma poli“ znamená `null` + nová pole, ne čitelný odkaz. `LEGACY_PLAIN_CROP_URL=true`
jen na výslovné rozhodnutí, dokud migrace (privacy doc, část 8) neproběhne.

**Dočasně nasazeno s `LEGACY_PLAIN_CROP_URL=true`** (rozhodnutí uživatele k auditu V3, 19. 10. 2026; parametr `LegacyPlainCropUrl`,
výchozí v `template.yaml` i `deploy.sh`): starší případy se čitelnými `sig_NN.png` v S3 (např. `SYN-A01`) dál vracejí `crop_url`
(300 s), nové šifrované výřezy (`.png.enc`) jen `preview_url` + `reveal_path` (`/image`). Bucket ani existující objekty se neměnily.
**Platí jen do migrace** starých výřezů na šifrované; po ní nasadit s `LEGACY_PLAIN_CROP_URL=false ./deploy.sh` a výchozí hodnoty vrátit na `false`.

**IAM** (role `wonderfulkb-agent-api-lambda`): přibylo `kms:Decrypt` na klíč `<KMS_KEY_ID>` (`SignatureKmsKeyId`) s podmínkou `ForAllValues:StringEquals`
nad `kms:EncryptionContextKeys` = `case_id`, `document_id`, `signature_id` a `Null: false` (bez kontextu by `ForAllValues` vyšlo vždy pravdivě). Žádné `GenerateDataKey`,
`Encrypt`, `ReEncrypt`: šifrovat umí jen pipeline, odkrýt jen toto API. `s3:GetObject` se nemění: `cases/*/analysis/*` už pokrývá `…/signatures/*`
(šifrované výřezy i náhledy); víc než dosud tedy roli nepřibylo. Poznámka: stejné oprávnění čte i staré čitelné `…/signatures/<sig>.png`, dokud se nesmažou při migraci.

- **Duplicity napříč případy (volání 1):** `duplicate_of` (dokumenty v jiných případech se stejným SHA-256, bez vlastního případu) a `duplicate_relevant` (jen u individuálních dokladů podle `duplicate_policy` štítku a mimo šablony ve ≥ 3 případech). SHA-256 se čte z `wonderfulkb-uw-documents` (jen atribut), případy z indexu `wonderfulkb-uw-content-hashes` (`Query`); politika je snapshot `duplicate_policy.json` z `classify/taxonomy.yaml` (obnova: `python -I -m dedup.policy --write api/duplicate_policy.json` v `infra/validator-agent`). Chyba čtení indexu, tabulky dokumentů nebo politiky = pole se vynechají, odpověď zůstává 200. Prázdné `HASHES_TABLE` funkci vypne. Detaily: [../dedup/README.md](../dedup/README.md). **Nenasazeno**, nasazená Lambda o duplicitách neví.

## Předpoklady nad rámec kontraktu (potvrdit s ostatními sessions)
1. **Klíč vektoru podpisu** je `<document_id>#s<n>` jako v `embed.write_signature_vectors` (n od 0 podle pořadí výřezů): `n` = číslo ze `signature_id` mínus 1 (`sig_01` → `#s0`), jinak pořadí v souboru. `signature_id` u `similar_signatures` se z klíče skládá zpět (`#s0` → `sig_01`), protože ho `embed` do metadat nezapisuje. Metadata podpisu mají obsahovat `case_id` a `document_id` (zapisuje `embed`).
2. **„Podpisy téhož klienta"** se v indexu poznají jen přes `case_id` (klient v metadatech vektoru není). Pokud má mít shoda zahrnout víc případů klienta, musí do metadat přibýt `client_id`.
3. **`copy_suspicion` a `phash` API nepočítá**: bere je ze `signatures.json`. Chybí-li `copy_suspicion`, pole se nevymýšlí (agent nesmí číst „none" jako ověřené).
4. Pole `crop_s3_key`, `crop_encrypted`, `preview_s3_key`, `crop_source` v podpisu jsou volitelná (viz výše) a v odpovědi se neobjeví. Tvar `crop_source` (`{case_id, document_id, signature_id}`) jsem určil já;
   zapisují ho `v-redact-pipeline`/`v-redact-migrate`, shodu je třeba potvrdit.
5. `preview_url` se vydává jen pro existující náhled (kontrola jedním `ListObjectsV2`). Předpodepsaná adresa vyprší nejpozději s přihlašovacími údaji role Lambdy.
6. `crop_reveal.py` má vlastní kopii dešifrování (formát `WKBS` v1), protože `signature_privacy` vyžaduje Pillow a numpy. Při změně formátu v `privacy/blob.py` se musí změnit obě místa; shodu hlídá `test_reveal.py`.

## Co je ověřeno a co ne
**Ověřeno**
- Kontraktový test (včetně `status` podpisů, `preview_url`, `reveal_path`, odkrytí přes HTTP a chyb 403/404/400) a `pytest` (59 testů včetně kontraktového a odkrytí, 19. 10. 2026) zelené nad fixturami (moto + fake S3 Vectors). Kontraktový test mocku (`validator-agent-mock`) prochází se spec 0.3.0 (48 kontrol).
- **Odkrytí podpisu (jen testy, bez AWS):** šifrovaný výřez se odkryje a shoduje se zdrojovým PNG; špatný kontext (`case_id`, `document_id`, `signature_id`), jiný klíč a poškozený bajt selžou; blok zašifrovaný knihovnou `signature_privacy` (lokální provider i mock KMS v moto) odkryje `crop_reveal.py`; starý nezašifrovaný výřez dá `409` a čitelný odkaz ani obrázek se nevrátí (ani s `LEGACY_PLAIN_CROP_URL=false`, šifrovaný výřez čitelný odkaz nedostane ani při `true`); `crop_source` odkryje výřez zašifrovaný pod jiným podpisem a nerozšíří klíč objektu; audit se zapíše s `caller`, výsledkem a bez klíče i obrazu (porovnáno s textem logu); Lambda adaptér vrací base64 PNG s `no-store`.
- **Živé AWS (19. 10. 2026, `live_smoke.py`, vše zelené, testovací data smazána):** skutečný S3 Vectors přijal moje `get_vectors`, `query_vectors` s filtrem `$and`/`$eq`/`$ne` a vrátil `distance`; neighbors (vyloučení vlastního dokumentu, jen `verified`), `similar_signatures`, dočtení `vector`, předpodepsaná adresa, UTF-8 text z S3, `403`/`404`. API klíč ze skutečného secretu se použil pro autentizaci a nikam se nevypsal.
- Čtení řádků zapsaných pipeline (case `17794315-26`, 3 dokumenty, `completed`): dokument i text se vrací, `vectors` a `signatures` zatím prázdné pole (pipeline je ještě nezapsala).

**Neověřeno**
- **Živý KMS `Decrypt` z Lambdy**: nevyzkoušen (nic nenasazeno). Mock KMS v moto ověřuje kontext a `KeyId`, ale ne skutečné IAM podmínky (`ForAllValues`/`Null` nad `kms:EncryptionContextKeys`), ani to, že `Decrypt` s aliasem jako `KeyId` projde pod touto rolí. Po nasazení ověřit `verify_deployed.py` nebo ručně jedním odkrytím; při `AccessDenied` je v auditu `denied`.
- Alias `alias/wonderfulkb-signatures` míří na klíč `<KMS_KEY_ID>` (`deploy.sh --plan` to ověřuje čtením, `kms:DescribeKey`); šablona po změně prošla `cfn-lint` a `sam validate --lint`.
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
- Volání 3 se změnilo (krok 3, viz „Podpisy: náhled a odkrytí“), v AWS zatím nenasazeno; nasazená verze ještě vrací `crop_url`.
