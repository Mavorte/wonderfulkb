---
title: "Case & Client: vyměnit mock za DynamoDB adaptér nad externími tabulkami"
type: implementation
---

# Case & Client: vyměnit mock za DynamoDB adaptér nad externími tabulkami

## Cíl a vstupy

Dodat volitelný skutečný DynamoDB adaptér do existující komponenty `be-case-client/`. Zachovat jeden handler, čtyři veřejné operace a business logiku. Implementační vstupy: `be-case-client/openapi-case-client.yaml` (1.3.0-final), existující Case/Client repository rozhraní, mock/behavior testy a README; proposal `docs/proposals/proposal-20261019-114433-08800d_case-client-lambda-vyvoj-nezavisly-na-externi-databazi.md`, sekce db-connection/external-db/deployed-integration. Výsledek je kód adaptéru, offline testy, explicitně spouštěný HTTP integrační runner, servisní šablona a runbook — ne cloudové připojení/deploy.

Nepřidávat druhou aplikaci či HTTP proxy na cizí API. API klíč není DB credential a není implementační vstup. Privátní dokumenty ani obsah sdílené quick-connect přílohy mimo sanitizovaný proposal nejsou vstupy tasku.

## Datový kontrakt

Host ověřil DescribeTable v účtu `609394381050`, region `eu-central-1`:
- `wonderfulkb-uw-clients`: PK `client_id` String, GSI `ico-index` PK `ico` String, ALL projection.
- `wonderfulkb-uw-cases`: PK `case_id` String, GSI **`client-created-index`**, PK `client_id` String / SK `created_at` String, ALL projection.
- ARN prefix `arn:aws:dynamodb:eu-central-1:609394381050:table/`; tabulky mají on-demand billing a vlastní je jiný tým. Starší `client-created-at-index` nepoužívat ani nevytvářet.

Nejsou ověřené nekličové atributy existujících položek. OpenAPI je veřejný cílový datový tvar; nevyžadovat neověřené pomocné sloupce. V README vyjmenovat předpoklady ke kontrole hostem (UTC formát času, metadata, stav klienta). Při nekompatibilních datech vrátit sanitizovanou chybu, ne vymyšlené hodnoty.

## Povolený rozsah a jednoduchost

Pouze `be-case-client/**` včetně dependency manifestu, SAM šablony, README a testů; frontend, jiné repozitáře, registry, credentials a externí konfiguraci neměnit. Zachovat OpenAPI, existující API key ochranu, všechny mock behavior testy a explicitní mock opt-in.

Přidat doménově pojmenovaný `case_client_dynamodb_repository.py` a `test_case_client_dynamodb_repository.py`; využít existující doménové soubory pro factory/handler, ne nové obecné `storage.py`, `service.py`, `utils.py`. Zkontrolovat stejné basename před přidáním. Jedna repository hranice, žádný framework, ORM, plugin systém nebo duplicitní normalizace/business služba.

## Implementace

