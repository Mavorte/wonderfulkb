# Plan 2026-10-19: Case Client — Python deployment and live DynamoDB integration

## Aktuálnost a převzetí
Host19.10.17:54 na výslovný pokyn uživatele přebírá hotový původní plán bez nového planneru. Tento odstavec a aktualizované kroky1/6/10/11/13 a zápisovýbudget mají přednost před historickou širší maticí. Bez verzovacích operací nebo přípravy větví. Schválený task brief zůstává autoritou. Nejde o tvrzení nové nezávislé review; nakonfigurovaný review gate zůstává.

## Analysis
- Zachovat hotové `src/case_client_handler.py` a `src/case_client_dynamodb_repository.py`: UUIDv4/201, caller ID ignorováno, Decimal, strong GetItem a podmíněná transakce již existují.
- Převzít existující `tools/case_client_test_deploy.py`, `tests/integration/case_client_api_integration.py` a `tests/test_case_client_live_tools.py`; před změnami porovnat jejich guardy a manifest posledního pokusu. Původní předpoklad o chybějících nástrojích již neplatí.
- Použít learnings z `learnings/architecture/2026-10-19_case-client-{source-contract-vs-deployed-state,live-tools-evidence-and-task-wide-budgets}.md` a `learnings/runtime-errors/rules-case-client-{dynamodb-decimal-range,normalize-filter-once,cursor-json-depth}.md`: ověřit nasazený hash odděleně od source, zachovat task-wide budget, Decimal, jednorázovou normalizaci a HTTP 400 pro hluboké tokeny.
- Ignorovat historické mock/idempotence a OpenAPI 1.3 předpoklady; nepřidávat zrušenou opravu kandidátů UUID. Recall použil local fallback, kolekce `wonderfulkb-learnings` v QMD neexistuje.
- Navázat na `plans/checkpoints/case-client-live-integration/task-beca6825-147b-43d9-9fb6-694368e70948/manifest.json`: 5 deploy pokusů, 4 vytvořené fixtures, 1 neověřený POST→500, žádné potvrzené case ID; rollback `verified-code-config-and-http` na původní nodejs22.x. Tyto údaje jsou historická evidence, ne nový cloudový readback této plánovací session.
- Vyřešit nesoulad historických polí `observed/post_live` (Python) a novějšího `restored` (Node) explicitním časovým/provenance označením; nepřepisovat historii ani tvrdit úspěšné nasazení Pythonu.
- Znovu posoudit R1–R5 z existujícího `review.md` proti aktuálním souborům: některé opravy již existují, ale starý review report je neověřuje. Prověřit zejména deadline po čekání limiteru, obnovu po deadline a ztrátu původní POST validační evidence při resume.

## Approach
- Pracovat s aktuálními soubory bez git operací, branch/worktree či úprav konfigurací projektu. Tato session vytváří pouze plán; následující kroky provede implementační session.
- Použít interpreter `/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python` (dále `$PY`), SAM `/Users/michal/.local/bin/sam`; nezačínat ensurepip ani instalace globálních nástrojů. Před testy ověřit Python 3.13 a import boto3/botocore/simplejson; chybějící závislost předat hostu jako environment blocker.
- Použít `skill:tdd` pro nové guardy, `skill:code-review` pro nezávislé review a `skill:write-review-report` pro jeho výstup; pro nezávislé review delegovat samostatného reviewera s přístupem k diffu a sanitizované evidenci. Zakončit implementační task `skill:save-learning`; dostupnost skillů ověřil discover-skills helper.
- Pro AWS řízení použít přednostně AWS MCP; lokální komponentový nástroj používá boto3 dle `skill:aws-sdk-python-usage`. Nevypisovat citlivé SDK odpovědi do modelu. AWS CLI nepoužívat místo MCP. Zpracování původního ZIP a API klíče musí zůstat uvnitř lokálního procesu, klíč nikdy nevracet nástrojem/modelu.

