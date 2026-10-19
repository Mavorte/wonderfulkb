# Plan 2026-10-19: Case & Client — DynamoDB adapter

## Analysis
- Zachovat `CaseClientRepository` se čtyřmi metodami v `be-case-client/src/case_client_repository.py`; rozšířit existující factory `create_handler` a `lambda_handler`, nikoli vytvářet druhou službu.
- Použít nezměněné `be-case-client/openapi-case-client.yaml` 1.3.0-final a sekce db-connection/external-db v `docs/proposals/proposal-20261019-114433-08800d_case-client-lambda-vyvoj-nezavisly-na-externi-databazi.md`; respektovat upřesnění rozsahu 14:35 před staršími end-to-end návrhy.
- Zachovat mock testy v `test_case_client_lambda.py`, jeho reset/idempotenci, explicitní opt-in i řazení. Nahradit pouze zastaralé statické předpoklady „SDK zakázáno ve všech modulech“ a „role vždy logs-only“ ekvivalentními kontrolami izolovaného mocku a podmíněných DB práv.
- Použít hostem dodaný kontrakt: `wonderfulkb-uw-clients` / `client_id` / `ico-index(ico)` a `wonderfulkb-uw-cases` / `case_id` / `client-created-index(client_id, created_at)`, projekce ALL, účet `609394381050`, region `eu-central-1`. Nekličové atributy validovat proti OpenAPI; nevymýšlet pomocné sloupce nebo výchozí business hodnoty.
- Uplatnit lokální learnings `architecture/decisions-case-client-mock-fixture-pagination.md`, `architecture/2026-10-19_in-memory-lambda-mocks-provide-only-execution-environment-lo.md`, `runtime-errors/rules-case-client-cursor-json-depth.md` a `tooling/2026-10-19_static-sam-checks-cannot-establish-deployed-gateway-behavior.md`: zachovat meziinstanční kurzory, hluboký JSON tokenu mapovat na400, oddělit stub důkazy od cloudových tvrzení.
- Zaznamenat provenance recallu: `backend=local`, `collection=wonderfulkb-learnings`, diagnostic `Collection not found: wonderfulkb-learnings`; aplikovat načtené lokální soubory. Při přidávání souborů zopakovat kontrolu basename; průzkum nenašel kolize ani PlantUML.

## Approach
- Provést implementaci jen v `be-case-client/**` na feature větvi; zachovat cizí rozpracované změny. Aktuální větev `plan-case-client-dynamodb-adapter` již vyhovuje pravidlu bez změn na main.
- Přidat jediný `DynamoDBCaseClientRepository` s injektovaným low-level boto3 klientem; factory SDK vytvoří až v DB režimu, bez profilu a bez automatického fallbacku. Pro mock neprovádět ani credential discovery.
- V existujícím `case_client_repository.py` sdílet normalizaci názvu a malé čisté business rozhodovací funkce pro existující case/vlastníka a aktivitu klienta. Adaptéry ponechají vlastní atomické persistence mechanismy; nepřidávat service/storage/utils vrstvu.
- Pro lokální integraci použít skutečný handler + skutečný adaptér + botocore Stubber. Zakázat síť, profilové soubory a metadata discovery; nevytvářet HTTP runner, cloudové fixtures, CLI ani server.
- Použít `skill:tdd` pro implementační RED/GREEN, `skill:validate-implementation` pro finální kontrolu kontraktu a scope, `skill:code-review` pro nezávislé kódové brány a `skill:write-review-report` na konci review fáze. Při práci s boto3 použít `skill:aws-sdk-python-usage`; nynější plán nevyžaduje AWS API ani čtení soukromých připojovacích podkladů.

