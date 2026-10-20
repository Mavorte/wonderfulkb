# Plan 2026-10-20: Monitoring MVP: pozorovaná extrakce ve stávajícím steps API

## Analysis
- Zachovat přítomné extraction větve `processing_monitor_step_routes.OBSERVATION_FIELDS`, focused `test_processing_monitor_extraction.py` a skutečnou run-events route; nevyrábět druhou implementaci podle zastaralého původního plánu.
- Navázat na `plans/checkpoints/task-12f46945-d733-47dc-b0e9-b8c9746fd7c2.red-green-proof.md` a `plans/monitoring/task-12f46945-d733-47dc-b0e9-b8c9746fd7c2-runtime-evidence.md`: historicky SOURCE/INSTALLED doloženo, DEPLOYED/LIVE-FUNCTION-VERIFIED nikoli. Nový plánovací běh runtime neověřuje.
- Reuse `read_authorized_window` → `AuditStore.read_document` → `audit_queries.read_document`: jediný document Query, Limit a poslední evaluated key; run/attempt/type filtr ponechat v route adapteru, zachovat technické EVENT#event_id pořadí.
- Řídit se `plans/tasks/2026-10-20_monitor-mvp-11-attempt-steps-get.md`, `plans/tasks/2026-10-20_monitor-mvp-16-extraction-events.md` a `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md`, section:slice-extraction; jediný OpenAPI YAML zachovat. Repo nemá nalezené PlantUML diagramy; nový diagram není potřebný.
- Uplatnit learnings o producer-supplied identitě, read failure místo empty success a task-wide budgetu; historické tvrzení `2026-10-20_extraction-steps-allowlist-and-run-events-prerequisite.md` o chybějící route nahradit aktuálním zdrojovým nálezem. Recall: backend local, collection wonderfulkb-learnings, diagnostika Collection not found; nepřebírat staré event/store zákazy deploymentu do této read dodávky.

## Approach
- Ponechat explicitní extraction StepStarted/StepFinished/StepFailed allowlist; vydávat jen event_id/type/sequence/occurred_at/run_id/attempt_no/stage a známou terminální duration_ms či bezpečný failure error_code. Žádné page_number, fields/quotes/evidence/labels/prompt/result/raw errors/counts ani model-call tvrzení.
- Zachovat mandatory positive attempt, partial/observed_at/next_token, terminal-only a start-only fragmenty, empty continuation a refresh od začátku bez snapshot/incremental garance; nesyntetizovat start/outcome/duration, úplnost polí ani konec runu. Nevyžadovat RunQueued/AttemptStarted a neodvozovat historii z business snapshotu.
- Reuse sdílené authorization/membership/no-store/read503 a page mapper; extraction nepatří do pages. Sdílenou facade upravit jen při vlastní prokázané DTO chybě; bez nového endpointu, readeru, indexu, projekce nebo celohistorického párování.