## Implementation
1. Převzít existující ledger, RED/GREEN proof a review. Starých5pokusů/rollback/nejasnýPOST zůstává nezměněná historie. Uživatel19.10.17:49 povolil nové odděleně účtované pokračování case-live-beca6825-20261019-iam1750: max3forward deploy pokusy+1rezervovaný rollback,30min,max6novýchPOST,4stávajícífixtures bez dalších. Neopakovat nejasnýstarýPOST. Host již opravil přesné IAM právo a ověřil allowed; žádné další IAM mutace workerem. Změnit jen nutné účetní/deadline části existujících nástrojů, žádný framework.
2. Po import preflight spustit baseline unit testy a registrovanou frontend bránu příkazy níže. Existující nástroje upravovat jen pro doložené chybějící guardy dle TDD níže; hotový backend ani fungující guardy nevyrábět znovu. Zachovat explicitní write opt-in, allowlist, bounded SDK timeouty a vypnuté debug logy. Použít pouze `boto3.Session(profile_name='ai-hackathon', region_name='eu-central-1')`; STS musí potvrdit účet `609394381050` před každou mutující fází. SSO expirace/AccessDenied → konkrétní BLOCKED bez loginu/eskalace. Žádné čtení credential souborů nástrojem.
3. Read-only preflight: GetFunction/GetFunctionConfiguration pro `arn:aws:lambda:eu-central-1:609394381050:function:wonderfulkb-case-client`, package ZIP, architekturu a RevisionId; DescribeTable pro obě tabulky, klíče, GSI/projekce; zkontrolovat skutečné datové vazby. Snapshot původních čtyř metod `/clients` GET, `/cases` POST, `/cases/{case_id}` GET a `/clients/{client_id}/cases` GET API `bgm7k1ggqi`, stage `v1`, AWS_PROXY URI/permissions, auth, deployment a throttles. Neočekávaný target zastavit.
4. Před první změnou vytvořit privátní adresář v `/tmp` mode 0700; stáhnout originální code ZIP přes GetFunction URL pouze v procesu, soubory mode 0600. Ověřit base64 SHA256 proti CodeSha256. Uložit soukromě původní runtime/handler/env/architekturu/roli a konfiguraci nutnou pro obnovu, snapshot API a případné vlastní inline policy. Nevkládat ZIP, download URL, kompletní config ani secrets do reportů. Ověřit původní API read-only smoke jako baseline obnovy.
5. Zachovat existující build ze současného `src/` a všech pinů `src/requirements.txt` pro Linux manylinux2014_x86_64/cp313. Připravený interpreter podle posledního pokusu nemá pip; převzít existující uv fallback, nezačínat bootstrap. Ověřit resolver, obsah ZIP, CPython 3.13/x86_64 wheel a ELF simplejson; nebalit macOS venv/cache/testy. Chybějící kompatibilní wheel je blocker. Změřit ZIP proti přímému upload limitu a vypočítat hex/base64 SHA256; nepoužívat S3 ani SAM deploy/CFN.
6. Zachovat původní execution roli. Hostem přidaná policy case-client-active-condition-check povoluje jen dynamodb:ConditionCheckItem na clients table; readback a regionální simulace allowed jsou v host-iam-authorization-20261019-1750.md. Žádné další IAM změny ani znovuotevírání procedurálního role-user discovery blockeru pro již schválenou změnu.
7. In-place UpdateFunctionCode s ZipFile, Architectures=['x86_64'] a RevisionId; waiter a následný GetFunctionConfiguration ověří LastUpdateStatus a nový RevisionId. Poté UpdateFunctionConfiguration s tímto RevisionId: python3.13, `case_client_handler.lambda_handler`, DATA_BACKEND=dynamodb, ALLOW_EPHEMERAL_MOCK=false, tabulky/indexy dle README; ostatní env i role zachovat, rezervovaný AWS_REGION nenastavovat. Každou další změnu i rollback podmínit vlastní poslední revizí; původní architekturu obnovovat přes UpdateFunctionCode. Konflikt → stop, nepřepsat konkurenční práci.
8. API měnit jen při doložené závadě některé ze čtyř původních integrací a po snapshotu; drobnou opravu promítnout do stávající stage a ověřit návrat auth/throttle beze změny. Nevytvářet resources, endpointy, klíče ani usage plans. Klíč vybrat z existujícího plánu navázaného na API/stage (ověřit `16u2jtkay6`, `b0w43mx5vf`); hodnotu získat až uvnitř HTTP runneru a držet pouze v paměti. Žádný secret v argv, stdout/stderr, souboru, tracebacku či logu.
9. Převzít `tests/integration/case_client_api_integration.py`: default read-only; zápisy pouze `--allow-writes --run-id <unique-run-id>`. Pevná URL `https://bgm7k1ggqi.execute-api.eu-central-1.amazonaws.com/v1`, TLS, zákaz redirectů v transportu, sanitizované chyby bez raw request/response debug. Sdílený limiter ≤2 req/s, max 2 HTTP souběžně, bounded timeouty a celkový budget. Znovu ověřit deadline po limiter čekání; timeout přizpůsobit zbývajícímu budgetu. Čtyři existující fixtures převzít, žádné další nevytvářet; conditional PutItem bez overwrite zachovat.
10. Spustit zúženou matici níže; nejvýše6novýchPOST celkem v tomto autorizovaném pokračování. Vést průběžný sanitizovaný ledger run_id/fixture IDs/case IDs a počítadel pokusů. GSI pollovat jen nad fixture klienty a nejvýše 60 s; strong GET známého case provést ihned bez slepého čekání. Žádný automatický retry POST po timeoutu: známé ID ověřit GET, jinak scoped list fixture klienta s run_id a budgetem; neurčený výsledek → BLOCKED a započítat potenciální zápis do limitu.
11. Opravit pouze prokázané integrační vady v komponentě, doplnit focused regresi a zopakovat build/deploy/test. Sdílet pouze nový autorizovaný limit3forward+1rollback a30min live ladění včetně čekání; počítat i neúspěšné pokusy a ponechat prostor na obnovu. Při nefunkčním výsledku obnovit originální ZIP/config a pouze případné vlastní API změny; hostovu úzkou IAM policy neodstraňovat s revision kontrolou; waiter, hash/config readback a původní smoke doloží obnovu. Při konkurenční revizi rollback nevnucovat, uvést neprovedenou obnovu jako blocker.
12. Oddělit rezervovaný bounded recovery smoke od vyčerpaného forward deadline; nikdy tím nepovolit další live ladění. V ledgeru oddělit přijetí 201, validaci response a skutečně okamžitý GET; pozdější GET nesmí změnit původně neověřený scénář na PASS. Zkontrolovat invalidaci PASS podle hash/revision/run_id, failed-build accounting a rollback config readback proti R1–R5; doplnit offline regrese jen pro zbývající vady.
13. Po live testech ověřit runtime/handler/roli/env,table/index vazby a CodeSha256 před i po matici. Aktualizovat README a nezávislé review aktuálního kódu/evidence. PASS jen při našem Pythonu na původním API s DB, aktuální povinné matici a standardních registrovaných branách. Dřívější IAM blocker je hostem vyřešen; nové skutečné problémy reportovat pravdivě.

