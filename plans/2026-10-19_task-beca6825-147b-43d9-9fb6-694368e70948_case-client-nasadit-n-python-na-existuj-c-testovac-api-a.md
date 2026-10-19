# Plan: Case & Client acceptance repair

## Analysis
- Navázat na původní plán `plans/2026-10-19_task-0c4b4cd5-64c3-4bb1-a2dd-a3f712a2fb3f_case-client-nasadit-n-python-na-existuj-c-testovac-api-a.md`; dodržet cloudový rozsah `plans/tasks/2026-10-19_case-client-deploy-live-integration.md` a OpenAPI1.4.0 v `be-case-client/`.
- Zachovat již rozpracovaný POST201/server UUIDv4 v handleru, repository, mocku a Stubber testech. Commit `7281e61` obsahuje konsolidaci komponenty; aktuální UUID změny jsou navíc necommitnuté. Nezaměňovat jejich přítomnost za deploy proof.
- Doplnit čtyři dosud chybějící deploy/runner/test soubory uvedené ve Files. Z parent checkpointu převzít pouze skutečnou historii: 0 deploy, 0 HTTP, 0 fixtures, bez RED/GREEN; původní STS/lint úspěch neprokazuje runtime.
- Vyřešit před implementací hostem připravenou feature větev: checkout je `main` s cizími rozpracovanými změnami a původní brief zakazuje git operace. Zachovat všechny existující změny; přípravu feature kontextu zajistí host.
- Uplatnit `learnings/tooling/checklist-case-client-host-prerequisites-before-tdd.md` a `rules-case-client-minimal-live-deploy-plan.md`: ověřit skutečný bootstrap venv/dependencies, ne pouze verzi Pythonu; držet dva lineární nástroje. Parent hlásí ensurepip failure, chybějící boto3/simplejson a build bez esbuild.
- Použít načtená pravidla o Decimal, strong reads, conditional transakcích, jediné normalizaci filtrů a query-bound tokenech; historické replay200/owner409 formulace podřídit aktuálnímu kontraktu. Recall použil `local`, collection `wonderfulkb-learnings`, diagnostic `Collection not found`.
- Čerpat konfiguraci z README a db-connection/deployed-integration částí proposalu `docs/proposals/proposal-20261019-114433-08800d_case-client-lambda-vyvoj-nezavisly-na-externi-databazi.md`; nezahrnovat samostatné GET /cases rozšíření. PlantUML průzkum nic nenalezl.

## Approach
- Opravit finding-001 dvěma explicitně spouštěnými nástroji a dokončeným build→in-place deploy→live test→cílená oprava cyklem v jednom implementačním tasku; použít standardní knihovnu a připnuté SDK, bez nového frameworku/pipeline.
- Opravit finding-002 průběžným sanitizovaným manifestem a scénářovými výsledky s konečným runtime hashem; finding-003 skutečným focused RED/GREEN pro nové guardy. Úpravy již správné UUID implementace kvůli RED nepovolovat.
- Pro AWS použít oficiální AWS MCP. Ještě před první mutací ověřit dostupnou cestu pro lokální build artefakt, privátní Lambda Zip download a SDK-key→HTTPS v jednom procesu bez výpisu tajemství; MCP `run_script` sám nemá lokální soubory ani obecnou síť. Přes `aws_mcp.search_functions` vyhledat podporované přenosy; nepředpokládat neexistující rozhraní, nevytvářet nový S3 bucket a nepoužít Bash AWS CLI jako náhradu. Pokud schválená cesta chybí, uvést konkrétní capability blocker ještě před cutoverem.
- Při implementaci použít `tdd`, při boto3 kódu `aws-sdk-python-usage`, při nutné scoped policy `aws-iam`; po dokončení `validate-implementation`, nezávislé `code-review` a `write-review-report`. Pro historickou TDD provenienci použít podle potřeby `task-evidence`; posledním krokem uložit poznatek přes `save-learning`.

