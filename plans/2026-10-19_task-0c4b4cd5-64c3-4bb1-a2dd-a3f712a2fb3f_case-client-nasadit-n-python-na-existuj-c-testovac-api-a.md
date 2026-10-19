# Plan 2026-10-19: Case & Client — in-place Python deployment and live DB integration

## Analysis
- Zachovat aktuální OpenAPI 1.4.0, `src/case_client_handler.py` a repository: serverové UUIDv4, každý úspěšný POST201, ignorované caller case_id již existují. Opravovat pouze prokázané regresní nebo live chyby; nepřepisovat backend.
- Použít `be-case-client/README.md`, připnuté `src/requirements.txt`, existující unittest/Stubber testy a proposal `docs/proposals/proposal-20261019-114433-08800d_case-client-lambda-vyvoj-nezavisly-na-externi-databazi.md` (db-connection/deployed-integration); staré replay200/owner409 a host-only instrukce nahradit zadáním tohoto tasku.
- Uplatnit learnings `architecture/2026-10-19_case-client-{source-contract-vs-deployed-state,server-generated-uuid-collision-contract}.md`, `tooling/decisions-case-client-in-place-deploy-vs-sam-template.md` a `runtime-errors/rules-case-client-{cursor-json-depth,dynamodb-decimal-range,normalize-filter-once}.md`: zachovat strong reads, conditional transakce, Decimal, query-bound tokeny a jednu normalizaci. Nezaměňovat offline důkaz za runtime proof.
- Recall proveden lokálním fallbackem: collection `wonderfulkb-learnings`, diagnostic `Collection not found`; použít načtené soubory. Průzkum nenašel kolize čtyř požadovaných basename ani PlantUML diagramy; vycházet z existujících zdrojů a dokumentace.

## Approach
- Nahradit odmítnutý víceoperační framework dvěma krátkými účelovými skripty: přímý deploy s rollbackem a pevná sada HTTP scénářů. Použít standardní knihovnu a existující SDK; žádné pluginy, univerzální orchestrátor, vlastní pipeline ani automatický opravovací engine.
- Provést build→deploy→HTTP test→cílená oprava ručně v témže implementačním pokusu; uchovat jediný run manifest a nejvýše5 mutačních deploy pokusů/60min live ladění. Import ani unittest discovery nesmějí volat cloud.
- Před implementací použít `tdd`; před boto3 kódem `aws-sdk-python-usage`, před případnou IAM změnou `aws-iam`; závěrem `validate-implementation`, nezávislé `code-review` s `write-review-report`, potom `save-learning`. Plánování končí před buildem, testovacími zápisy a cloudovými mutacemi.
- AWS operace provádět oficiálním AWS MCP, nikoli AWS CLI přes Bash. Nejdříve ověřit podporu profilu `ai-hackathon`, privátního rollback downloadu a in-process SDK→HTTPS transportu bez návratu klíče/URL do modelu; chybějící podporu reportovat jako konkrétní blocker, neobcházet transport ani permission guard.
- Zachovat feature-branch pravidlo bez git operací: použít hostem připravený feature kontext; pokud chybí, před zdrojovými změnami vyžádat jeho přípravu. Neprovádět Wonderful deploy ani změny frontendů, registry či task state.