## TDD
- Implementace TDD cyklu dle skill:tdd; task ID `task-beca6825-147b-43d9-9fb6-694368e70948`, přesný interpreter a argv uložit do kanonického proof určeného skillem; sanitizované live podklady pod `plans/checkpoints/case-client-live-integration/`.
- Rozšířit existující `be-case-client/tests/test_case_client_live_tools.py`; unittest, zachovat zákaz socket/DNS a mock AWS klientů. Import/runtime chyba není RED. Zachovat historický proof; nový focused cyklus musí prokázat dosud neopravené chování, ne opakovat již zelené testy.
- Focused argv: `/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m unittest discover -s be-case-client/tests -p test_case_client_live_tools.py -v`.
- Připojit následující metodu do existující `LiveToolGuards` (reálné importy `api`, `Mock`, `patch` již obsahuje test soubor); aktuální `Transport.request` kontroluje deadline před sleep, ale ne po něm:

```python
    def test_deadline_rechecked_after_rate_limit_wait(self):
        now = [100.0]
        def sleep(seconds):
            now[0] += seconds
        http = api.Transport('fake-key', clock=lambda: now[0], sleep=sleep)
        http.deadline = 100.1
        http.next_start = 100.55
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{}'
        response.code = 200
        response.headers = {}
        opener = Mock()
        opener.open.return_value = response
        with patch.object(api, 'build_opener', return_value=opener):
            with self.assertRaisesRegex(ValueError, 'deadline'):
                http.request('GET', '/clients')
        opener.open.assert_not_called()
```

| Focused test | RED before guard | GREEN |
|---|---|---|
| deadline_rechecked_after_rate_limit_wait | ValueError not raised; mocked request sent after deadline | deadline ValueError; no request |

- Zachovat již existující testy správného profilu/region/function/URL, write opt-in, redakce, no-redirect, RevisionId/waiterů, záložního SHA/permissions, rollbacku a budgetů. Doplnit chybějící R1–R5 regrese s fake clock/transportem: recovery smoke po deadline, validačně neúplný 201 při resume, změna hash/revision se starými PASS, failed build a timeout po čekání; žádné cloud/credential discovery.

## Testing
- Import preflight před baseline i RED: `/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -c 'import sys, boto3, botocore, simplejson; assert sys.version_info[:2] == (3, 13); print(sys.version.split()[0], boto3.__version__, botocore.__version__, simplejson.__version__)'`. Výstup ukládat jako environment evidence, nikoli RED/GREEN důkaz.
- Pro komponentové testy: `PYTHONPATH=be-case-client/src /Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m unittest discover -s be-case-client/tests -p 'test_*.py' -v`.
- Compile: `/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m compileall -q be-case-client/src be-case-client/tests be-case-client/tools`.
- Offline lint: `AWS_REGION=eu-central-1 AWS_DEFAULT_REGION=eu-central-1 AWS_EC2_METADATA_DISABLED=true AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_ACCESS_KEY_ID=offline AWS_SECRET_ACCESS_KEY=offline SAM_CLI_TELEMETRY=0 /Users/michal/.local/bin/sam validate --lint --template-file be-case-client/template.yaml`. Tuto šablonu nenasazovat.
- Registrovaná brána (timeout 300 s): `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`. Přesný environment/unrelated blocker reportovat bez změn frontendu; nepřepsat na úspěch.
- Live runner volat stejným `$PY` pouze při znovu výslovně autorizovaném live rozpočtu; v aktuálním tasku další live běh nespouštět. Po schválení nejprve read-only běh, poté `--allow-writes --run-id <ledger-run-id>`; nepředávat API key argument ani vytvářet další fixtures. Následující matice zůstává povinným cílem, nikoli dosaženým výsledkem.