## Implementation
1. Porovnat vlastní source, původní plán, TDD a runtime evidence se současným checkoutem; zachovat souběžné změny ostatních ownerů. Ověřit historické source/wheel/image hashe, nepovažovat starý tag za aktuální artifact. První programová změna pro nově zjištěnou mezeru musí být focused test a skutečný RED dle skill:tdd; hotovou funkci neodstraňovat kvůli RED.
2. V `processing_monitor_step_routes.py` zachovat tři extraction type/stage dvojice, scope-bound cursor a jedinou bounded read delegaci. Případnou vlastní chybu opravit zde; žádný Scan/fill-page loop, druhý handler nebo auth kopie. `processing_monitor_routes.py`/main měnit pouze nezbytným malým DTO/zapojením diffem.
3. Ověřit document/run event parity pro stejné event_id/type/duration/error bez duplikace; zachovat dřívější úzkou DTO korekci StepFailed duration_ms/EXTRACTION_FAILED. Jediný YAML validovat proti skutečnému JSON: uzavřené extraction větve, optional duration, safe error allowlist, partial/unknown/empty continuation; ostatní operations zachovat.
4. Spustit focused a regresní gates níže. Použít existující root-context build: `docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:extraction-task-12f46945 .`. Ověřit skutečně instalovaný wheel bez worker dependencies a route import jako UID10001: `docker run --rm -i --platform linux/amd64 --user 10001 --network none --entrypoint python wonderfulkb-ingest:extraction-task-12f46945 - < be-intake/tests/image_processing_monitor_smoke.py`. Bez source mountů/PYTHONPATH; doložit source manifest, wheel SHA256 a image manifest/config digest, po buildu znovu zkontrolovat source drift.
5. Načíst skill:signing-in-to-aws a `/Users/michal/.agents/skills/signing-in-to-aws/references/wonderfulkb-test-access.md`; pro App Runner/ECR realizaci použít skill:aws-containers. Preferovat oficiální AWS MCP po signed STS ověření účtu 609394381050 v eu-central-1, kontrolovat api_calls. Pro podporované lokální deployment nástroje výslovně profil ai-hackathon a region; AWS CLI nespouštět přes Bash. Jen skutečná expirace opravňuje požádat hosta o zavedený SSO login s potvrzením.
6. Od Jackieho převzít existující deployment serialization guard a zbývající shared ledger, bez resetu. Cíl výhradně `arn:aws:apprunner:eu-central-1:609394381050:service/wonderfulkb-ingest/c9ef96fae3da4192abd7e8280d43ae6b`. Čerstvě DescribeService/ListOperations/ECR ověřit owner, URL, image digest, config fingerprint, permission/capacity prerequisites. `be-intake/template.yaml` spravuje role/secret, nikoli samotný service rollout; reuse skutečný native owner postup, nevymýšlet framework/script.
7. Před mutací chráněně uchovat kompletní recovery config a ověřený dostupný recovery image/manifest; do repo jen bezpečné reference/hash. Zamýšlený diff image identifier only; zachovat env, secret references, auth/IAM, síť, health, CPU/memory a auto-deploy. Ověřit kompatibilitu skutečných writer/reader artifactů; chronological/schema prerequisites řešit existujícím ownerem dle `plans/handoffs/aws-runtime-readiness-20261020.md`. Bez resetu/backfillu/Scan, nespravované tabulky či automatické fyzické migrace s rizikem ztráty dat.
8. Pod guardem pushnout ověřený candidate do existujícího ingest ECR, ověřit registry/platform digest; těsně před podporovaným in-place rolloutem porovnat operations/config/image/auth VersionId. Při driftu/cizím rollout nic nepřepsat. Nepředstírat App Runner RevisionId/CAS: guard je owner lock + fresh read. Nejvýše min(zbývající budget, 2 candidate rollouts + 1 recovery); bounded wait 15 minut/15s polling. Vyžadovat operation SUCCEEDED, RUNNING a fresh deployed digest/config readback. Při outage použít ověřený recovery jen při zachovaném vlastnictví.
9. V jediném procesu bezpečně načíst Secrets Manager `wonderfulkb/ingest-api-key`, `wonderfulkb/monitoring-synthetic-bearer-20261020` a policy `wonderfulkb/monitoring-synthetic-20261020`; ověřit hash binding/active credential/exaktní grant a membership SYN-A01 / 34fcd896-107a-583f-a406-6a8100cf8150. Poslat x-api-key a Authorization s doslovným `Bearer ` pouze na HTTPS host z DescribeService; bez redirectu, credentials/policy/raw dumpů v chatu/argv/evidenci.
10. Vyžádat doloženou existující extraction fixture/event provenance a skutečný run/attempt; historicky má schválený dokument 0 audit events bez continuation. Žádný audit seed, metadata insert, replay, upload/queue/model call pro výrobu důkazu. Převzít ledger: historicky 0 HTTP GET a 0 push/rollout/recovery; maximálně min(shared remainder, 12 GET celkem napříč kandidáty), 0 nových business/audit writes/POST. Zapsat spotřebu před requesty; novým buildem budget neobnovit.
11. Po rollout provést přímý authenticated steps GET se skutečně pozorovaným run/attempt; assert nonempty extraction ID/type/stage/schema, partial/no-store, známou duration/safe error a absenci business values. V témže budgetu ověřit document/run parity, izolaci jiného attempt, pages bez extraction, continuation pokud fixture dovolí, cross-run/operation token rejection a negativní auth/scope podle skutečné policy. Read503 hermeticky; /health, vymyšlený run a 200empty nejsou live extraction proof.
12. Vlastní package/router/DTO chyby z HTTP opravit test-first ve stejném scope, znovu gates a guardovaný rollout v původním budgetu. Při skutečném denial/chybějícím guardu/interface/fixture dodat Jackiemu konkrétní artifact digest, target, config diff, recovery a přesný zbývající operator krok v TÉŽE dodávce, potom dokončit ověření; nic neobcházet a neuzavírat source-only DONE.
13. Do taskové runtime evidence appendnout časy, fixture/request IDs, safe status/schema assertions, ledger, source/wheel/image/target operation/digest a oddělené SOURCE / INSTALLED / DEPLOYED / LIVE-FUNCTION-VERIFIED. Historické neúspěchy ponechat; úspěch vyžaduje deployed + nonempty live funkci, jinak přesný blocker. Použít validate-implementation, scoped code-review a write-review-report; acceptance s caller manifestem, zachovat gates. Jako poslední krok save-learning.

## TDD
- Implementace TDD cyklu dle skill:tdd; zachovat původní helper-generated proof `plans/checkpoints/task-12f46945-d733-47dc-b0e9-b8c9746fd7c2.red-green-proof.md` (genuine RED: authorized 200 vracelo items=[]; GREEN: 4 passed). Pozdější regrese nevydávat za původní RED.
- Test file: `be-intake/tests/test_processing_monitor_extraction.py` již existuje; reuse explicitní intake/monitor fixtures, HEADERS/event a stávající testy. Níže je spustitelný reprezentativní skeleton existujícího testu, nikoli pokyn přidat duplicitní soubor.
- Run command z repo root: `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_extraction.py`.

