# Plan 2026-10-19: Case & Client — in-place Python deployment and live DB integration

## Progress
- [x] Určit kanonickou cestu plánu pro task-0c4b4cd5-64c3-4bb1-a2dd-a3f712a2fb3f.
- [x] Prozkoumat komponentu, kontrakt, dokumentaci a relevantní learnings.
- [x] Připravit implementační kroky, TDD a live přejímku; předat k nezávislému schválení.
- [x] Opravit kanonický úvod a přesné sekce; převést HTTP/offline scénáře na1.4.0. Pro runtime proof provést až implementační fázi a nezávislou přejímku.

## Analysis
- Rozšířit jedinou komponentu `be-case-client/`: zachovat REST proxy, strong GetItem, transakční kontrolu active klienta + conditional Put, GSI Query a query-bound opaque token; v existujícím handleru odstranit veřejné caller-ID/replay chování.
- Použít připnuté `src/requirements.txt`, zejména binární `simplejson==3.20.2`; nepovažovat macOS nativní SAM build za Linux artefakt.
- Sjednotit skutečný zdrojový rozpor před deployem: OpenAPI je 1.4.0, ale aktuální `_request` handleru vyžaduje caller `case_id` a vrací replay200. Implementovat serverové UUIDv4/plain-create a aktualizovat staré README; veřejný kontrakt nesnižovat na 1.3.0.
- Respektovat learnings: statické SAM kontroly nejsou runtime proof; zachovat mock bezpečnostní invarianty a offline SDK testy. Recall: local, collection wonderfulkb-learnings, diagnostic Collection not found; fallback úspěšný.
- Nevytvářet nový architektonický diagram: v repozitáři nebyl nalezen `*.puml`; architekturu číst z README, OpenAPI a proposalu.
- Zachovat regresní ochrany z `learnings/runtime-errors/rules-case-client-{cursor-json-depth,dynamodb-decimal-range,normalize-filter-once}.md`: hluboký token →400, Decimal bez ztráty a normalizace filtru právě jednou. Mock nepoužít jako důkaz persistence.
- Použít `docs/proposals/proposal-20261019-114433-08800d_case-client-lambda-vyvoj-nezavisly-na-externi-databazi.md`, sekce `db-connection`/`deployed-integration`; starší host-only instrukce nahradit pouze v autorizovaném rozsahu tohoto tasku.
- Použít nové názvy níže: průzkum basename kolize nenašel. Zachovat `unittest`/Stubber, explicitní fake credentials a zákaz socket/DNS z `tests/test_case_client_dynamodb_repository.py`.
- Opravit retry artefakt na této cestě: první řádek přesně `# Plan 2026-10-19: …`, pouze povolené `##` nadpisy; nepoužít historický plán jako přejímku 1.4.0. Existující test `test_post_generates_new_uuid_and_ignores_supplied_case_id` zachovat; staré replay testy cíleně převést na plain-create, ne odstranit sadu.

## Approach
- Připravit pouze plán; cloudové mutace zahájit až při implementaci schváleného plánu.
- Použít skilly `tdd` pro RED/GREEN, `validate-implementation` pro závěrečnou kontrolu kontraktu, `code-review` a `write-review-report` pro nezávislé review, `save-learning` jako poslední dokončovací krok. Před psaním boto3 načíst `aws-sdk-python-usage`; před scoped IAM změnou `aws-iam`.
- AWS práci vést přes oficiální AWS MCP (`run_script`, pro lokální soubory podporovaný transfer); nepoužívat AWS CLI přes Bash. Při implementaci nejprve ověřit, že dostupný transport umí požadovaný profil/identitu, privátní rollback download a SDK→HTTPS předání klíče bez jeho návratu do modelu. Pokud ne, uvést přesný blocker; neobcházet guard ani zavádět nový S3 resource. Lokální build/offline příkazy oddělit od cloudových akcí.
- Nepoužívat Wonderful deploy ani git operace. Před implementací doložit existující feature-branch kontext z předaného stavu; pokud není dostupný nebo je vyžadována změna branche v rozporu se zákazem git operací, vyžádat vyřešení hostem před zdrojovými změnami, neměnit branch politiku.