1. Přepnutí `DATA_BACKEND=dynamodb`; `mock` zachová `ALLOW_EPHEMERAL_MOCK=true`. Žádný automatický fallback. Konfigurace `CLIENTS_TABLE_NAME`, `CASES_TABLE_NAME`, `CLIENTS_ICO_INDEX_NAME`, `CASES_CLIENT_CREATED_INDEX_NAME`, AWS region. V DB režimu pravdivé `X-Data-Backend: dynamodb`. SDK dependency deklarovat a připravit reprodukovatelné nativní balení. Lokální testy nesmějí potřebovat Docker, DynamoDB Local, LocalStack nebo AWS SSO. Lambda používá execution role, ne profil: `ai-hackathon` patří pouze do host runbooku.
2. Repository dostává injektovatelného SDK klienta/resource. `GetItem` pro klienta a case; case/idempotence číst `ConsistentRead=true` na tabulce. Seznam klientů s IČO přes Query `ico-index`; další AND filtry zachovat. Bez IČO stránkovaný Scan pro malý syntetický dataset, normalizace názvu sdílená s mockem. Žádný požadavek na nový index nebo `name_normalized` atribut.
3. Seznam cases: ověřit existenci klienta, potom Query `client-created-index`, `ScanIndexForward=false`; zachovat status, limit a token. GSI je eventually consistent, nepoužívat nepodporované silné čtení indexu ani neslibovat okamžitý list po POST.
4. SDK stránkování: DynamoDB Limit není počet shod po filtru; pokračovat přes prázdné filtrované stránky a respektovat LastEvaluatedKey/1MB hranici. Žádné ztracené/duplicitní výsledky při plnění veřejné stránky, včetně zbylých položek v SDK stránce. Token neprůhledný, strukturálně validovaný, navázaný na dotaz/backend a použitelný napříč instancemi; token jiné konfigurace/dotazu vrátí400. Bounded práce jednoho requestu, případná neplná/prázdná stránka s pravdivým pokračováním; žádný neomezený Scan loop. Zdokumentovat eventual consistency a absenci snapshotové konzistence při souběžných změnách.
5. Create-case: nejprve konzistentně ověřit existující ID. Stejné ID+klient vrací původní hodnotu/200 bez přepsání metadat/času, i když je klient nyní inactive/blocked. Jiné vlastnictví409. U nového ID neznámý klient404, neaktivní/blokovaný409. Nový case vytvořit `TransactWriteItems`: podmínka existence+active status klienta a podmíněný Put case (`attribute_not_exists(case_id)`). Vysvětlit a otestovat závody: stejný ID+klient, různí klienti a současná změna stavu klienta. Po condition conflict opětovně konzistentně přečíst a rozlišit idempotenci/business konflikt od transient chyby. Bez nekonečných retries, bez duplicitního insertu, žádný nechráněný Get→Put. Transakční chybu oprávnění/throttling nepřekládat automaticky na409.
6. Mapování dat: podporované OpenAPI JSON typy včetně vnořených metadat, null, boolean a čísel; explicitní korektní boto3/Decimal serializace. Nevracet interní atributy. Zachovat dokumentovaný metadata limit z komponenty, bezpečně ošetřit neplatný/velký item bez částečných zápisů. Nové created_at jednotně UTC tak, aby GSI správně řadil.
7. AccessDenied, resource-not-found, timeout, throttling a poškozená uložená data nejsou business404 ani prázdný seznam. Vrátit sanitizované 5xx `{"error":"..."}`; bez logování klientů, metadat, credentialů nebo raw SDK exception detailů do odpovědi. Zachovat gateway403/429 jako oddělené chování.
8. SAM: parametry existujících tabulek/indexů, nastavení režimu a least-privilege role policy. Pouze potřebné GetItem/Query/Scan pro clients a index; GetItem/Query/PutItem pro cases/index a ConditionCheckItem na clients pro transakční kontrolu, rozdělit správně table/index resources dle operace. Pro TransactWriteItems AWS autorizuje jednotlivé akce, nevymýšlet plošné `dynamodb:*` nebo transakční wildcard policy. Žádné DeleteItem/UpdateItem, DB resources, seed, migrace, VPC nebo oprávnění na jiné tabulky. Mock výchozí režim zachovat bez aktivních DB práv (podmíněná policy). Šablona je artefakt, worker ji nenasazuje.

## Testy a přejímka

- Charakterizovat stávající handler/repository chování a zachovat mock testy; sdílená business pravidla neduplikovat uvnitř adaptéru.
- Offline testy skutečného adaptéru přes botocore Stubber či ekvivalentně přesné SDK fake; handler s DB adaptérem otestovat dohromady. Explicitní falešné credentials/region, zakázat metadata discovery a skutečnou síť. Testy nesmějí číst uživatelův AWS profil nebo DB.
- Ověřit přesné table/index názvy, klíče, podmínky, consistency a sestupné řazení; nulové shody s LastEvaluatedKey, filtrování před/za limitem, více SDK stránek a neplatné/cizí tokeny. Vnořená metadata a desetinná čísla zachovat.
- Simulovat 201→200 po nové instanci adaptéru, neměnnost metadat/created_at, jiného vlastníka409, neznámého klienta404, inactive/blocked409 a transakční závody včetně DB chyb. Stub test není důkaz skutečného cloudového souběhu.
- Chybějící/nesprávná konfigurace nesmí aktivovat mock; backend marker odpovídá režimu. Staticky ověřit externí-only prostředky, přesné IAM actions/resources a žádná DB práva mocku.
- Spustit komponentové unittest testy z kořene repozitáře s explicitním import path dle existující komponenty, compileall, `sam validate --lint`, `npm --prefix apps/backoffice test` a `npm --prefix apps/backoffice run build`. Nezeslabovat existující brány. Chybějící SAM nebo jiný nástroj přesně reportovat hostu, netvrdit ověření bez výsledku.
- README: instalace SDK/dev závislostí, nativní SAM balení bez povinného Dockeru, přesné env/parametry, rozdíl SSO a role, minimální práva včetně zápisu, eventual consistency, náklady Scan a bezpečné oddělení mock/test/live prostředků. Host před případným deployem zjistí vlastnictví cílového API/stacku; neimportovat/nepřevzít cizí nasazení automaticky.
- Popsat NEPROVEDENÝ host smoke po zvláštním schválení: syntetické ID, vytvoření a konzistentní get, opakování a konflikt, omezený souběh a GSI propagace. Bez automatického úklidu data mazáním. Finále oddělí lokální SDK důkazy od neprovedeného runtime/deploy/persistence smoke.

