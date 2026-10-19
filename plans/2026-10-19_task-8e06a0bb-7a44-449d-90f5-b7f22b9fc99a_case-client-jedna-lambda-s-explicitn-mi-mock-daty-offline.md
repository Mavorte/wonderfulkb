# Plan 2026-10-19: Case & Client — explicit mock Lambda

## Analysis
- Zachovat `be-case-client/openapi-case-client.yaml` 1.3.0-final beze změny; komponenta nyní obsahuje pouze tento kontrakt, žádné Python soubory ani duplicitní požadované basename nebyly nalezeny.
- Řídit se `docs/proposals/proposal-20261019-114433-08800d_case-client-lambda-vyvoj-nezavisly-na-externi-databazi.md`, sekcemi decisions/lambda-mock; z `plans/case-client-aws.md` nepřebírat DB, boto3, seed, Docker ani globální idempotenci.
- Použít pouze case status `open`; fixtures rozlišit časy a klientskými stavy. Dokumentovat 400 pro neplatné path ID i u detailu case, kde původní OpenAPI 400 nevyjmenovává.
- Navázat na `apps/backoffice/package.json`: `test` je Vitest, `build` je TypeScript + Vite; zachovat registrovanou frontendovou bránu z dodaného snapshotu.
- Při implementaci opakovat kontrolu duplicit basename; nebyly nalezeny projektové AGENTS.md/CLAUDE.md ani PlantUML diagramy. Aplikovat `learnings/architecture/decisions-case-client-mock-fixture-pagination.md`: fixture smoke a kurzory přenositelné mezi čistými repository, nikoli slib sdílené persistence. Recall: backend `local`, collection `wonderfulkb-learnings`, diagnostic `Collection not found: wonderfulkb-learnings`.
- Zachovat při opravě retry hlavičku `# Plan 2026-10-19: …` dle compound-plan a pouze přesné povolené `##` nadpisy; původní artefakt byl odmítnut jako `invalid_header`. Nezapisovat task lifecycle ani externí registry; kanonickou cestu evidovat odkazem na tento plán.

## Approach
- Omezit zdrojové změny na `be-case-client/**`; zjistit `python3 --version`, použít stdlib kompatibilní s dostupným lokálním Pythonem a runtime Python 3.13, bez instalačních závislostí. Nepoužívat runtime-only API, která brání lokální offline bráně.
- Vytvořit `create_handler(repository=None)` a veřejný `lambda_handler(event, context)` ve stejném modulu; produkční vstup lazy inicializuje jedinou konfigurací povolenou repository pro execution environment, testy injektují skutečný mock adaptér.
- Použít malé `typing.Protocol` repository se čtyřmi operacemi a konkrétními doménovými výjimkami; validaci HTTP a veřejnou serializaci ponechat handleru, atomické create/repeat/conflict adaptéru. Nepřidávat další aplikační vrstvu.
- Použít `skill:tdd` pro implementaci, `skill:validate-implementation` pro závěrečné ověření rozsahu a kontraktu a `skill:save-learning` pro závěrečný poznatek; žádný z těchto kroků nyní neprovádí implementaci.