## Implementation
1. **Nejdříve RED:** doplnit existující handler test a dva offline soubory podle TDD; bez produkčních změn prokázat očekávané selhání. Zachytit baseline komponentové/registrované brány včetně již existujícího UUID testu; rozporné replay testy převést na 1.4.0 se zachováním ochrany metadat, transakcí a mock izolace. Použít Python `/Users/michal/.local/bin/python3.13`, privátní `mkdtemp` pod `/tmp` mode700, soubory600, venv s `requirements-dev.txt`; bez čtení credential souborů.
   - **Sjednotit zdrojový kontrakt před buildem:** po RED upravit `_request`/POST flow: validovat client_id/metadata, caller case_id vůbec nepoužívat, přidělovat UUIDv4 na serveru a každému úspěšnému POST vracet201. Zachovat repository hranici; generované kolize řešit nejvýše3čerstvými UUID, conditional Put + strong read-back, nikdy nevydat existující case jako replay/owner409. Vyčerpání →sanitizovaná500; chyby/timeouty SDK automaticky neopakovat. Otestovat skutečný handler s mockem i Stubberem; nevnášet pátou routu ani rozšiřovat CaseDetails mimo zadání. Pokud sjednocení mezitím dodal předchozí task, nejprve je ověřit a neduplikovat.