## Implementation
1. **Předpoklady:** potvrdit hostem připravený feature kontext bez vlastních git mutací. V privátním `/tmp` mkdtemp (700, soubory600) zprovoznit `/Users/michal/.local/bin/python3.13` venv a `requirements-dev.txt`; ověřit pip, import boto3/simplejson a baseline z Testing. Pokud ensurepip stále selže, vyžádat přesně opravu bootstrapu hostem; neopakovat tutéž chybu jako RED. Chybějící esbuild reportovat hostovi k obnovení existujícího backoffice prostředí, bez frontend změn.
2. **TDD:** znovu ověřit basename kolize, zkontrolovat parent proof a provést TDD níže pouze pro dosud chybějící deploy-target/write-opt-in chování; nepřepisovat existující UUID testy. Import/discovery musí zůstat bez SDK inicializace a sítě.
3. **Read-only preflight:** přes standardní SSO chain profilu `ai-hackathon` potvrdit STS účet `609394381050`, region `eu-central-1`, Lambda `arn:aws:lambda:eu-central-1:609394381050:function:wonderfulkb-case-client`, Zip/x86_64 a roli `arn:aws:iam::609394381050:role/wonderfulkb-lambda-role`. Načíst skutečné policies a paginovaně všechny Lambda uživatele role; dalšího uživatele před její změnou vyhodnotit jako blocker. STS samo nepotvrzuje profil ani write oprávnění.
4. **Vazby:** ověřit čtyři AWS_PROXY integrace REST API `bgm7k1ggqi`/stage `v1` na tutéž nealiasovanou Lambdu, invoke permission, apiKeyRequired, usage plans/throttles. Správný existující key vybrat vazbou API/stage z IDs `16u2jtkay6`/`b0w43mx5vf`; hodnoty z GetUsagePlanKeys/GetApiKey redigovat před výstupem. DescribeTable ověří `wonderfulkb-uw-clients`/PK client_id S/ico-index (ico S, ALL) a `wonderfulkb-uw-cases`/PK case_id S/client-created-index (client_id S, created_at S, ALL). Datové tvary ověřovat cíleně na vlastních/známých syntetických IDs s projekcí, bez DB dumpu.
5. **Deploy skript:** zavést `tools/case_client_test_deploy.py`: výchozí read-only kontrola, explicitní write opt-in a lineární snapshot→build/upload→config→verify; explicitní restore původního snapshotu. Před každou mutační skupinou zopakovat account/region/function guard. Shodný hash i konfigurace→no-op; AccessDenied/SSO expirace→nonzero BLOCKED s action/ARN, bez loginu nebo čtení credential souborů.
6. **Rollback a build:** před první mutací stáhnout původní Zip pouze soukromě, ověřit base64 SHA256 proti CodeSha256 a uložit runtime/handler/env/role/RevisionId i pouze případně měněné IAM/API údaje. URL držet v paměti. Balit src+lock dependencies reprodukovatelně pro Linux x86_64 CPython3.13 (`pip --only-binary=:all: --implementation cp --python-version 3.13 --abi cp313 --platform manylinux2014_x86_64`); ověřit handler v kořeni, wheel/ELF architekturu zejména simplejson, hash a přímý upload limit. Mac venv není artefakt; SAM šablonu pouze lintovat, nespouštět sam deploy.
7. **In-place cutover:** pouze při prokázaném deficitu přidat jednu vlastní nekolidující inline policy s nutnými přesnými table/index akcemi, zejména `dynamodb:ConditionCheckItem` na clients; nepřepsat `dynamodb-access`, trust/managed policies. UpdateFunctionCode→waiter→UpdateFunctionConfiguration→waiter s očekávaným RevisionId; cizí změna→stop. Nastavit python3.13, `case_client_handler.lambda_handler`, `DATA_BACKEND=dynamodb`, `ALLOW_EPHEMERAL_MOCK=false`, čtyři table/index env dle README, zachovat ostatní env a roli. AWS_REGION je rezervovaný, nezapisovat jej. Jen prokázaná nutná oprava čtyř existujících API metod/stage po snapshotu, bez změn auth/throttles.
8. **Fixtures:** v deploy skriptu oddělená explicitní provisioning funkce s allow-writes/run_id. Nejvýše4 nové clients (2active/inactive/blocked), run-derived UUID, společný syntetický run-name s diakritikou/právní formou, source=synthetic, validní osmimístná IČO. IČO ověřit cíleným Query; PutItem vždy `attribute_not_exists(client_id)`. Při opakování pouze ověřit vlastní manifest/IDs, nikdy overwrite ani změna statusu. Nejvýše12 cases, výhradně přes HTTP; manifest zapisovat i při částečném selhání, všechny fixture IDs ponechat.
9. **HTTP runner:** zavést `tests/integration/case_client_api_integration.py` s main, read-only defaultem, `--allow-writes`, run_id, deployment manifestem a očekávaným dynamodb. Přijmout jen `https://bgm7k1ggqi.execute-api.eu-central-1.amazonaws.com/v1`; validovat deployment identitu před zápisem. Key pouze v paměti SDK/transport procesu či procesním env, nikdy argv/soubor/stdout; zakázat redirects, debug a raw exceptions. Tisknout pouze allowlist report polí, ne headers/payloady či presigned URL.
10. **Rozpočty:** sdílet run manifest přes všechny iterace; nejvýše5 mutačních deploy pokusů/60min live ladění, 200 HTTP pokusů celkem (přísnější aktuální proposal), timeout10s/request, průměr≤2req/s, max2 souběžná volání jen pro races, GSI deadline60s s omezenými stránkami/cycle detection. Plná sada má7 úspěšných POST (3plain+2same-client+2cross-client); rezervovat potenciální zápis i při timeoutu do limitu12. POST automaticky neopakovat ani po5xx; známéID ověřit GET, neznámý výsledek pouze bounded list vlastního klienta/run_id. Nevyřešená nejistota→nonzero BLOCKED, missing fixtures→NOT_READY, assertion→FAIL.
11. **Živý cyklus:** ověřit nasazený hash/config/API/table/index identitu a spustit všechny scénáře z Testing. In-scope chybu reprodukovat offline, opravit minimálně, zopakovat brány/build/deploy/full live sadu ve zbývajícím budgetu. Při unhealthy deployi obnovit původní zdravý Zip/config a pouze vlastní IAM/API změny s RevisionId/waitery; cizí změny nepřepsat, DB neuklízet. Ověřit obnovený hash/config/dostupnost; obnovený Node není úspěšný Python deploy.
12. **Předání:** znovu načíst CodeSha256 po testech a porovnat s testovaným Zip; uložit manifest, scenario results a iterations/rollback metadata z Files. README změnit z odložené integrace na skutečný runbook a doložený stav. Finální checkpoint svázat s tímto taskem a původním checkpointem; uvést bezpečné příkazy, gate/live výsledky, hash před/po, pokusy, ponechané IDs a soukromé rollback umístění. Bez celé live sady a nezávislých bran nepřiznat success; přístupový blocker uvést konkrétní action/ARN. Uzavřít validací/review a nakonec `save-learning`.