```python
from fastapi.testclient import TestClient
from test_monitor_file_received import intake  # noqa: F401
from test_processing_monitor_routes import monitor, HEADERS, event  # noqa: F401

def test_extraction_terminal_only_http_observation(monitor):
    main, _, _, _, _, table = monitor
    table.query.return_value = {"Items": [event(
        "extraction-terminal", type="StepFinished", sequence=7,
        run_id="run-test", attempt_no=1, stage="extraction")]}
    path = "/v1/cases/case-test/processing/documents/doc-test/runs/run-test/steps"
    with TestClient(main.app) as client:
        response = client.get(path, params={"attempt_no": 1, "limit": 1}, headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    body = response.json()
    assert body["coverage"] == "partial"
    # Historical genuine RED: [] instead of the persisted terminal.
    assert [item["event_id"] for item in body["items"]] == ["extraction-terminal"]
    assert not ({"page_number", "duration_ms", "status", "fields"} & body["items"][0].keys())
    table.query.assert_called_once()
    assert table.query.call_args.kwargs["Limit"] == 1
    table.scan.assert_not_called()
```

| Test | RED | GREEN |
|---|---|---|
| test_extraction_terminal_only_http_observation | Historicky HTTP200, items=[] | Jeden terminál bez syntetického startu/duration |
| test_extraction_facts_parity_privacy_and_schema[StepFinished/StepFailed/None] | Historicky chybějící extraction IDs | Start→finish/failure nebo start-only; parity a pages exclusion |
| Nová vlastní oprava, pouze pokud nalezena | Konkrétní behaviorální assertion před produkční opravou | Tentýž command/assertion projde; oddělený nový proof cyklus |

- Pokud skeleton již prochází, zaznamenat characterization GREEN a navázat na historickou proof; nevyrábět RED chybným importem, chybějící fixture, falešným očekáváním nebo revertingem funkce.

## Testing
- Spustit focused command; ověřit start→finish/failure, terminal-only bez RunQueued/AttemptStarted, missing end unknown, dvě stages/runy/attempts, Decimal duration JSON a safe error, stejné IDs právě jednou v document/run events a žádnou extraction v pages.
- Ověřit empty items + continuation/ExclusiveStartKey, jediný Query/request a žádný Scan; cross-case/document/run/attempt/operation/malformed cursor odmítnout před Query. Nezaměnit pokus za latest/business snapshot.
- Zachovat missing/invalid attempt400, auth403, scope404, required auth/membership/read/decode503 a private,no-store na všech chybách; OAS30Validator ověří pozitivní response i zakázané page_number/fields/status/model_call/business properties proti jedinému YAML.
- Spustit `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests`; zachovat source/page/cache observations, všechny předchozí GET a sole-contract gates.
- Spustit registrovaný gate přesně `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` (timeout 300 s) a `git diff --check`; zapsat skutečné exit codes, neopisovat historické počty jako nové výsledky.
- Po build/image smoke provést kroky 5–12; installed hermetická fixture není deployed/worker proof. Neprovádět cloud fault injection, nové paid calls/downstream case processing, grant/IAM widening ani destructive writes.

## Files
| Cesta | Akce |
|---|---|
| be-intake/app/processing_monitor_step_routes.py | Reuse/úzce opravit extraction allowlist/DTO/operation adapter |
| be-intake/tests/test_processing_monitor_extraction.py | Reuse focused HTTP/schema/isolation testy; rozšířit doložené mezery |
| be-intake/tests/test_processing_monitor_step_routes.py | Zachovat source/page a již upravené extraction očekávání |
| be-intake/app/processing_monitor_routes.py | Jen nezbytná vlastní DTO parity korekce; auth/reader facade reuse |
| be-document-processing/contracts/openapi-processing-monitor.yaml | Validovat/úzce opravit vlastní steps/event DTO, ostatní zachovat |
| be-intake/tests/image_processing_monitor_smoke.py, be-intake/app/Dockerfile | Reuse installed wheel/router smoke; opravit jen prokázaný packaging defect |
| be-document-processing/src/document_processing/audit/audit_queries.py, be-intake/app/main.py | Ověřit existující reader/registraci, bez plánované přestavby |
| plans/monitoring/task-12f46945-d733-47dc-b0e9-b8c9746fd7c2-runtime-evidence.md | Append artifact/deploy/HTTP ledger, assertions a blocker; uchovat historii |
| plans/checkpoints/task-12f46945-d733-47dc-b0e9-b8c9746fd7c2.red-green-proof.md | Zachovat původní proof; nové cykly pouze pro nové opravy |

## Progress
- [x] Získat kanonickou cestu, načíst současné source/contract/test/evidence a připravit tento aktualizovaný plán.
- [x] Zahrnout TDD pokračování, registrované gates, instalaci, guardovaný rollout a bounded live assertions.
- [ ] Při realizaci doložit aktuální source/installed/deployed/live stavy; plánovací běh tyto operace nespouští.