2. **Read-only preflight:** přes standardní chain profilu `ai-hackathon` ověřit STS účet `609394381050` a efektivní region všech klientů `eu-central-1`. Describe/Get cílové funkce `arn:aws:lambda:eu-central-1:609394381050:function:wonderfulkb-case-client`, code/config/RevisionId, role a resource policy. Vypisovat pouze allowlist nesekretných polí; raw env zůstanou soukromé. Zkontrolovat Zip/x86_64, role `arn:aws:iam::609394381050:role/wonderfulkb-lambda-role`, všechny uživatele role přes paginovaný ListFunctions a potřebné inline/managed policy dokumenty. Neshodu či dalšího uživatele role před její změnou označit BLOCKED.
3. **Zmapovat původní gateway:** pro REST API `bgm7k1ggqi`/stage `v1` načíst resources, čtyři methods/integrations, stage deployment, API-key requirements, usage plans/throttles a Lambda invoke vazbu. Vyžadovat AWS_PROXY REST eventy a URI přímo na tutéž nealiasovanou Lambdu pro GET `/clients`, POST `/cases`, GET `/cases/{case_id}`, GET `/clients/{client_id}/cases`. Správný existující key ID zjistit z usage-plan vazby (kandidáti `16u2jtkay6`, `b0w43mx5vf`); hodnotu získat až uvnitř procesu runneru a nikdy nevrátit z nástroje. Načítání usage-plan keys může také obsahovat value: redigovat ještě před serializací výstupu.
4. **Ověřit tabulky a tvary:** DescribeTable pouze `wonderfulkb-uw-clients` (PK client_id S, ico-index/ico S/ALL) a `wonderfulkb-uw-cases` (PK case_id S, client-created-index/client_id S+created_at S/ALL). Cíleným Get/Query s ProjectionExpression ověřit pouze známé syntetické položky, UTC timestamp, statusy a metadata; bez scan dumpů. Chybějící známé syntetické IDs neřešit čtením reálných dat; potřebná data dodat odděleným provisioningem v kroku 8.
5. **Implementovat deploy nástroj:** `tools/case_client_test_deploy.py` s explicitními operacemi preflight/build/deploy/verify/rollback a injektovatelnými SDK/transport/clock. Import ani výchozí spuštění nic nemutují. Idempotentní opakování již shodného hashe/config je no-op, souběžný cizí RevisionId stop. Před KAŽDOU skupinou IAM/Lambda/gateway/fixture mutací opakovat account/region/target guard; žádné rozšiřování lokálních credentials. AccessDenied/expirace SSO →nonzero BLOCKED s action/ARN, bez loginu.
6. **Snapshot a build před první mutací:** uložit původní Zip, kompletní vratnou konfiguraci včetně code/runtime/handler/env/role a snapshot pouze případně měněných IAM/API údajů do privátního rollback adresáře; download URL používat pouze v paměti, ověřit base64 SHA256 Zip proti CodeSha256. Zip stáhnout i pro původní rollback, ne pouze odkaz. Sestavit deterministický Zip ze `src/` bez cache/testů a ze všech připnutých dependencies pomocí pip target pro CPython3.13/manylinux2014_x86_64 (`--only-binary=:all: --implementation cp --python-version 3.13 --abi cp313 --platform manylinux2014_x86_64`); validovat wheel tagy a ELF x86_64 u simplejson, odmítnout Mach-O/arm64. Při chybě wheelů stop, ne použít macOS venv. Ověřit kořen handleru, manifest závislostí, deterministický hash a přímý SDK Zip upload pod limitem včetně base64 režie; žádný S3/CFN stack. SAM lint zachovat samostatně; `sam deploy` nepoužít.
7. **In-place cutover:** pokud skutečně chybí oprávnění, přidat jedinou vlastní pojmenovanou inline policy na přesné nutné ARN (typicky pouze `dynamodb:ConditionCheckItem` na `arn:aws:dynamodb:eu-central-1:609394381050:table/wonderfulkb-uw-clients`). Předem ověřit nekolidující název, nezasahovat do `dynamodb-access`, trust ani managed policies. Použít UpdateFunctionCode →waiter →čerstvý RevisionId →UpdateFunctionConfiguration →waiter; nastavit `python3.13`, `case_client_handler.lambda_handler`, DATA_BACKEND=dynamodb, ALLOW_EPHEMERAL_MOCK=false a čtyři table/index env z README. Sloučit s existujícími nesouvisejícími env, role zůstává původní; `AWS_REGION` je rezervovaná automatická runtime proměnná, nezapisovat ji. Re-read region ověřit z ARN/SDK/runtime evidence. Drobné gateway opravy jen na těchto čtyřech metodách po přesném snapshotu, včetně nutného stage deploymentu a vratné stage vazby; neměnit auth, usage plan ani throttles. Nepotřebná gateway mutace se neprovádí.
8. **Provisioning oddělit od HTTP testů:** explicitní write opt-in + run_id; nejvýše4nové clients (2active, inactive, blocked), validní UUID odvozená z run_id, unikátní osmimístná syntetická IČO a společný run-name s diakritikou/právní formou, `source=synthetic`. Cíleně ověřit ico-index, při kolizi vybrat jiné IČO; PutItem vždy `attribute_not_exists(client_id)`. Re-run čte manifest a ověřuje pouze vlastní IDs, nic nepřepisuje. Částečné/nejisté inserty evidovat a před pokračováním cíleně ověřit; AccessDenied →BLOCKED. Cases pouze HTTP: plánovat7úspěšných POST (první, repeat, caller-ID ignored, dva same-client concurrent, dva cross-client concurrent); sdílený limit12nových cases/run včetně všech iterací a nejednoznačných zápisů. Změnou run_id neobcházet budget; po jeho vyčerpání stop. Ponechané IDs zapisovat průběžně, bez cleanupu.
9. **Implementovat HTTP runner:** `tests/integration/case_client_api_integration.py`, import-safe, explicitní `main`, read-only default, write profil pouze `--allow-writes --run-id ...` a očekávaný dynamodb backend. Ověřit přesný HTTPS host/stage `https://bgm7k1ggqi.execute-api.eu-central-1.amazonaws.com/v1`, account/region a deployment hash ještě před credentials requestem/POST. SDK získá klíč přímo do HTTP transportu, případně env pouze uvnitř procesu; žádná hodnota v argv/souboru/logu. Zakázat redirects a HTTP/SDK debug; všechny výjimky/reporty přes allowlist/redakci před tiskem. Nepřijímat libovolný endpoint.
10. **Ohraničit runner:** globální budget240HTTP requestů/run včetně retries/auth probes/iterací, connect/read timeout3/10s, deadline10min na průchod v rámci60min celkem, max2workers a sdílené tempo≤2req/s (párové race rezervují obě místa). GSI poll deadline≤60s i page cap/cycle detection sdílí request budget. POST nikdy automaticky neopakovat: při timeoutu/5xx známé vrácenéID ověřit cíleným GET; bezID jen bounded list vlastního syntetického klienta/run_id. Okamžitá absence v GSI nedokazuje nezápis; nevyřešená nejistota →nonzero BLOCKED, chybějící fixtures →NOT_READY, assertion chyba →FAIL. Potenciální zápis rezervuje case budget. Read-only subset není plná přejímka.
11. **Provést a opakovat:** verify CodeSha256/runtime/handler/env/role/table/index/API binding před testy, spustit plný profil z Testing. Při chybě v povoleném kódu přidat offline reprodukci, opravit, opakovat offline gates→Linux build→guarded deploy→live. Nejvýše5mutačních deploy pokusů a60min live ladění celkem v tomto implementačním tasku; počítat i částečně neúspěšný cutover, nepřidávat automatické nekonečné pokračování. Při prokázaně unhealthy deployi obnovit bezpečný baseline před další přípravou; při vyčerpání obnovit předchozí zdravou variantu, pokud aktuální není zdravá.
12. **Rollback ověřit:** guarded obnovení původního Zip/runtime/handler/env/role se stejnými waitery/RevisionId kontrolami; vrátit pouze vlastní IAM delta a případné vlastní gateway změny, ne celou sdílenou roli. Nepřepsat neočekávanou souběžnou změnu ani při rollbacku; reportovat blocker. Ověřit obnovený hash/config a dostupnost; žádné DB deletes ani cleanup. Rollback původního Node není úspěch nasazení Pythonu.
13. **Uzavřít důkazy:** po HTTP testech znovu GetFunction a porovnat CodeSha256 s testovaným artefaktem. Do `plans/checkpoints/case-client-live-integration/` uložit sanitizovaný deployment manifest, run report všech povinných scénářů, fixture IDs, iterace/opravy, časy/exit codes a rollback metadata (cesta a hash, žádný raw obsah). Aktualizovat komponentové README příkazy a výsledky, zachovat samostatnou SAM šablonu. Zachovat nezávislou přejímku a registrované gates; finální poznámka oddělí offline/live výsledky a uvede cloud/code diff, příkazy bez secretů, hash před/po, počet pokusů, ponechané IDs, rollback cestu a konkrétní případné action/ARN blockery. Nakonec skill `save-learning` uloží poznatek z implementace.

