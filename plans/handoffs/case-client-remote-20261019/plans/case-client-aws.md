# Plán: samostatná komponenta Case & Client API v AWS

Stav k 19. 10. 2026: pouze příprava a plán, bez implementace a bez nasazení.

## 1. Výchozí stav a ověření AWS

- Komponenta: `be-case-client/` přímo v kořeni repozitáře.
- Přesná kopie vstupního kontraktu: `be-case-client/openapi-case-client.yaml`, OpenAPI 3.0.3, verze `1.3.0-final`.
- Zdroj: `/Users/michal/Downloads/hackathon/openapi-case-client.yaml`.
- Repozitář zatím nemá aplikační kód, infrastrukturu ani stanovený jazyk/build systém.
- Ověřen AWS profil `ai-hackathon`, účet `609394381050`, region `eu-central-1` (odpovídá OpenAPI). SSO přihlášení bylo obnoveno.
- `describe-table` pro `wonderfulkb-uw-clients` i `wonderfulkb-uw-cases` vrátilo `ResourceNotFoundException`.
- `aws dynamodb list-tables --region eu-central-1 --profile ai-hackathon` vrátilo prázdný seznam. **V tomto účtu a regionu není vytvořena ani jedna tabulka.** Ostatní účty a regiony nebyly kontrolovány.
- Lokálně: AWS CLI 2.38.1, Docker CLI 28.3.2, Node.js 25.2.1, Python 3.9.6. SAM CLI není nainstalovaný; běh Docker daemonu nebyl ověřován.

Před budoucím deployem znovu ověřit tabulky. Pokud mezitím vzniknou, předat jejich názvy/ARN jako parametry a vyřešit vlastnictví; stack nesmí zkoušet vytvořit další tabulku stejného názvu.

## 2. Doporučená architektura

```text
HTTP klient + x-api-key
  → API Gateway REST API, stage v1
  → jedna Lambda wonderfulkb-case-client (on-demand)
      → wonderfulkb-uw-clients (čtení)
      → wonderfulkb-uw-cases (čtení a zakládání)
```

- **AWS SAM** pro infrastrukturu, build, lokální emulaci a nasazování přes CloudFormation. Pro malou samostatnou Lambdu poskytuje přímočarý vývojový cyklus.
- **Python 3.13**, standardní Lambda handler a `boto3`; závislosti explicitně verzovat a balit. Lokálně doplnit odpovídající Python. Výběr je návrh pro tento nový modul, nikoli existující standard repozitáře.
- **Lambda on-demand**, ZIP balíček, bez VPC: jednotlivé krátké API požadavky nepotřebují server ani trvale běžící instanci. Výchozí návrh: 256 MB RAM, timeout 10 s; upravit podle měření.
- **API Gateway REST API**, protože kontrakt požaduje nativní `x-api-key`, odpovědi 403 a throttling. HTTP API je jednodušší a levnější, ale nemá nativní API keys/usage plans; zde použít REST API.
- Testovací prostředí: jeden API klíč a usage plan, bez Cognito, vlastního authorizeru, vlastní domény či další bezpečnostní infrastruktury. API klíč je jednoduchá kontrola přístupu, nikoli uživatelská identita.
- Role Lambdy: logování, čtení klientské tabulky a jejího indexu, potřebné čtení/zápis cases a případná transakční kontrola klienta. Seed poběží samostatně pod vývojářským profilem.
- Proměnné prostředí: `CLIENTS_TABLE_NAME`, `CASES_TABLE_NAME`, volitelně `DYNAMODB_ENDPOINT_URL` pouze pro lokální databázi.
- AWS prostředky označit `project=wonderfulkb`. Logy do CloudWatch s krátkou retencí pro testování.

## 3. Datový model

### Klienti: wonderfulkb-uw-clients

