---
title: "Case & Client: vyměnit mock za DynamoDB adaptér nad externími tabulkami"
type: implementation
---

# Case & Client: vyměnit mock za DynamoDB adaptér nad externími tabulkami

## Cíl a vstupy

**Rozsah upřesněný Michalem 19. 10. 2026 14:35: pouze implementace adaptéru a lokální integrace pomocí testů a mocků.** Propojit skutečný Python handler/business rozhraní s novým adaptérem nad stubovaným SDK. HTTP integrační runner ani jeho testovací infrastrukturu v tomto tasku NEVYTVÁŘET; budou předmětem samostatného tasku až po nasazení. Výsledek tohoto tasku se přijímá na základě lokálních testů a nezávislých kódových bran. Deploy, AWS připojení, skutečné HTTP volání a živé integrační testy nejsou součástí provedení ani podmínkou dokončení; neprovádět je ani při dostupných credentials. Budoucí nasazení je odložené, nikoli automatická návaznost tohoto tasku. Tento explicitní rozsah má přednost před případnou obecnou end-to-end formulací v podkladech. Nevytvářet jinou implementaci služby — rozšířit Python komponentu z prvního tasku.

Dodat volitelný skutečný DynamoDB adaptér do existující komponenty `be-case-client/`. Zachovat jeden handler, čtyři veřejné operace a business logiku. Implementační vstupy: `be-case-client/openapi-case-client.yaml` (1.3.0-final), existující Case/Client repository rozhraní, mock/behavior testy a README; proposal `docs/proposals/proposal-20261019-114433-08800d_case-client-lambda-vyvoj-nezavisly-na-externi-databazi.md`, sekce db-connection/external-db. Výsledek je kód adaptéru, lokální integrační a jednotkové testy, servisní šablona a dokumentace konfigurace — ne HTTP runner, cloudové připojení nebo deploy. Sekce deployed-integration v proposalu je budoucí návrh mimo implementační rozsah tohoto tasku.

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
- Finále oddělí lokální SDK/handler důkazy od neprovedeného runtime/deploy/persistence smoke. Nepřidávat HTTP integrační runner, CLI, fixture manifest nebo cloudový testovací framework; budoucí scénáře zůstávají jen návrhem v proposalu.

## Bezpečnostní hranice

Žádné AWS API operace ani čtení živých dat, credentials/profilů nebo privátních dokumentů; žádné HTTP volání existujícího API, cloudové zápisy, seed, deployment, restart, model/provider/message volání, lokální modely nebo změny služeb/schedulerů. Žádný API klíč v repozitáři, fixture, logu či výstupu. Neměnit autocommit, task lifecycle nebo projektový registry runner. Instalaci běžného host runtime a skutečné připojení/nasazení vlastní host mimo tento kódový task.