## Implementation
1. **Offline příprava:** vytvořit privátní `mkdtemp` pod `/tmp` (adresář700, soubory600), venv pomocí `/Users/michal/.local/bin/python3.13` a deklarovaných requirements. Zachytit baseline bran z Testing, pak RED/GREEN nové offline testy z TDD. Znovu ověřit basename kolize; existující soubor nejprve prozkoumat.
2. **Preflight před cloudovým zápisem:** ověřit STS účet `609394381050`, region `eu-central-1`, Lambda `arn:aws:lambda:eu-central-1:609394381050:function:wonderfulkb-case-client` (Zip/x86_64) a roli `arn:aws:iam::609394381050:role/wonderfulkb-lambda-role`. Paginovaným ListFunctions ověřit všechny uživatele role před její případnou změnou; dalšího uživatele řešit jako blocker. Ověřit skutečné inline/managed permissions bez jejich přepisování.
3. **Potvrdit původní vazby:** na REST API `bgm7k1ggqi`, stage `v1`, ověřit všechny4 kontraktové metody/integrace jako AWS_PROXY na tutéž nealiasovanou Lambdu, invoke oprávnění, API-key ochranu, usage plans a throttling. Správný existující key vybrat přes usage-plan vazbu z ID `16u2jtkay6`/`b0w43mx5vf`; redigovat i hodnoty z GetUsagePlanKeys před jakýmkoli výstupem. DescribeTable ověří `wonderfulkb-uw-clients`/PK client_id S/ico-index (ico S, ALL) a `wonderfulkb-uw-cases`/PK case_id S/client-created-index (client_id S, created_at S, ALL). Tvary ověřit jen cílenými projection reads známých syntetických IDs nebo vlastních fixtures, nikdy scan dumpem.
4. **Deploy skript:** přidat `tools/case_client_test_deploy.py` jako lineární postup snapshot→upload→config→verify, s explicitním write opt-in a samostatným explicitním obnovením snapshotu. Před každou skupinou mutací zopakovat STS/region/target guard. Stejný hash a konfigurace znamenají no-op. SSO expirace/AccessDenied znamenají nonzero BLOCKED s action/ARN, bez loginu či čtení credential souborů.
5. **Snapshot a artefakt:** před první mutací stáhnout původní Zip a ověřit base64 SHA256 proti CodeSha256; kompletní nutnou vratnou konfiguraci (runtime/handler/env/role), RevisionId a pouze případně měněné IAM/API údaje uložit do privátního rollback adresáře. URL použít pouze v paměti. Zabalit `src/` a připnuté dependencies do reprodukovatelného Zip pro CPython3.13/Linux x86_64: pip `--only-binary=:all: --implementation cp --python-version 3.13 --abi cp313 --platform manylinux2014_x86_64`. Ověřit kořen handleru, wheel tagy a ELF x86_64 zejména simplejson, hash a přímý upload limit; macOS wheel/venv odmítnout. Nevytvářet S3/CFN prostředky; SAM šablonu pouze lintovat jako samostatný artefakt.
6. **In-place změna:** pouze pokud skutečně chybí oprávnění, přidat jednu vlastní nekolidující inline policy s nutnými akcemi na přesných table/index ARN, zejména `dynamodb:ConditionCheckItem` na clients; nezasahovat do `dynamodb-access`, trust nebo managed policies, nepoužít wildcard. UpdateFunctionCode→waiter→UpdateFunctionConfiguration→waiter, vždy s očekávaným RevisionId; cizí změna znamená stop. Nastavit `python3.13`, `case_client_handler.lambda_handler`, `DATA_BACKEND=dynamodb`, `ALLOW_EPHEMERAL_MOCK=false` a čtyři table/index env podle README; nesouvisející env sloučit, rezervovaný AWS_REGION nezapisovat, region ověřit z SDK/ARN. Role zůstává původní. Jen prokázaně nutná gateway oprava smí měnit4 stávající metody a stage deployment po snapshotu, nikdy auth/usage plans/throttles nebo nové resources.
7. **Oddělený fixture provisioning:** v deploy skriptu přidat pouze malou explicitně volanou funkci pro4 nové clients (2active, inactive, blocked), nikoli další nástroj. Vyžadovat allow-writes/run_id, guard, UUID odvozená z run_id, syntetické jméno se společným run-name/diakritikou/právní formou, source=synthetic a validní osmimístná IČO. Ověřit IČO cíleným indexovým Query, při kolizi vybrat jiné; PutItem vždy s `attribute_not_exists(client_id)`. Při opakování použít manifest a cíleně ověřit již vytvořené vlastní IDs, nikdy overwrite/status změnu. Nejvýše4 nové clients a12 nových cases za run, rozpočet sdílet napříč iteracemi; všechny cases pouze HTTP. Existující data nemazat; manifest doplňovat průběžně i při částečném selhání.
8. **HTTP runner:** přidat `tests/integration/case_client_api_integration.py` s explicitním main, read-only defaultem, `--allow-writes`/run_id pro plnou sadu a očekávaným dynamodb backendem. Přijmout pouze přesnou HTTPS URL `https://bgm7k1ggqi.execute-api.eu-central-1.amazonaws.com/v1` a potvrzenou deployment identitu/account. Key získat SDK pouze do paměti procesu (případně procesní env), předat rovnou transportu. Zakázat redirects a HTTP/SDK debug/shell tracing; výstupy i výjimky tisknout pouze přes allowlist sanitizovaných polí, nikdy headers/payloady/raw SDK odpovědi.
9. **Ohraničený průchod:** použít timeout10s/request, společný limit240 HTTP requestů/run včetně pollů a opakovaných průchodů, tempo≤2req/s a nejvýše2 souběžná volání pouze pro race scénáře. GSI čekání nejvýše60s, omezené stránky s detekcí cyklu. Naplánovat7 úspěšných POST pro celou sadu (3plain-create +2same-client +2cross-client); rezervovat i potenciálně zapsaný case při timeoutu do limitu12. POST automaticky neopakovat ani po5xx: známéID ověřit GET, neznámé jen bounded list vlastního klienta/run_id. Nevyřešená nejistota→nonzero BLOCKED; okamžitá absence v GSI nedokazuje nezápis. Missing fixtures→nonzero NOT_READY, assertion chyba→FAIL.
10. **Live ladění a rollback:** před testy ověřit code hash/runtime/handler/env/role/API/table/index vazby, spustit celou sadu z Testing. In-scope chybu reprodukovat offline, opravit, zopakovat brány, build, deploy a test v témže tasku. Po prokázaně unhealthy deployi obnovit původní zdravou variantu; při limitu5pokusů/60min reportovat blocker a obnovit ji, pokud nový kód není zdravý. Rollback vrací původní code/runtime/handler/env/role a jen vlastní IAM/API změny s RevisionId/waitery, bez přepisování konkurenčních změn a bez DB cleanupu; ověřit obnovený hash/config/dostupnost. Obnovení Node neoznačovat jako úspěšný Python deploy.
11. **Předání:** po testech znovu získat CodeSha256 a porovnat s testovaným Zip. Uložit sanitizovaný deployment manifest, scénářové výsledky/statusy/run_id/backend/IDs, iterace/opravy a rollback metadata do `plans/checkpoints/case-client-live-integration/`; raw rollback ponechat soukromý. README upravit na skutečný runbook a doložené výsledky. Finální poznámka uvede code/cloud změny, bezpečné příkazy, offline/live výsledky, hash před/po, pokusy, ponechané IDs, rollback cestu a konkrétní případné action/ARN blockery; zachovat nezávislou přejímku a registrované brány.