## Implementation
1. Nejprve přidat testovací soubor dle TDD níže a zaznamenat RED; před vytvořením každého dalšího souboru ověřit jeho basename přes glob v celém repozitáři. Existující cizí změny zachovat. V tomto planning runu měnit pouze kanonický plán a povinný learning.
2. Přidat `src/case_client_fixtures.json`: minimálně dva aktivní klienty pro stránkování, inactive, blocked a klienta bez cases; stabilní UUID, syntetická osmimístná IČO včetně počáteční nuly (validní kontrolní číslice), `source: synthetic`, názvy s diakritikou a variantami `s.r.o.`/`a.s.`. Zabalit více známých `open` cases s různými UTC časy a jeden původní case neaktivního klienta pro kontrolu precedence opakování; používat pouze vymyšlené firemní údaje, případně rezervované `.example` kontakty.
3. Definovat čtyřoperační repository Protocol a doménové chyby v `case_client_repository.py`; implementovat `MockCaseClientRepository` s hlubokou kopií fixtures i vstupních/výstupních metadata. Fixture cestu odvodit od `__file__`, nikoli pracovního adresáře. Jeden `threading.Lock` chrání rozhodnutí existující ID → vlastník → existence/stav klienta → zápis; souběžná stejná ID nesmějí vytvořit dva cases.
4. V `case_client_handler.py` povolit factory pouze při přesných `DATA_BACKEND=mock` a `ALLOW_EPHEMERAL_MOCK=true`, i při injekci adaptéru. Jinak vyvolat jasnou konfigurační chybu; veřejný Lambda vstup ji mapuje na JSON 500. Lazy cache drží stav pouze v jednom execution environmentu; nic nepíše do `/tmp`, nepoužívá SDK, credentials ani síť. Neočekávanou provozní chybu mapovat na sanitizovanou 500, nikdy prázdný seznam/200. Mock hlavičku dávat všem odpovědím inicializovaného mock handleru, včetně chyb; neoznačovat neaktivovaný backend falešně za mock.
5. Routovat podle REST proxy `httpMethod`, `resource`/`pathParameters` (a skutečného `path` pro přímé eventy), query číst jako stringy; zachovat JSON `body` jako string a `Content-Type: application/json`. Implementovat přesně čtyři routy; neznámé routy/metody vracejí konzistentní JSON 404/405. API klíč neověřovat v handleru, vlastní jej gateway. Podporovat validní base64 tělo přes `isBase64Encoded`, vadné tělo odmítnout 400; nedumpovat eventy/klíče do logů.
6. Validovat objekt JSON, povinné stringy, case ID fullmatch `[A-Za-z0-9._-]{1,128}`, UUID, metadata objekt a nejvýše 16384 bajtů `json.dumps(metadata, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')`; odmítnout neplatný JSON a nestandardní NaN/Infinity. Query: IČO přesně osm číslic, name délka 2–255 a neprázdný po normalizaci, přesné status enumy, limit celé číslo 1–100/default 50; chybné hodnoty →400. Nezpřísňovat další vlastnosti requestu proti OpenAPI bez zdokumentovaného důvodu.
7. `GET /clients`: kombinovat filtry AND; `unicodedata` + casefold odstraní diakritiku, sjednotí mezery a odstraní běžné právní formy jako celé výrazy (včetně teček/mezer a dlouhých českých forem), ne podřetězce běžných slov. Stejnou normalizaci použít na dotaz i jméno. Po filtrovaní stránkovat ve stabilním pořadí `client_id`; vracet pouze explicitní veřejný allowlist Client a vnořených schémat, žádné interní atributy.
8. Použít malý verzovaný base64url JSON kurzor: přesné schema, fingerprint endpointu/client ID/normalizovaných filtrů/limitu a poslední veřejné ID v deterministicky seřazeném výsledku. Omezit délku, striktně validovat base64/UTF-8/JSON/schema/verzi/typy, vazbu dotazu i existenci kurzoru v daném výsledku; vadný nebo cizí token →400. Token je neprůhledné klientské rozhraní, nikoli autentizace/šifrování; nevyžadovat instance-local secret, který by rozbil stránkování neměnných fixtures mezi instancemi. Vrátit `next_token: null` na konci; token není snapshot a pro ephemeral nově vytvořená data nemusí po resetu fungovat. Implementovat přímo v doménovém modulu, ne token framework.
9. `POST /cases`: po validaci nejprve pod zámkem vyhodnotit existující ID: stejný klient →200 s původními metadata/časem i pro nyní inactive/blocked klienta, jiný klient →409; teprve pro nové ID kontrolovat klienta (404/409), vytvořit `open` s UTC `created_at` a vrátit 201. `GET /cases/{case_id}` →200/404; seznam klientových cases nejprve existence klienta →404, jinak `client_id`, `cases`, `next_token`, filtr pouze `open`, čas sestupně a case ID jako stabilní tie-break, bez cases prázdný seznam.
10. Přidat `template.yaml` v JSON syntaxi (platná podmnožina YAML, dlouhé formy `Ref`/`Fn::Sub`/`Fn::GetAtt`), aby stdlib `json` umožnila skutečné strukturální testy bez PyYAML. Jedna `AWS::Serverless::Function`: `CodeUri: src/`, `Handler: case_client_handler.lambda_handler`, `Runtime: python3.13`, 256MB/10s, on-demand, explicitní mock env. Jedna `AWS::Serverless::Api`, REST stage `v1`, přesně čtyři explicitní `Api` events odkazující na stejné API; globální `Auth.ApiKeyRequired: true`, žádná route jej nevypíná.
11. Ve stejné šabloně vytvořit explicitní ApiKey, UsagePlan a UsagePlanKey; UsagePlan stage navázat na SAM generovaný stage resource, aby závislost nevytvářela race při deployi. API Gateway responses `INVALID_API_KEY`, `ACCESS_DENIED`, `DEFAULT_4XX`/403 a `THROTTLED`, `QUOTA_EXCEEDED`/429 s JSON `{"error":"..."}`. Jeden log group s retention 7 dní a role s Lambda trust a pouze `logs:CreateLogStream`/`logs:PutLogEvents` na jeho stream ARN; nevytvářet DB/S3/VPC/pipeline/custom resources ani další stacky. Vyhnout se kruhové závislosti log group/function/role. Tagovat podporované prostředky `project=wonderfulkb` (API Gateway Tags map dle resource typu); outputs pouze URL včetně `/v1`, jméno funkce, API/klíč/usage-plan ID, nikdy hodnota klíče.
12. Přidat čtyři REST proxy JSON eventy do `events/` pro všechny operace, s konkrétními fixture UUID/case ID a POST s novým ID. Do README vložit přesný přímý Python příkaz z kořene, který nastaví obě mock proměnné, vloží `be-case-client/src` přes `sys.path.insert`, načte zvolený event a zavolá `lambda_handler`; nic nesmí vyžadovat globální PYTHONPATH, SAM, Docker, server nebo přihlášení.
13. README označit jako ephemeral demo: reset při cold startu, rozdílná data instancí, pouze lokální idempotence, stránkování bez snapshot záruky, metadata 16KiB a 400 odchylka detailu. Uvést přesné offline příkazy níže a oddělený host runbook: `sam validate --lint --template-file be-case-client/template.yaml`, poté `sam deploy --guided --profile ai-hackathon --region eu-central-1 --stack-name wonderfulkb-case-client-mock --template-file be-case-client/template.yaml --capabilities CAPABILITY_IAM`. Použít přímo CodeUri, bez `sam build`, dependencies či containerů; neukládat config/klíč do repozitáře.
14. Host runbook doplnit o získání API URL a nesekretních ID z outputs, získání klíče pouze do dočasné shell proměnné se zakázaným tracingem, žádný výpis/ukládání klíče nebo verbose curl. Smoke: platný klíč GET clients, GET známého zabaleného case, GET jeho klientových cases, nový POST/201, inactive POST/409, neexistující klient POST/404, bez klíče/špatný klíč 403; u Lambda úspěchů ověřit mock marker. Nepoužívat POST→GET ani opakovaný HTTP POST jako důkaz persistence/idempotence. Uvést `sam delete --stack-name wonderfulkb-case-client-mock --profile ai-hackathon --region eu-central-1` pouze pro hosta a jen tento stack.