- On-demand (`PAY_PER_REQUEST`), partition key `client_id` (String, UUID), bez sort key.
- GSI `ico-index`: partition key `ico` (String), projekce `ALL`.
- Povinné atributy: `client_id`, `ico`, `name`, `name_normalized`, `status`, `source`, `created_at`, `updated_at`.
- `ico`: přesně osm číslic; unikátnost zajišťuje seed skript. GSI sám unikátnost nevynucuje.
- `name_normalized`: odstranění diakritiky, malá písmena, odstranění právní formy a normalizace mezer. Stejná funkce pro seed i filtr názvu; právní formy odstraňovat jako celé výrazy, aby nepoškozovaly běžná slova.
- `status`: `active`, `inactive`, `blocked`; `source` vždy `synthetic`.
- Volitelné: `dic`, `legal_form`, `address`, seznamy map `contacts` a `signatories`, mapa `kyc` přesně podle zadání.
- `contacts.preferred_channel`: `email` nebo `phone`; `signatories.authorized`: boolean.
- `kyc.status`: `ok`, `pending`, `failed`; `kyc.checked_at`: datum `YYYY-MM-DD` podle OpenAPI.
- `created_at` a `updated_at`: ISO 8601 v UTC.
- API serializovat pomocí explicitního seznamu vlastností schématu `Client`. `name_normalized`, databázové timestamps a další interní atributy se do odpovědi nedostanou.
- Seed: malá opakovatelná sada syntetických klientů, stabilní UUID, unikátní IČO, varianty názvů a všech stavů. Opakované spuštění nesmí mazat nesouvisející data.

### Cases: wonderfulkb-uw-cases (navrhované schéma)

OpenAPI vyžaduje i cases; jejich fyzické schéma nebylo dodáno, proto je toto návrh:

- On-demand; partition key `case_id` (String), bez sort key.
- Atributy `case_id`, `client_id`, `status` (zatím pouze `open`), `created_at` (UTC ISO 8601), volitelné `metadata` (mapa).
- GSI `client-created-at-index`: partition key `client_id`, sort key `created_at`, projekce `ALL`.
- Seznam klientových cases číst přes GSI s `ScanIndexForward=false`. Čas ukládat v jednotném UTC formátu a přesnosti, aby lexikografické řazení odpovídalo časovému. Při stejném čase není pořadí mezi cases zaručeno; kontrakt sekundární řazení neurčuje.
- GSI jsou eventual consistent: bezprostředně po vytvoření case použít `GET /cases/{case_id}` s konzistentním čtením; při testování seznamu počítat s krátkým zpožděním indexu.
- Tabulky při odstranění stacku ponechat (`DeletionPolicy` a `UpdateReplacePolicy: Retain`).

## 4. Chování endpointů

| Endpoint | Plán |
|---|---|
| `GET /clients` | S `ico` použít `Query` na `ico-index`, jinak `Scan`; `name` a `status` kombinovat AND. |
| `POST /cases` | Validace vstupu, existence a aktivní stav klienta, vygenerování `case_id` (UUID v4) a podmíněné vytvoření case. Prostý create, bez idempotence. |
| `GET /cases/{case_id}` | `GetItem` podle klíče, 200 nebo 404. |
| `GET /clients/{client_id}/cases` | Nejdříve existence klienta (404), potom `Query` na GSI, nejnovější první, případně filtr status. |

### Vytvoření a souběh

1. `case_id` generuje služba (UUID v4); případné `case_id` v požadavku se ignoruje. Každé volání založí nový case, create není idempotentní.
2. Ověřit klienta: neexistující → 404, `inactive`/`blocked` → 409.
3. Zapsat `Put` s `attribute_not_exists(case_id)`; kolize UUID prakticky nenastává, případná provozní chyba je 5xx.
4. Úspěšný zápis vrací vždy 201.

## 5. Budoucí struktura komponenty