## TDD
- Implementace TDD cyklu dle skill:tdd. Nejdříve přes `task-evidence` dohledat případný skutečný historický RED pro stejné guardy; parent checkpoint žádný neobsahuje. Historický UUID proof není důkaz deploy-target/write-opt-in. Pokud mezitím nástroje vznikly, nejprve číst jejich test/proof a převzít platný RED + čerstvý GREEN; nerozbíjet hotový kód kvůli novému RED.
- Pro aktuálně chybějící nástroje vytvořit nejprve následující dva nové test soubory. Absenci požadovaného modulu ověřit explicitním assertion; žádné produkční stuby před RED ani import/ensurepip selhání vydávané za behavior proof.
- `be-case-client/tests/test_case_client_test_deploy.py`:
```python
import importlib
import importlib.util
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

class DeployTargetTests(unittest.TestCase):
    def test_wrong_account_is_rejected(self):
        self.assertIsNotNone(importlib.util.find_spec('case_client_test_deploy'),
                             'Required deploy-target guard is absent')
        deploy = importlib.import_module('case_client_test_deploy')
        with self.assertRaises(ValueError):
            deploy.require_case_client_target('000000000000', 'eu-central-1')
```
- `be-case-client/tests/test_case_client_api_integration.py`:
```python
import importlib
import importlib.util
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'integration'))

class WriteOptInTests(unittest.TestCase):
    def test_default_profile_rejects_write(self):
        self.assertIsNotNone(importlib.util.find_spec('case_client_api_integration'),
                             'Required HTTP write-opt-in guard is absent')
        runner = importlib.import_module('case_client_api_integration')
        with self.assertRaises(ValueError):
            runner.require_case_client_write_opt_in(False, 'synthetic-run')
```
- Doplnit ještě před RED do těchto tříd orchestration testy s fake SDK/transportem: neplatný account/region/function a read-only/missing run_id musí skončit před jakýmkoliv mutačním SDK/POST voláním; validní target a opt-in nesmějí být plošně odmítané. Zachytit genuine failing assertion chybějícího guardu, následně implementovat minimální funkce i jejich skutečné zapojení do entrypointů.
- Stejný focused argv pro obě fáze, z project root (VENV je funkční privátní venv z kroku1):
```sh
TASK_ID=task-beca6825-147b-43d9-9fb6-694368e70948 python3 "$HOME/.config/opencode/skills/tdd/scripts/proof-capture.py" red -- "$VENV/bin/python" -m unittest discover -s be-case-client/tests -p 'test_case_client_*.py' -v
TASK_ID=task-beca6825-147b-43d9-9fb6-694368e70948 python3 "$HOME/.config/opencode/skills/tdd/scripts/proof-capture.py" green -- "$VENV/bin/python" -m unittest discover -s be-case-client/tests -p 'test_case_client_*.py' -v
```
- Před RED zkontrolovat, že discovery zahrnuje oba nové soubory. Nastavit offline prostředí a zákazy socket/DNS v testech stejně jako stávající Stubber sada; pro následnou diagnostiku lze spouštět každý nový soubor vlastním přesným `-p`, ale published RED/GREEN argv neměnit.