## HTTP integrační runner pro hosta po deployi

V témže tasku dodat `be-case-client/tests/integration/case_client_api_integration.py` a offline test `be-case-client/tests/test_case_client_api_integration.py`. Respektovat přesný návrh `deployed-integration` v proposalu. Žádný třetí server nebo další implementační task, žádný auto-live hook v běžných testech. Runner použije skutečné HTTPS API; injektovatelný transport dovolí jeho kompletní offline ověření. Domain basename před přidáním zkontrolovat.

- Vstupy: CASE_CLIENT_BASE_URL, CASE_CLIENT_API_KEY pouze z prostředí, syntetický fixture manifest, explicitní expected backend. Ověřit HTTPS/očekávaný target, nenásledovat redirect s credentialy; nemít default cizí API URL ani klíč. Standardní knihovna postačí.
- Default read-only: kontroly gateway403 bez/s chybným klíčem, marker a JSON typy, klient podle IČO/name/status, známý case, list cases, validace400, neexistující404, stránkování limit1 přes stabilní fixtures a neplatné/cizí tokeny. Nevyvozovat úspěch stránkování z jedné položky. Neměnit API kvůli testu.
- Pouze `--allow-writes --expected-backend dynamodb` po úspěšném read-only preflight: unikátní validní it-<run_id> ID; nový POST201→GET shodného case; repeat200 s původní metadata/časem; jiný známý aktivní klient409; neexistující404 a inactive/blocked409 bez vytvoření case; GSI výskyt v bounded polling/stránkování. Dva bounded concurrent POSTy stejné ID/klient dávají201+200, různí aktivní klienti201+409. Nejvýše2 souběžné requesty a konzervativní request budget/rate pod10req/s; žádný flood429.
- Manifest dodá host/DB tým; API neumí clients vytvořit. Plný profil potřebuje2aktivní +inactive+blocked klienty a více stránkovatelných položek. Chybějící povinné vstupy mají nonzero NOT_READY, nikoli zelený SKIP. Read-only subset nesmí být označen jako full acceptance. Nepotřebné konfliktní IDs test neodvozuje z reálných dat.
- Request/total timeouts a omezené retry pouze na bezpečné GET/GSI propagaci; žádné automatické opakování nejednoznačného POST timeoutu/5xx. Sanitizovaný JSON report+summary s run_id/target/backend/scénáři/statusy/latencemi a vytvořenými syntetickými IDs; žádné secrets, headers nebo raw response dumpy. Output se neukládá automaticky do verzovaného repozitáře. Selhání/assertion/fixture-not-ready mají nonzero; PASS jen všechny povinné testy vybraného profilu.
- Bez DELETE/DB přístupu/seedu, beze změn Lambda concurrency nebo forcing cold startu. Nové HTTP spojení není důkaz jiné execution instance. Vytvořené syntetické cases zůstanou pro domluvený úklid vlastníkem DB. Runbook jasně vypíše write effects a konfiguraci, neobsahuje skutečný klíč. Live spuštění patří hostu po zvláštní autorizaci.
- Offline testovat runner se simulovaným transportem, no-network default discovery, credential redakci v chybách/reportu, explicitní write gate, target/redirect ochranu, selhání/scénáře, chybějící fixture, stránkování a bounded GSI deadline. Simulované HTTP výsledky nejsou live smoke důkaz.

## Bezpečnostní hranice

Žádné AWS API operace ani čtení živých dat, credentials/profilů nebo privátních dokumentů; žádné HTTP volání existujícího API, cloudové zápisy, seed, deployment, restart, model/provider/message volání, lokální modely nebo změny služeb/schedulerů. Žádný API klíč v repozitáři, fixture, logu či výstupu. Neměnit autocommit, task lifecycle nebo projektový registry runner. Instalaci běžného host runtime a skutečné připojení/nasazení vlastní host mimo tento kódový task.