## TDD
Implementace TDD cyklu dle skill:tdd. Jako první implementační krok vytvořit níže uvedený nový soubor, spustit RED, až potom doplnit produkční moduly a fixtures; zaznamenat RED/GREEN dle skillu. Chybějící import je úvodní diagnostika, nikoli dostatečný behaviorální RED: doplnit jen importovatelné factory/adaptér stubs, znovu spustit a zachytit selhání konkrétního assertion před implementací chování. Nyní skeleton pouze plánovat.

Test file: `be-case-client/tests/test_case_client_lambda.py`; framework: stdlib `unittest`; import path řeší samotný test, bez globálního PYTHONPATH. Přesný focused příkaz z kořene: `python3 -m unittest discover -s be-case-client/tests -p 'test_case_client_lambda.py' -v`.

```python
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from case_client_handler import create_handler
from case_client_mock_repository import MockCaseClientRepository

class CaseClientLambdaTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'DATA_BACKEND': 'mock', 'ALLOW_EPHEMERAL_MOCK': 'true'
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.repository = MockCaseClientRepository()
        self.handler = create_handler(repository=self.repository)

    def invoke(self, method, resource, body=None, query=None, params=None):
        return self.handler({
            'httpMethod': method, 'resource': resource, 'path': resource,
            'pathParameters': params, 'queryStringParameters': query,
            'body': None if body is None else json.dumps(body),
            'isBase64Encoded': False,
        }, None)

    def test_clients_have_public_shape_and_mock_marker(self):
        response = self.invoke('GET', '/clients')
        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(response['headers']['X-Data-Backend'], 'mock')
        self.assertEqual(response['headers']['Content-Type'], 'application/json')
        clients = json.loads(response['body'])['clients']
        self.assertGreater(len(clients), 0)
        self.assertTrue(all('name_normalized' not in c for c in clients))

    def test_repeat_preserves_original_case_and_new_repository_resets(self):
        clients = json.loads(self.invoke('GET', '/clients')['body'])['clients']
        active = next(c for c in clients if c['status'] == 'active')
        request = {'case_id': 'case-offline-red',
                   'client_id': active['client_id'], 'metadata': {'note': 'první'}}
        first = self.invoke('POST', '/cases', body=request)
        request['metadata'] = {'note': 'jiné'}
        repeat = self.invoke('POST', '/cases', body=request)
        self.assertEqual(first['statusCode'], 201)
        self.assertEqual(repeat['statusCode'], 200)
        self.assertEqual(json.loads(first['body']), json.loads(repeat['body']))
        self.handler = create_handler(repository=MockCaseClientRepository())
        missing = self.invoke('GET', '/cases/{case_id}',
                              params={'case_id': 'case-offline-red'})
        self.assertEqual(missing['statusCode'], 404)
        self.assertIsInstance(json.loads(missing['body'])['error'], str)
```