```text
be-case-client/
  openapi-case-client.yaml  # již uložený původní kontrakt
  template.yaml            # SAM, Lambda, REST API, tabulky, indexy, role, klíč
  samconfig.toml           # nesekretní konfigurace testovacího stacku
  requirements.txt
  requirements-dev.txt     # pytest a nástroje kontroly kontraktu
  src/                     # handler, validace, služby, DynamoDB repository
  scripts/                 # vytvoření lokálních tabulek, seed, smoke test
  tests/                   # unit a integrační testy
  events/                  # API Gateway REST proxy eventy pro sam local invoke
  env.local.example.json   # lokální konfigurace bez přihlašovacích údajů
  README.md                # spustitelné příkazy a provozní postup
```

Zdrojový OpenAPI ponechat čitelný; deployment definice jej rozšíří o Lambda proxy integrace, napojení API klíče a gateway responses. Ověřit podporovaný podmnožinový import OpenAPI v API Gateway. Samotné nahrání kontraktu nepropojí routy s Lambdou.

## 6. Typický lokální vývoj a testování

### A. Rychlý cyklus bez AWS

1. Doplnit Python 3.13 a SAM CLI; vytvořit virtualenv, nainstalovat aplikační a testovací závislosti. Spustit Docker daemon.
2. Unit testy volají služby/handler přímo, s izolovanou databázovou vrstvou: validace, normalizace názvů, generování `case_id` a převod chyb. Docker není potřeba.
3. Integrační testy použijí DynamoDB Local v Dockeru; vytvoří obě tabulky i GSI a vloží syntetické fixtures. Endpoint je konfigurovatelný, použijí se pouze fiktivní lokální credentials.
4. `sam build --use-container` připraví balíček v prostředí odpovídajícím Lambdě.
5. `sam local start-api` spustí lokální HTTP endpointy; `sam local invoke` poslouží pro jednotlivé uložené API Gateway eventy.

Příklad budoucích příkazů z adresáře komponenty (soubory a skripty teprve vzniknou):

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/unit
docker network create wonderfulkb-local
docker run --rm --name wonderfulkb-dynamodb --network wonderfulkb-local -p 8000:8000 amazon/dynamodb-local -jar DynamoDBLocal.jar -inMemory -sharedDb
```

Docker příkaz běží v samostatném terminálu. Pro skripty na hostiteli použít endpoint `http://localhost:8000`; pro Lambdu uvnitř SAM kontejneru `http://wonderfulkb-dynamodb:8000` na stejné Docker síti.

```bash
sam validate --lint
sam build --use-container
sam local start-api --docker-network wonderfulkb-local --env-vars env.local.json
sam local invoke CaseClientFunction --event events/list-clients.json --docker-network wonderfulkb-local --env-vars env.local.json
```

`CaseClientFunction` bude logické ID v šabloně. SAM emuluje handler a HTTP integraci, nikoli kompletní cloud: API keys/usage plans, IAM, throttling a skutečné chování indexů je nutné ověřit v AWS. Lokální API může mít jinou prefixovou cestu než cloudový stage `/v1`.

Pokud již existují build artefakty v `.aws-sam/`, po změně kódu znovu spustit `sam build`, aby lokální API používalo aktuální kód; při změně šablony lokální server restartovat.

### B. Doporučený cyklus pro tento hackathon: rychlé testy + reálné AWS

Po unit testech nasadit do testovacího účtu, naplnit syntetická data a volat skutečný HTTPS endpoint. Není nutné nejdříve budovat kompletní lokální emulaci. Lokální Lambda může volat i cloudovou DynamoDB přes `sam local ... --profile ai-hackathon`, pokud se vynechá lokální endpoint a předají názvy cloudových tabulek; takové volání již pracuje se skutečnými testovacími daty.

## 7. Nasazení do testovacího AWS

Příkazy jsou plán pro budoucí implementaci; v této přípravě se nespouštějí.