| Test | Genuine RED před novým nástrojem | GREEN |
|---|---|---|
| wrong_account_is_rejected | Assertion: požadovaný deploy-target modul/guard chybí | ValueError před mutací; správný target projde |
| default_profile_rejects_write | Assertion: požadovaný write-opt-in modul/guard chybí | ValueError před POST; opt-in+run_id projde |
| entrypoint side effects | Chybí požadovaný entrypoint/guard | Fake SDK/HTTP bez zápisu pro odmítnuté vstupy |

- Přijmout pouze helper `accepted_red` s nonzero child a `accepted_green` s child0, identický argv. Canonical proof `plans/checkpoints/task-beca6825-147b-43d9-9fb6-694368e70948.red-green-proof.md` generuje helper, ne ruční zápis; raw diagnostika `.tdd-test-runs/` zůstává ignored. Propojit proof ze sanitizovaného live checkpointu; neměnit acceptance manifest ani task state.
- Rozšířit offline pokrytí na snapshot hash/packing, env merge/no-op, RevisionId/waitery/rollback, redakci key i výjimek, redirect bez druhého requestu, request/fixture budgets, GSI deadline a ambiguous POST bez retry.

## Testing
- Před změnami a po implementaci spustit `PYTHONPATH=be-case-client/src "$VENV/bin/python" -m unittest discover -s be-case-client/tests -p 'test_*.py' -v`; ověřit, že discovery ani import nevolají cloud.
- Spustit `PYTHONPYCACHEPREFIX="$PRIVATE_DIR/pycache" "$VENV/bin/python" -m compileall -q be-case-client/src be-case-client/tests be-case-client/tools` a offline `SAM_CLI_TELEMETRY=0 /Users/michal/.local/bin/sam validate --lint --template-file be-case-client/template.yaml` s regionem eu-central-1, fake credentials, AWS config/credentials paths `/dev/null` a EC2 metadata disabled.
- Zachovat přesný registrovaný gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` (timeout300s); pokud zůstane unrelated esbuild failure, uvést FAIL/followup a neoznačit celkový gate green. Plánování tyto testy ani deployment nespouští.
- Zaznamenat každý řádek live matice samostatně včetně assertion, výsledku, času, HTTP statusů a run_id; read-only subset neoznačovat za plnou přejímku:

| Scénář | Povinné ověření |
|---|---|
| Auth/backend/types | Bez/s chybným klíčem403; žádný redirect; app JSON/error a public field typy, X-Data-Backend=dynamodb; gateway403 oddělit od app markeru. |
| Clients | IČO/name/status i AND mismatch; case/diakritika/právní forma normalizace; žádné interní atributy. |
| Validation/not found |400neplatné IČO/name/status/query/limit0,101,nečíselný/token/POST;404neznámý case a client list. |
| Plain create/persistence | Bez case_id→201/UUIDv4; okamžitý GET přes vrácenéID se shodnými nested/Decimal/null/bool metadata. Totožný POST→nové201/ID; caller case_id ignorováno→další201/ID. |
| Negative POST | Unknown404, inactive/blocked409; žádný nový case pro negativní fixtures po bounded scoped GSI kontrole plus offline důkaz bez zápisu. Okamžitá absence v GSI není sama důkaz. |
| Pagination/tokens | Po GSI konvergenci cases newest-first, limit1 všechny vlastníIDs bez duplicit/ztrát, bez tie-break slibu; clients limit1 přes run-name všechny4fixtures; změněný query/limit/client s tokenem400. |
| Same-client race | Dva souběžné POST→201+201/různá UUIDv4; oba obsahy přes GET. |
| Cross-client race | Dva aktivní klienti se stejným caller case_id→201+201/různá serverováID/správní vlastníci přes GET, žádný owner409. |
| Deployment identity | Původní endpoint, python3.13/handler/role/env/table/index/API vazby; CodeSha256 před i po testech shodný s artefaktem. Hlavička samotná nestačí. |

## Files
| Cesta | Konkrétní změna |
|---|---|
| `be-case-client/tools/case_client_test_deploy.py` | Nový lineární deploy/snapshot/restore a oddělený fixture provisioning. |
| `be-case-client/tests/integration/case_client_api_integration.py` | Nový explicitní bounded HTTP runner a sanitizovaný report. |
| `be-case-client/tests/test_case_client_test_deploy.py` | Offline guard/build/revision/rollback testy. |
| `be-case-client/tests/test_case_client_api_integration.py` | Offline opt-in/transport/redakce/budget testy. |
| `be-case-client/README.md` | Skutečný in-place runbook, bezpečné příkazy a odkazy na doložené výsledky. |
| `be-case-client/src/case_client_*.py` a existující komponentové testy | Jen minimální oprava konkrétní reprodukované live chyby; zachovat současný UUID kontrakt. |
| `plans/checkpoints/case-client-live-integration/task-beca6825-147b-43d9-9fb6-694368e70948/` | `deployment.json`: account/region/function/URL/runtime/handler/role, allowlisted env/table/index vazby, build hash/CodeSha256 před+po a časy; `scenarios.json`: assertion/status/backend/outcomes/IDs; `iterations.json`: pokusy/opravy/budgets/rollback stav; `checkpoint.md`: provenance, gates, proof/review odkazy a privátní rollback cesta bez obsahu. |
| `plans/checkpoints/task-beca6825-147b-43d9-9fb6-694368e70948.red-green-proof.md` | Výhradně skill:tdd helperem zachycený genuine proof, link z live checkpointu. |
- Ponechat raw Zip/config/key/URL/credentials pouze v povolené privátní paměti/rollback prostoru; verzovat jen sanitizované důkazy. Neměnit frontend, registry, lifecycle/state, platform deploy ani cizí rozpracované soubory; canonical plan propojí host standardním mechanismem, bez ruční editace task storage.

## Progress
- [x] Přečíst parent plán/brief/checkpoint, aktuální komponentu, historii/diff a relevantní learnings.
- [x] Uložit dedikovaný kanonický plán pro task-beca6825-147b-43d9-9fb6-694368e70948; namapovat všechna tři blocking findings na implementaci a důkazy.
- [ ] V implementační fázi vyřešit konkrétní host prerequisites, provést TDD, autorizovaný deploy a plnou live sadu; doložit hash/config/scénáře/retained IDs/rollback a brány, poté uložit learning.