## TDD
- Implementace TDD cyklu dle skill:tdd; nejprve dva nové offline testy, RED, potom minimální funkce a GREEN. Zachovat existující server-UUID/Stubber testy; nevyrábět RED změnou již správného handleru. Použít fake SDK/HTTP a zákaz socket/DNS jako v existujících DB testech.
- Nový `be-case-client/tests/test_case_client_test_deploy.py`:
```python
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from case_client_test_deploy import require_case_client_target

class DeployTargetTests(unittest.TestCase):
    def test_wrong_account_is_rejected(self):
        with self.assertRaises(ValueError):
            require_case_client_target('000000000000', 'eu-central-1')
```
- Nový `be-case-client/tests/test_case_client_api_integration.py`:
```python
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'integration'))
from case_client_api_integration import require_case_client_write_opt_in

class WriteOptInTests(unittest.TestCase):
    def test_default_profile_rejects_write(self):
        with self.assertRaises(ValueError):
            require_case_client_write_opt_in(False, 'synthetic-run')
```
- Před zachycením RED založit import-safe moduly s uvedenými funkcemi jako prázdnými stuby, aby selhal assertion `ValueError not raised`, nikoli import. Následně testy doplnit o validní target/opt-in a skutečné volání guardů před SDK/HTTP side effectem; stuby bez guardu nesmí projít.
- Focused commands: `PYTHONPATH=be-case-client/src "$VENV/bin/python" -m unittest discover -s be-case-client/tests -p 'test_case_client_test_deploy.py' -v` a totéž s `-p 'test_case_client_api_integration.py'`.

| Test | RED | GREEN |
|---|---|---|
| `test_wrong_account_is_rejected` | Chybí ValueError | Neshodný účet odmítnut před SDK mutací |
| `test_default_profile_rejects_write` | Chybí ValueError | Výchozí profil odmítnut před POST/transportem |

- Doplnit smysluplné fake testy existujícího toku: account/region/URL guard, idempotentní no-op, snapshot hash a Linux packing, env merge, RevisionId konflikt/waitery/rollback vlastních změn; key redakce i výjimky, redirect bez druhého requestu, request/write budgets, GSI deadline a ambiguous POST bez retry. Důkazy RED/GREEN ukládat pod povolený checkpoint adresář.