```bash
aws sso login --profile ai-hackathon
aws sts get-caller-identity --profile ai-hackathon
sam validate --lint
sam build --use-container
sam deploy --guided --stack-name wonderfulkb-case-client-test --region eu-central-1 --profile ai-hackathon --capabilities CAPABILITY_IAM
```

- Guided deploy uloží nesekretní parametry do `samconfig.toml`; další aktualizace přes `sam build` a `sam deploy --config-env default --profile ai-hackathon`.
- SAM zabalí artefakty do S3 a CloudFormation vytvoří/aktualizuje prostředky. Stack má vlastnit nové tabulky, pokud stále neexistují; názvy tabulek parametrizovat.
- Výstupy stacku: URL API (`.../v1`), název Lambdy, názvy tabulek a ID API klíče. Hodnotu klíče získat samostatně přes AWS CLI, neukládat do Git.
- Seed skript spustit s explicitním profilem, regionem a názvem klientské tabulky.
- Smoke test: vyhledat aktivního klienta, vytvořit case, zopakovat vytvoření, načíst case a seznam klientových cases.
- Logy: `sam logs --name CaseClientFunction --stack-name wonderfulkb-case-client-test --region eu-central-1 --profile ai-hackathon --tail`.
- Rychlé iterace nad testovacím stackem: `sam sync --code --watch --stack-name wonderfulkb-case-client-test --region eu-central-1 --profile ai-hackathon`. Přímý sync je vývojová zkratka; změny infrastruktury a finální stav potvrdit plným `sam deploy`.

Příklad volání po deployi (proměnné vyplněné z výstupů a testovacích dat):

```bash
curl -H "x-api-key: $API_KEY" "$API_URL/clients?limit=10"
curl -X POST -H "x-api-key: $API_KEY" -H 'Content-Type: application/json' \
  -d "{\"client_id\":\"$CLIENT_ID\"}" "$API_URL/cases"
```

## 8. Ověření funkčnosti při implementaci

- Kontrakt: všechny čtyři operace a tvar odpovědí vůči OpenAPI, včetně absence interních atributů klienta.
- Filtry: IČO s nulou na začátku, diakritika, právní forma, kombinace AND, prázdné výsledky a vícestránkové výsledky včetně prázdné stránky s tokenem.
- Cases: 201 pro nový (vždy s novým `case_id`), 409 pro neaktivního a blokovaného klienta, 404 pro neexistujícího klienta/case.
- Souběžné vytvoření pro stejného klienta: každé volání dostane vlastní `case_id` a 201.
- Seznam cases: nejnovější první, stránkování, filtr stavu, existující klient bez cases → prázdný seznam, neexistující klient → 404.
- Reálné AWS: 403 bez klíče i se špatným klíčem, správný JSON error, funkční IAM a indexy; řízeně ověřit 429 přes nízký testovací limit usage planu (omezení je best effort).
- Smoke testy používat vlastní rozpoznatelná ID a neodstraňovat seed/ostatní cases. Indexovou eventual consistency řešit omezeným opakováním čtení, nikoli náhodnými dlouhými prodlevami.

## 9. Pořadí realizace

1. Doplnit nástroje, založit SAM šablonu a konfiguraci samostatného modulu.
2. Vytvořit tabulky, GSI, API, API klíč/usage plan a Lambda roli.
3. Implementovat normalizaci, validace, databázovou vrstvu a čtyři operace.
4. Doplnit deterministický seed a cílené testy uvedené výše.
5. Nasadit přímo do testovacího účtu, naplnit klienty, provést smoke testy a ověřit odpovědi API Gateway.
6. Zapsat skutečnou URL API a přesné vývojové/deploy příkazy do README komponenty.

## Reference

- AWS SAM lokální HTTP API: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/using-sam-cli-local-start-api.html
- SAM deploy: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html
- SAM sync: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-sync.html
- REST API klíče a usage plans: https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-usage-plans.html
- DynamoDB Scan a filtry: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Scan.html
- DynamoDB Local: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html