## TDD
- Implementace TDD cyklu dle skill:tdd; nejdříve vytvořit pouze níže uvedené offline testy, zachytit RED, potom implementovat a zachytit GREEN. RED nesmí být jen ImportError: importlib ověří existenci zamýšleného modulu assertionem a následně skutečné fail-closed chování. Důkazy ukládat pod `plans/checkpoints/case-client-live-integration/`.
- Do existující třídy `CaseClientLambdaTests` v `be-case-client/tests/test_case_client_lambda.py` přidat následující metodu (používá reálné importy/fixture setup tohoto souboru):
```python
    def test_plain_create_without_caller_id_is_never_replayed(self):
        body = {'client_id': ACTIVE, 'metadata': {'nested': {'ok': True}}}
        first = self.invoke('POST', '/cases', body=body, expected=201)
        second = self.invoke('POST', '/cases', body=body, expected=201)
        self.assertEqual(UUID(first['case_id']).version, 4)
        self.assertEqual(UUID(second['case_id']).version, 4)
        self.assertNotEqual(first['case_id'], second['case_id'])
        self.assertEqual(self.invoke(resource='/cases/{case_id}',
            params={'case_id': first['case_id']}), first)
```
- Focused handler command: `PYTHONPATH=be-case-client/src:be-case-client/tests "$VENV/bin/python" -m unittest test_case_client_lambda.CaseClientLambdaTests.test_plain_create_without_caller_id_is_never_replayed -v`.
- Nový `be-case-client/tests/test_case_client_test_deploy.py` (unittest; kontrakt guardu nesmí potřebovat credentials):
```python
import importlib.util
from pathlib import Path
import unittest

class DeployTargetTests(unittest.TestCase):
    def test_wrong_account_fails_before_mutation(self):
        path = Path(__file__).resolve().parents[1] / 'tools/case_client_test_deploy.py'
        self.assertTrue(path.is_file(), 'missing guarded deploy tool')
        spec = importlib.util.spec_from_file_location('case_client_test_deploy', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        mutations = []
        class FakeSDK:
            def get_caller_identity(self):
                return {'Account': '000000000000'}
        with self.assertRaises(module.TargetMismatch):
            module.guarded_mutation(sts=FakeSDK(), region='eu-central-1',
                function_arn='arn:aws:lambda:eu-central-1:609394381050:function:wonderfulkb-case-client',
                mutation=lambda: mutations.append('write'))
        self.assertEqual(mutations, [])
```
- Nový `be-case-client/tests/test_case_client_api_integration.py` (unittest; transport injektovatelný, no real network):
```python
import importlib.util
from pathlib import Path
import unittest

class LiveWriteGuardTests(unittest.TestCase):
    def test_default_profile_rejects_post_before_transport(self):
        path = Path(__file__).resolve().parent / 'integration/case_client_api_integration.py'
        self.assertTrue(path.is_file(), 'missing explicit live runner')
        spec = importlib.util.spec_from_file_location('case_client_api_integration', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        calls = []
        runner = module.CaseClientApiRunner(
            base_url='https://bgm7k1ggqi.execute-api.eu-central-1.amazonaws.com/v1',
            transport=lambda *a, **kw: calls.append('network'))
        with self.assertRaises(module.WritesNotAllowed):
            runner.request('POST', '/cases', body={})
        self.assertEqual(calls, [])
```
- Focused command z kořene s připraveným privátním venv: `PYTHONPATH=be-case-client/src "$VENV/bin/python" -m unittest discover -s be-case-client/tests -p 'test_case_client_test_deploy.py' -v` a totéž s `-p 'test_case_client_api_integration.py'`.