| Live scenario | Required evidence |
|---|---|
| Auth | bez klíče a s chybným klíčem 403; správný klíč na původních metodách funguje |
| Clients | IČO, name/status AND a diakritika/case/právní forma; limit=1 a další stránky bez duplicit/ztrát fixture shod; scoped výsledky bez dumpu |
| Validation/missing | invalid ico/name/status, limit 0/101/nečíslo, malformed a query-bound token →400; missing case/client →404 |
| Create/detail | bez caller ID →201 UUIDv4; okamžitý GET shodných polí a nested Decimal metadata bez float roundtrip; opakovaný POST →jiné ID/201 |
| Caller ID | caller ID ignorován; shodný caller ID u dvou active klientů →201+201/různá serverová ID, nikoli 409 |
| Rejections | unknown client →404, inactive/blocked →409; fixture-client list před/po a scoped bounded polling nepotvrdí žádné vytvoření; pro unknown i cílená kontrola jeho partition |
| Case pages | po bounded GSI propagaci úplná sada známých case IDs newest-first, limit=1 a následné stránky bez duplicit/ztrát; token s jiným client/filter/limit →400 |
| Concurrency | přesně dva souběžné POST stejnému active klientovi →201+201/různá ID, GET obou; sdílený rate limiter |

- Aktuální úzká live matice:2úspěšnéPOST se stejným dodaným callerID→201/různáUUIDv4, okamžitýGETshody/metadata;3negativníPOST unknown404/inactive409/blocked409;clientcaseslist obsahuje vytvořenáID;auth403. Celkem5POST+1rezerva, ne širší historická matice nad budget. Stávající cases při porovnávání listu zachovat, nevyžadovat že partition obsahuje jen novéIDs. Rozsáhlejší concurrency/scénáře výše jsou historický referenční rozsah, ne další povinné novéHTTPzápisy tohoto pokračování.
- Manifest `plans/checkpoints/case-client-live-integration/task-beca6825-147b-43d9-9fb6-694368e70948/manifest.json`: účet/region/function/API URL, runtime/handler/backend/role a table/index vazby, artifact SHA a CodeSha256 před deployem, před i po live testech, jednotlivé scénáře PASS/FAIL/BLOCKED, pokusy, run_id/syntetická IDs, write budget, rollback stav a brány/review. URL API je veřejný identifikátor; podepsaná code download URL/config/credentials/key/payload dump do manifestu nesmí.
- Nezávislé review musí ověřit hash nasazení, povinnou live matici, guardy a pravdivost evidence; uložit sanitizovaný review report do stejného checkpointu. Samotná hlavička X-Data-Backend není důkaz.

## Files
| Path | Planned change |
|---|---|
| `be-case-client/tools/case_client_test_deploy.py` | převzít nástroj; jen doložené zbývající recovery/accounting guard opravy |
| `be-case-client/tests/integration/case_client_api_integration.py` | deadline po limiteru, bounded recovery, pravdivá resume/evidence validace |
| `be-case-client/tests/test_case_client_live_tools.py` | připojit focused offline regrese ke stávajícím testům |
| `be-case-client/src/*.py`, `be-case-client/tests/test_case_client_*.py` | pouze prokázané integrační opravy a regrese, zachovat hotový UUID kontrakt |
| `be-case-client/README.md`, `be-case-client/openapi-case-client.yaml` | skutečný runbook/stav nasazení a důkazní odkazy; neměnit API kontrakt |
| `plans/checkpoints/case-client-live-integration/**` | sanitizované live výsledky, manifest a review |
- `template.yaml` a pinned requirements použít jako vstupy; měnit pouze při skutečné doložené komponentové vadě. Žádný nový globální GET /cases, frontend, policy/pipeline framework ani Wonderful publish.

## Progress
- [x] Získat kanonickou cestu pro task-beca6825-147b-43d9-9fb6-694368e70948.
- [x] Převzít skutečné existující nástroje, requirements, README, OpenAPI 1.4.0, source kontrakt, testy, manifest a review; opravit zastaralé předpoklady původního plánu.
- [x] Převzít existující plán; host19.10.17:54 aktualizuje pouze pověření/IAM/rozpočet a zúženou live matici, bez dalšího LLM plánování.
- [ ] Provést úzké dokončení existujících nástrojů, nasazení, aktuální live matici, standardní brány a nezávisléreview.