## Implementation
1. **Charakterizace a RED:** spustit původní unittest suite, uložit výsledek, potom vytvořit test níže. Upravit testy před implementací každého dalšího scénáře; zachovat původní mock behavior assertions.
2. **Factory a společná pravidla:** rozšířit `_configured()` o validované `DATA_BACKEND=dynamodb`, obě table names, oba index names a `AWS_REGION` (případně `AWS_DEFAULT_REGION`). Chybějící/prázdné/neplatné hodnoty odmítnout i při injekci repository; mock stále vyžaduje přesné `ALLOW_EPHEMERAL_MOCK=true`. Marker odvozovat z úspěšně zvoleného backendu pro úspěchy i chyby; chyba inicializace nemá falešný marker. Zachovat warm cache; nesmí po změně konfigurace obsluhovat starý backend (navázat cache na konfiguraci nebo změnu odmítnout).
3. **SDK a JSON:** deklarovat uzamčené runtime závislosti v `src/requirements.txt` a reprodukovatelné dev závislosti v `requirements-dev.txt`. Použít boto3/botocore TypeSerializer/TypeDeserializer, pro přesné JSON Decimal zvolit `simplejson` s `use_decimal=True`; nepřevádět čísla na řetězce ani všechny Decimal na float. Parsovat desetinné requesty bezeztrátově, odmítat NaN/Infinity, nevalidní/neserializovatelná čísla a překročení DynamoDB číselných mezí před zápisem. Sdílet JSON cestu a 16384b limit kompaktního UTF-8 metadata objektu v handleru; přímý adaptér musí rovněž bezpečně odmítnout neplatný item. Zachovat null/bool/int/list/map a vnořená metadata.
4. **Read a mapování:** `GetItem` na primárních klíčích; case detail, idempotence i kontroly klienta používat `ConsistentRead=true`. Chybějící Item znamená doménovou404, chybějící tabulka nikoli. Validovat povinná pole, enumy, typy a volitelné objekty dle OpenAPI, včetně UTC `created_at`; metadata mohou chybět, ale přítomná musí být objekt. Nevyžadovat `source` ani jiné volitelné atributy. Interní atributy ignorovat, veřejný allowlist zachovat; poškozená uložená data → sanitizovaná500.
5. **List clients/cases:** při IČO Query `ico-index`, jinak Scan; další AND filtry aplikovat nad položkami a `normalize_name` sdílet s mockem. Nevyžadovat `name_normalized`. Cases nejprve ověří klienta, potom Query `client-created-index` s `ScanIndexForward=false`, bez silného čtení GSI; status filtrovat při stránkování. DB clients nemají OpenAPI příslib globálního pořadí; neprovádět neomezené třídění Scan. Cases řadit dle indexu, bez nového veřejného tie-break slibu nad shodným časem; mock svůj stávající tie-break zachová.
6. **Bounded stránkování:** použít Query/Scan paginator po SDK stránkách s `PageSize=min(limit,25)`, nejvýše 8 SDK stránek/request (nejvýše 200 vyhodnocených položek). Pokračovat přes prázdné filtrované stránky a 1MB hranici. Je-li SDK stránka celá spotřebovaná, pokračování = její `LastEvaluatedKey`; naplní-li se veřejný limit uprostřed SDK stránky, pokračování = úplný klíč poslední vydané položky, nikoli LEK konce stránky. Pro GSI zahrnout table PK i index PK/SK, pro Scan table PK; při další instanci předat jako `ExclusiveStartKey`. Tím se nepřeskakují zbylé shody ani neukládají celé klientské objekty do tokenu. Při vyčerpání budgetu vrátit i neplnou/prázdnou stránku s pravdivým tokenem; konec pouze bez pokračování. Omezit SDK timeouty/retries (connect1s/read2s, total attempts1) a celkový čas: před dalším SDK voláním kontrolovat monotonic deadline7s s rezervou3s pro volání, případně kratší zbývající Lambda budget. Při časovém budgetu vrátit pokračování, skutečný SDK timeout →5xx. Testovat hranice s fake clock, bez čekání.
7. **Token:** použít verzovaný base64url JSON s přesným schématem a klíčem; fingerprint zahrne backend, region, obě tabulky/indexy, operaci, client_id, normalizované filtry a limit. Omezit token na4096 znaků, kontrolovat kanonické kódování, typ/verzi (ne bool), přesné klíče a stringové AttributeValues klíčů; zachytit i RecursionError. Cizí/mock/změněný-dotaz/změněná-konfigurace token →400 před SDK voláním. Nepoužívat instance-local tajemství; kurzor není autentizace ani snapshot. Otestovat resume uprostřed poslední SDK stránky bez LEK i GSI se shodnými timestampy.
8. **Atomický create:** konzistentní Get case před čtením klienta; existující stejný vlastník →původní case/200 i při neaktivním/odstraněném klientovi, jiný →409. Pro nový case číst klienta, neznámý →404, inactive/blocked →409. Připravit validovaný item s `status=open`, jednou zvoleným `created_at` ve fixním UTC formátu `YYYY-MM-DDTHH:MM:SS.ffffffZ`; žádný předchozí write. Poslat `TransactWriteItems` s ConditionCheck klienta `attribute_exists(client_id) AND status=:active` (expression aliases) a Put case s `attribute_not_exists(case_id)`. Žádný nechráněný Get→Put ani samostatný duplicitní insert.
9. **Závody a selhání:** pouze při transaction condition failure konzistentně znovu přečíst case a případně klienta: vítěz stejného klienta →200 původní data, jiný →409, smazaný klient →404, inactive/blocked →409. Pokud nejsou business důvody pro konflikt, vrátit sanitizovanou transient5xx; ostatní cancellation reasons, transaction conflict, AccessDenied, throttling, resource-not-found a timeout nepřekládat automaticky na409. Rozlišit CancellationReasons, včetně kombinovaných a chybějících; nepředpokládat vítěze z textu výjimky. Omezit recovery na jeden read-back průchod, bez automatického opakovaného zápisu. Po nejistém výsledku timeoutu netvrdit úspěch; další explicitní stejný POST rozhodne idempotentně.
10. **SAM/IAM:** zachovat JSON podobu `template.yaml`, sedm existujících prostředků, jednu Lambdu/python3.13, CodeUri `src/`, chráněné čtyři routy a gateway403/429. Přidat parametry backendu (default mock), externích table/index názvů a účtu tabulek (default609394381050), env refs a DynamoDB condition; region brát z prostředí Lambdy, nedefinovat rezervovaný `AWS_REGION`. Podmíněnou policy přidat přes Fn::If/AWS::NoValue pouze pro DB. Nevytvářet DB resources ani managed wildcard policy. Rozdělit přesné akce/resources dle tabulky níže, zachovat scoped logs.