| Test | RED před implementací | GREEN |
|---|---|---|
| test_plain_create_without_caller_id_is_never_replayed |400 místo201 (handler vyžaduje case_id) |201+201, různá UUIDv4, přesný GET |
| test_wrong_account_fails_before_mutation | missing guarded deploy tool | TargetMismatch, nula mutací |
| test_default_profile_rejects_post_before_transport | missing explicit live runner | WritesNotAllowed, nula HTTP volání |

- Rozšířit fake SDK/HTTP testy: region/ARN/account guard, no-op deploy, env merge bez rezervovaného AWS_REGION, Linux wheel/Zip limit/hash, download hash mismatch před mutací, waitery/RevisionId konflikt/scoped rollback, policy kolize,5pokusů/60min,4clients/12cases a240requests napříč iteracemi, fixture resume/AccessDenied, key redakce včetně výjimek/usage-plan response, no-redirect bez druhého requestu, sdílený budget2workers, GSI60s timeout, token cyklus a ambiguous POST se známým i neznámýmID→žádný retry/nonzero BLOCKED. Doplnit server-ID kolize, nested Decimal roundtrip a odmítnutí inactive/blocked bez zápisu. Zakázat socket/DNS, žádné skutečné SSO.

## Testing
- Spustit baseline i finální `PYTHONPATH=be-case-client/src "$VENV/bin/python" -m unittest discover -s be-case-client/tests -p 'test_*.py' -v`; runner nesmí mít jméno test_ ani import-time cloud efekty.
- Spustit `PYTHONPYCACHEPREFIX="$PRIVATE_DIR/pycache" "$VENV/bin/python" -m compileall -q be-case-client/src be-case-client/tests be-case-client/tools`.
- Spustit `SAM_CLI_TELEMETRY=0 /Users/michal/.local/bin/sam validate --lint --template-file be-case-client/template.yaml` s offline fake credentials/metadata disabled; lint není deployment evidence.
- Zachovat přesný registrovaný gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` (timeout300s). Unrelated frontend failure uvést s příkazem/exit code; frontend neopravovat a gate neobcházet.
- Provést živé scénáře přes původní API s deployment identity + `X-Data-Backend: dynamodb`; každý scénář musí mít status/assertions/outcome/run_id, ne pouze aggregate PASS:

| Scénář | Povinný důkaz |
|---|---|
| Auth a response kontrakt | Bez/s chybným klíčem403; JSON/error string dle OpenAPI, žádný redirect; app odpovědi mají DB marker, gateway auth chyby jej nepotřebují |
| Clients filters | Přesné IČO, name diakritika/case/právní forma, status a všechny AND kombinace včetně neshody; veřejné typy a allowlist bez interních atributů |
| Chybové reads/requests |400invalid IČO/name/status/limit0/101/nečíselný/token;404unknown case i unknown client list;400invalid POST; chybové tělo odpovídá kontraktu |
| Plain-create a persistence |POST bez case_id→201, serverové UUIDv4→okamžitý strong GET se shodou veřejných polí/nested/Decimal/null/bool metadata. Totožný POST→další201/jinéUUID; další POST s caller case_id→201/jinéUUID než caller; všechny ověřit GET |
| Business negatives |Unknown klient404, inactive/blocked409 bez zápisu. U existujících vlastních inactive/blocked před/po bounded GSI konvergenci prázdné cases; unknown-client list404. Offline Stubber doloží žádný write. Neověřovat neexistenci pomocí ignorovaného caller-ID ani ji netvrdit pouze z okamžité absence v GSI |
| Pagination |Nejméně2own cases stejného klienta; po bounded GSI konvergenci limit1, další stránky bez ztrát/duplicit/cyklů, newest-first bez neexistujícího tie-break slibu; clients limit1 přes společný run-name filtr zachytí všechny4fixtures |
| Query-bound token |Reálný vrácený next_token při změně filtru/limitu/klienta400; nezavádět nový veřejný token formát ani total count |
| Souběh stejný klient |Dva současné POST téhož active klienta→201+201/různá serverová UUIDv4; oběID přes GET se shodnými poli |
| Souběh různí klienti |Stejné caller case_id, dva různí active klienti→201+201/různá UUIDv4 odlišná od callerID; oba GET patří správnému klientovi/metadata, žádný owner409 |
| Identita po testech |CodeSha256 před/po = hash nahraného Zip; python3.13/handler/role/tabulky/indexy/původní API potvrzené |

- Success vyžaduje celý write profil, všechny offline/registrované brány a nezávislé review; žádný green skip při NOT_READY/BLOCKED, žádný429flood. Nové HTTP spojení není důkaz nové execution environment.

## Files
| Cesta | Plánovaná změna |
|---|---|
| `be-case-client/tools/case_client_test_deploy.py` | Nový scoped deploy/build/rollback/preflight a oddělený fixture provisioning |
| `be-case-client/tests/integration/case_client_api_integration.py` | Nový explicitní bezpečný HTTP runner/report |
| `be-case-client/tests/test_case_client_test_deploy.py` | Offline SDK/build/rollback/guard testy |
| `be-case-client/tests/test_case_client_api_integration.py` | Offline transport/redakce/budget/scénáře |
| `be-case-client/src/case_client_handler.py`, `src/case_client_dynamodb_repository.py`, `src/case_client_repository.py` (v komponentě) | Sjednotit zjištěný rozpor plain-create/UUIDv4; další opravy jen s regresním důkazem, zachovat jediný backend |
| `be-case-client/src/case_client_mock_repository.py`, `be-case-client/events/create-case.json` | Sjednotit existující mock/POST event s plain-create; zachovat backend bezpečnostní invarianty |
| `be-case-client/tests/test_case_client_{lambda,dynamodb_repository,template}.py` | Zachovat ochrany, sjednotit veřejné replay testy na 1.4.0, přidat UUID/collision/Decimal regresní testy |
| `be-case-client/README.md` | Přesný in-place runbook, offline/live příkazy, limity, rollback, interpretace důkazů |
| `be-case-client/src/requirements.txt`, `requirements-dev.txt`, `template.yaml` (v komponentě) | Jen nutná kompatibilita balení/opravy, bez nového vlastnictví existující API a bez změny OpenAPI kontraktu |
| `plans/checkpoints/case-client-live-integration/` | Sanitizované RED/GREEN, deployment/HTTP/fixtures/iterations/rollback metadata a review evidence |