## Testing
- Před změnami i na konci spustit `PYTHONPATH=be-case-client/src "$VENV/bin/python" -m unittest discover -s be-case-client/tests -p 'test_*.py' -v`; běžný gate zůstává offline.
- Spustit `PYTHONPYCACHEPREFIX="$PRIVATE_DIR/pycache" "$VENV/bin/python" -m compileall -q be-case-client/src be-case-client/tests be-case-client/tools` a `SAM_CLI_TELEMETRY=0 /Users/michal/.local/bin/sam validate --lint --template-file be-case-client/template.yaml` s offline credentials/metadata disabled.
- Spustit registrovaný gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` (timeout300s). Unrelated failure přesně uvést bez frontend oprav nebo obcházení brány.
- Zaznamenat každý následující live scénář jednotlivě, včetně assertions a výsledku; read-only subset nikdy neoznačit jako plnou přejímku:

| Scénář | Očekávaný důkaz |
|---|---|
| Auth/response | Bez klíče i s chybným klíčem403; JSON/error typy podle OpenAPI, žádný redirect. App odpovědi mají X-Data-Backend=dynamodb; gateway chyby posoudit zvlášť. Rozpor gateway error tvaru opravit jen povolenou scoped změnou, nebo reportovat blocker. |
| Clients | IČO/name/status a AND kombinace včetně neshody; normalizace case/diakritiky/právní formy; veřejné response typy bez interních atributů. |
| Validace |400neplatné query/IČO/name/status/limit0,101,nečíselný/token/POST;404neznámý case i klientův seznam. |
| Plain-create | POST bez case_id→201/UUIDv4, okamžitý GET shodných polí a nested/decimal/null/bool metadat. Stejný POST→nové201/jinéID; dodané caller case_id ignorováno→201/jinéID. Každý úspěšný case ověřit GET. |
| Negativní POST | Unknown klient404, inactive/blocked409; vlastní negativní fixtures bez nových cases po bounded GSI kontrole, spolu s offline důkazem žádného zápisu. Nepoužívat ignorované callerID ani samotnou okamžitou GSI absenci jako důkaz. |
| Pagination/tokens | Po konvergenci GSI cases newest-first, limit1→všechny vlastní IDs bez duplicit/ztrát; bez slibu tie-breaku. Clients limit1 přes společný run-name zachytí4fixtures. Vrácený token při změně dotazu/limitu/klienta400 podle současného kontraktu. |
| Same-client race |2souběžné POST téhož active klienta→201+201/různá UUIDv4; oba přes GET. |
| Cross-client race |Stejné caller case_id pro2různé active klienty→201+201/různá serverová UUID, správní vlastníci a metadata přes GET, žádný owner409. |
| Runtime identity |Původní endpoint, python3.13/handler, správné role/table/index/env a CodeSha256 před i po testech shodný s artefaktem; hlavička sama nestačí. |

- Success přiznat pouze po celé live sadě, offline/registrovaných branách a nezávislém review. Nové HTTP spojení nepovažovat za důkaz nové execution environment; neprovádět429flood nebo změny concurrency/kvót.

## Files
- Přidat pouze `be-case-client/tools/case_client_test_deploy.py`, `be-case-client/tests/integration/case_client_api_integration.py`, `be-case-client/tests/test_case_client_test_deploy.py` a `be-case-client/tests/test_case_client_api_integration.py`.
- Upravit `be-case-client/README.md`; existující `src/case_client_*.py`, komponentové testy, requirements nebo template měnit pouze pro konkrétní reprodukovanou chybu/kompatibilitu. SAM šabloně nepřidělovat vlastnictví existující API.
- Ukládat sanitizované deployment/HTTP/fixture/iteration/review důkazy pouze pod `plans/checkpoints/case-client-live-integration/`; původní Zip/config/credentials/URL tam nepatří.

## Progress
- [x] Přečíst odmítnutý plán a feedback; odstranit frameworkové rozšíření a zastaralou reimplementaci UUID.
- [x] Ověřit současný zdrojový kontrakt, dokumentaci, learnings a kanonickou cestu; opravit neplatný nadpis Review Feedback začleněním připomínky do Approach.
- [ ] Nezávisle schválit plán před implementací; poté provést TDD, in-place deploy a úplnou live přejímku podle výše uvedených kroků.