| Test | RED | GREEN |
|---|---|---|
| `test_clients_have_public_shape_and_mock_marker` | Chybějící modul/export; po zavedení minimálního vstupu nesplněný 200/marker/seznam | 200, JSON, neprázdní syntetičtí klienti, mock marker, bez interního pole |
| `test_repeat_preserves_original_case_and_new_repository_resets` | Chybějící adaptér nebo nefunkční create/repeat/reset | 201→200, nezměněná metadata i čas, nová repository vrátí 404 |

Rozšířit stejný integrační suite o další acceptance případy níže; nesimulovat obě strany rozhraní mocky. Pro provozní 500 lze navíc použít malý selhávající repository double, hlavní suite musí používat reálný adaptér.

## Testing
- Pokrýt handler + skutečný adaptér pro čtyři routy: známé fixtures, nově vytvořený detail ve stejné repository, prázdný/neexistující klient, neexistující case, chyby `{"error": string}`, JSON string body a mock hlavičku i na aplikačních chybách.
- Tabulkově ověřit AND IČO/název/status, diakritiku/casefold, právní formy jako celá slova a nepoškození podobných běžných slov, IČO s nulou, name 1/2/255/256 i prázdný po normalizaci; oba status enumy, limit 0/1/50/100/101/neinteger, více stránek, konečný null, chybný/příliš dlouhý/cizí token, neexistující kurzor i změněný limit, endpoint a client ID. Token nad neměnnými fixtures ověřit i v nové repository.
- Ověřit časové řazení včetně shody časů, platné UUID/case ID i hraniční délky, chybějící pole, neobjektový JSON/metadata, prázdný/vadný/base64 JSON, UTF-8 metadata přesně na 16KiB a nad limitem, NaN/Infinity. Ověřit veřejný allowlist a vnořená data, nikoli jen nepřítomnost jediného interního klíče.
- Ověřit 201→200 s jinými metadata a identickým časem, 409 jiného vlastníka včetně neexistujícího klienta na již obsazeném ID, inactive/blocked→409, nový neexistující klient→404 a fixture case neaktivního klienta→200 při repeat. Použít `ThreadPoolExecutor` + bariéru pro dvě souběžná create stejného ID: právě jedno 201, zbytek 200 pro stejného vlastníka; rozdílní vlastníci 201/409. Ověřit izolaci hlubokých kopií i reset nové repository.
- V testech samostatně mazat/chybně nastavovat obě env hodnoty a ověřit fail-closed factory/JSON 500 veřejného vstupu. Ověřit import i obsluhu bez credentials: `patch.dict(..., clear=True)`, zákaz `socket.socket`/`socket.getaddrinfo` při importu i invokaci a AST kontrola src importů bez boto3/botocore/HTTP klientů. Nemockovat handler ani mock repository; žádné reálné síťové volání ani API key.
- Do `tests/test_case_client_template.py` přidat strukturální stdlib kontrolu `json.loads(template.yaml)`: allowlist typů prostředků (Function, Api, Role, LogGroup, ApiKey, UsagePlan, UsagePlanKey), přesně jedna funkce/API, runtime/CodeUri/env/limity, přesné čtyři REST routy odkazující na stejné API, účinná API key ochrana bez override, vazba usage plan/stage/key, JSON 403/429, krátká retence, pouze logové IAM actions/resources a žádné secret outputs. Statický test není důkaz běžící gateway.
- Spustit z kořene před implementací frontendovou baseline a po GREEN tyto brány; výsledky zapisovat přesně, ne odhadovat:

```bash
python3 -m unittest discover -s be-case-client/tests -p 'test_*.py' -v
python3 -m compileall -q be-case-client/src
npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build
sam validate --lint --template-file be-case-client/template.yaml
```

- SAM validaci spustit pouze je-li dostupné `sam`; při chybějícím SAM CLI uvést named blocker `AWS SAM CLI (sam)` a neoznačit validaci za splněnou. Unit testy/compileall na něm nezávisí. Případné chybějící frontend závislosti/nástroje reportovat přesně, bez přepisování konfigurace.
- Přes `skill:validate-implementation` ověřit diff pouze v komponentě, nezměněný zdrojový OpenAPI a absenci DB/cloud/config změn. Finální implementační poznámka uvede soubory, skutečné příkazy/výsledky, named blockers, ephemeral persistence a neprovedený deploy/smoke. Host následně skutečně validuje/deployuje a rozšíří registrovanou bránu o backend bez odstranění frontendu; worker registry nečte ani neupravuje.

## Files
| Cesta | Plánovaná změna |
|---|---|
| `be-case-client/src/case_client_handler.py` | Factory, Lambda vstup, routing, validace, normalizace, serializace a chyby |
| `be-case-client/src/case_client_repository.py` | Úzký Protocol a doménové výjimky |
| `be-case-client/src/case_client_mock_repository.py` | Izolované fixtures, atomické rozhodování, filtry/řazení/kurzory |
| `be-case-client/src/case_client_fixtures.json` | Zabalená syntetická data se stabilními ID |
| `be-case-client/tests/test_case_client_lambda.py` | Offline handler/adaptér acceptance a RED/GREEN |
| `be-case-client/tests/test_case_client_template.py` | Strukturální kontrola SAM přes stdlib JSON |
| `be-case-client/events/{list-clients,create-case,get-case,list-client-cases}.json` | Čtyři přímé REST proxy vstupy |
| `be-case-client/template.yaml` | Jediný minimální mock servisní stack, JSON-compatible YAML |
| `be-case-client/README.md` | Offline příkazy, limity a oddělený host runbook/smoke/cleanup |

## Progress
- [x] Získat kanonickou cestu plánu pro `task-8e06a0bb-7a44-449d-90f5-b7f22b9fc99a`.
- [x] Prozkoumat kontrakt, komponentu a relevantní learnings.
- [x] Doplnit konkrétní změny, TDD skeleton a ověřovací brány; opravit úvodní hlavičku po `invalid_header` a zachovat povolené sekce.
- [ ] Implementovat podle plánu, zachytit RED/GREEN a provést lokální brány v navazujícím tasku.