| Resource (prefix `arn:${AWS::Partition}:dynamodb:${AWS::Region}:${ExternalTablesAccountId}:table/`) | Povolené actions pouze v DB režimu |
|---|---|
| `${ClientsTableName}` | `dynamodb:GetItem`, `dynamodb:Scan`, `dynamodb:ConditionCheckItem` |
| `${ClientsTableName}/index/${ClientsIcoIndexName}` | `dynamodb:Query` |
| `${CasesTableName}` | `dynamodb:GetItem`, `dynamodb:PutItem` |
| `${CasesTableName}/index/${CasesClientCreatedIndexName}` | `dynamodb:Query` |

11. **Dokumentace/balení:** aktualizovat README o přesné env/parametry, SDK/dev instalaci, Python3.13 nativní `sam build --template-file be-case-client/template.yaml` bez `--use-container` a použití výstupu `.aws-sam/build/template.yaml` pro budoucí host balení. Připnout SDK i transitivní verze pro opakovatelný build; při chybějícím Python3.13/SAM reportovat nástroj, neinstalovat host runtime. Uvést execution role vs host SSO `ai-hackathon`, potřebná write/ConditionCheck práva, Scan budget/náklady, eventual consistency a absenci snapshotu. Vyjmenovat k host kontrole UTC/precision timestamps, reprezentaci metadata a client status. Oddělit syntetický mock/test od budoucího live prostředí; před budoucím deployem host ověří vlastnictví cílového API/stacku/role, žádný automatický import nebo převzetí. HTTP runner zůstane pouze v proposalu.

## TDD
- Implementace TDD cyklu dle skill:tdd; v implementační fázi nejprve vytvořit test, zachytit skutečný RED, potom minimální GREEN a rozšiřovat scénáře. Nyní skeleton pouze uložit v plánu.
- Nový soubor: `be-case-client/tests/test_case_client_dynamodb_repository.py`, standardní unittest + botocore Stubber. Nejdříve zajistit deklarované test dependencies; chybějící SDK není zamýšlený RED.
- Focused command z kořene: `PYTHONPATH=be-case-client/src python3 -m unittest discover -s be-case-client/tests -p 'test_case_client_dynamodb_repository.py' -v`.
- Vložit tento spustitelný skeleton; po GREEN přidat přímé adapter testy se stejným stubovaným klientem a kompletní matici níže:

```python
import json
import os
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.stub import Stubber
import case_client_handler


class DynamoDBHandlerTests(unittest.TestCase):
    def test_factory_strong_get_preserves_decimal_and_backend(self):
        env = {
            'DATA_BACKEND': 'dynamodb',
            'CLIENTS_TABLE_NAME': 'wonderfulkb-uw-clients',
            'CASES_TABLE_NAME': 'wonderfulkb-uw-cases',
            'CLIENTS_ICO_INDEX_NAME': 'ico-index',
            'CASES_CLIENT_CREATED_INDEX_NAME': 'client-created-index',
            'AWS_REGION': 'eu-central-1',
            'AWS_DEFAULT_REGION': 'eu-central-1',
            'AWS_EC2_METADATA_DISABLED': 'true',
            'AWS_CONFIG_FILE': os.devnull,
            'AWS_SHARED_CREDENTIALS_FILE': os.devnull,
        }
        case = {
            'case_id': 'offline-db',
            'client_id': '11111111-1111-4111-8111-111111111111',
            'status': 'open', 'created_at': '2026-10-19T12:00:00.000000Z',
            'metadata': {'nested': [None, True, Decimal('0.1234567890123456789')]},
        }
        with patch.dict(os.environ, env, clear=True), \
                patch('socket.socket', side_effect=AssertionError('network forbidden')), \
                patch('socket.getaddrinfo', side_effect=AssertionError('DNS forbidden')):
            sdk = boto3.client('dynamodb', region_name='eu-central-1',
                               aws_access_key_id='offline', aws_secret_access_key='offline')
            self.addCleanup(sdk.close)
            with Stubber(sdk) as stub, \
                    patch('boto3.client', return_value=sdk), \
                    patch.object(case_client_handler, '_cached_handler', None):
                stub.add_response('get_item', {
                    'Item': TypeSerializer().serialize(dict(case, internal='hidden'))['M']
                }, {'TableName': 'wonderfulkb-uw-cases',
                    'Key': {'case_id': {'S': 'offline-db'}}, 'ConsistentRead': True})
                result = case_client_handler.lambda_handler({
                    'httpMethod': 'GET', 'resource': '/cases/{case_id}',
                    'pathParameters': {'case_id': 'offline-db'},
                }, None)
                self.assertEqual(result['statusCode'], 200, result)  # RED: dnes500
                self.assertEqual(result['headers']['X-Data-Backend'], 'dynamodb')
                self.assertEqual(json.loads(result['body'], parse_float=Decimal), case)
                stub.assert_no_pending_responses()
```

| Test | RED před implementací | GREEN po implementaci |
|---|---|---|
| `test_factory_strong_get_preserves_decimal_and_backend` | assertion `500 != 200` z mock-only konfigurace |200, dynamodb marker, přesný GetItem, bezeztrátová metadata, skryté interní pole, vyčerpán stub|
| Následná pagination matice | chybějící DB Query/Scan/resume chování | žádné ztráty/duplicitní výsledky na stabilních datech; bounded práce |
| Následná transaction matice | chybějící atomický create/recovery | přesné podmínky,201/200/404/409 a rozlišené5xx |

## Testing
- Zachovat všechny mock behavior testy; omezit AST zákaz boto3/botocore na mock/shared modul a doplnit test, že mock factory nevytváří SDK klienta ani nečte credential chain. Síť/DNS zakázat po celou dobu všech DB testů, explicitní falešné credentials a `/dev/null` configy použít i při factory testech; žádné SSO.
- Ověřit přesné SDK requesty: table/index/key, Query vs Scan, ConsistentRead pouze na tabulkách, sestupný cases index, AND normalizaci a nevyžadování pomocných sloupců. Chybějící klient seznamu →404, existující bez cases →[]; všechny čtyři operace přes skutečný handler s DB adaptérem.
- Pokrýt pagination: prázdná stránka+LEK, filtry před/za limitem, více SDK stránek,1MB rozdělení, overflow shod uprostřed SDK stránky, poslední SDK stránka bez LEK, plný budget bez shody, stejné timestamps, token do nové instance a exhaust bez duplicit/ztrát. Testovat cizí backend/query/region/table/index/client/limit, neplatné schéma, příliš dlouhý i hluboce zanořený token →400 bez SDK requestu.
- Pokrýt create:201 a200 s novou instancí adaptéru/handleru, původní metadata/čas nezměněné; existující ID při inactive/blocked/absent klientovi; jiný vlastník409; nový unknown404/inactive409/blocked409. Stubovat transakční interleavingy stejný ID+stejný klient, různí klienti a souběžná změna/deletion klienta. Assertovat jediný write, přesné ConditionCheck+Put a bounded read-back; konflikt s dosud nezjištěným vítězem →5xx.
- Ověřit metadata null/bool/int/desetinná čísla/vnoření, Unicode16384b hranici, přímé SDK serializace, neplatné/velké itemy bez zápisu a kompletní veřejný allowlist. Poškozené uložené typy/enumy/čas/metadata →500, volitelné chybějící atributy bez vymyšlených náhrad.
- Stubovat AccessDenied, ResourceNotFound, throttling, timeout, mixed/missing transaction CancellationReasons a unknown SDK error. Assertovat JSON `{"error":"..."}`,5xx, žádné raw exception detaily/klienti/metadata/credentials ve výstupu či zachycených aplikačních logách; nesmí vzniknout fallback/prázdný úspěch/business404/409.
- Staticky vyhodnotit obě větve Fn::If: mock bez aktivních DB práv; DB přesná matice actions/resources výše. Zakázat DeleteItem/UpdateItem, `dynamodb:*`, index wildcardy, DB resources, seed/migrace/VPC a nové endpointy; zachovat key/usage-plan/403/429 a scoped log práva. Test nesmí pouze hledat řetězec v nevyhodnocené šabloně.
- V implementační fázi spustit z kořene a zaznamenat přesný exit/výstup:

```sh
PYTHONPATH=be-case-client/src python3 -m unittest discover -s be-case-client/tests -p 'test_*.py' -v
python3 -m compileall -q be-case-client/src be-case-client/tests
sam validate --lint --template-file be-case-client/template.yaml
npm --prefix apps/backoffice test
npm --prefix apps/backoffice run build
```

- Před lintem nastavit explicitní region a pro AWS credential/config lookup pouze fake test prostředí; nedovolit síť ani přístup k host profilu. Chybějící SAM/cfn-lint/Python nebo offline-incompatible validaci přesně reportovat s neprovedeným příkazem; nenahrazovat statickým testem tvrzení o úspěšném SAM lint.
- Dokončit nezávislou kontrolu business/transaction correctness, pagination/serializace, IAM/scope a API kompatibility; finální předání rozliší skutečně spuštěné lokální důkazy od neprovedeného deploy/runtime/persistence smoke. Nespouštět cloud/HTTP testy ani při dostupných credentials, neměnit registry runner ani task lifecycle.

## Files
| Cesta | Konkrétní změna |
|---|---|
| `be-case-client/src/case_client_dynamodb_repository.py` | Nový injektovatelný adaptér, mapping/SDK serialization, bounded pagination/token a transakce |
| `be-case-client/src/case_client_repository.py` | Zachovaný Protocol/exceptions; přesun sdílené normalizace a čistá business pravidla |
| `be-case-client/src/case_client_mock_repository.py` | Import sdílených funkcí, zachované mock persistence/lock/fixtures/token chování |
| `be-case-client/src/case_client_handler.py` | Validace konfigurace/factory/cache, pravdivý marker, přesný JSON Decimal a sanitizované chyby |
| `be-case-client/src/requirements.txt`, `be-case-client/requirements-dev.txt` | Připnuté SDK/JSON runtime a dev dependencies pro native SAM build a offline testy |
| `be-case-client/tests/test_case_client_dynamodb_repository.py` | Nové adapter+handler SDK stub testy a kompletní matice |
| `be-case-client/tests/test_case_client_lambda.py` | Zachované mock behavior; cíleně aktualizovaný AST/no-SDK-init invariant |
| `be-case-client/tests/test_case_client_template.py` | Obě konfigurační/IAM větve, přesné externí-only resources a zachované gateway kontroly |
| `be-case-client/template.yaml`, `be-case-client/README.md` | Parametry/conditional IAM, SDK balení, konfigurace a oddělený budoucí host runbook |

## Progress
- [x] Získat kanonickou cestu pro `task-11fe7375-3c4e-4afe-b11b-cab49fc2c973` a přečíst existující rozpracovaný plán.
- [x] Prozkoumat komponentu, kontrakt, proposal a learnings; zkontrolovat basename a dostupné skilly.
- [x] Doplnit konkrétní implementační kroky, spustitelný TDD skeleton a ověřovací brány.
- [ ] Při implementaci provést RED/GREEN, lokální brány a nezávislé kódové kontroly.
