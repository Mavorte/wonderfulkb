# Plan 2026-10-20: Monitoring MVP: skutečná worker → HTTP integrační cesta

## Analysis
- Vycházet z `runtime-producer-context-contract.md` a `worker-instrumentation-contract.md`: `Context.send` zahazuje SQS response, claim vrací string, worker předává pouze case/document a warm-cached Options; nezaměnit audit package za podporovaný producer.
- Ověřit novější `processing_monitor_authorization.ServiceDocumentAuthorizer` proti owner schválené policy a deployed konfiguraci; historické hlášení absence auth není důkaz aktuálního stavu.
- Při retry zachovat tento soubor; `inspect_plan_file` vyžaduje prefix `# Plan`, samotné správné `##` sekce neodstraňují `invalid_header`.
- Zachovat rozpracované změny ostatních tasků; Dockerfile intake již instaluje audit wheel, worker build jej dosud nestaguje.
- Použít existující `audit_page_observations.py`, lifecycle reducer a jediný OpenAPI; aktuální `main.py` registruje monitor i lifecycle router a Dockerfile kopíruje oba. Ověřit jednotlivé operation/DTO a celý artifact, neplánovat jejich opětovné vytvoření.

## Approach
- Nejdříve vyžádat od execution ownera kanonický build/source manifest a schválené rozhraní dle `runtime-producer-context-contract.md`: stabilní enqueue identity s confirmed/rejected/ambiguous výsledkem, atomický claim+attempt a explicitní immutable context. Při trvající absenci zapsat konkrétní blocker; nepřidávat counter/outbox ani měnit retry/lease/claim/fencing.
- Potvrdit s intake ownerem platnost existujícího `ServiceDocumentAuthorizer`, trusted SERVICE policy, current/retained membership a dostupnost test credentials přes bezpečného ownera. Bez tohoto vstupu je možné hermetické ověření modulu, nikoli autorizovaný live success.
- Reuse `AuditStore`, `audit_queries`, `audit_page_observations` a lifecycle reducer; producer prerequisite a jednotlivé read dodávky musí dodat vlastní implementaci a runtime evidence. Tato integrace jejich deployment neodkládá ani nenahrazuje.
- Aplikovat learnings: producer identity nepřebírat z receive count/audit řádků; ověřit skutečný Moto Decimal round-trip a oddělit local adapter od AWS proof. Recall backend `local`, collection `wonderfulkb-learnings`, diagnostic `Collection not found`; použité zdroje: `2026-10-20_attemptstarted-audit-contract-preserves-producer-identity.md`, `2026-10-20_audit-envelope-decimal-round-trip.md` a FileReceived scope pravidla v `learnings/architecture/` (jejich historická source-only hranice neplatí pro tuto dodávku).
- Použít `skill:tdd` při implementaci, `validate-implementation` při závěrečné validaci a `save-learning` jako poslední workflow; registry gates převzít z injektovaného kontextu bez čtení registru. Při skutečné AWS práci načíst příslušné AWS skilly pro Lambda/App Runner/IAM/SDK, nikoli zavádět nový framework.
- Zachovat task-wide ledger a Case Client limity dle načtených Case Client learnings z 2026-10-19; equivocal POST neopakovat. Při lifecycle porovnání použít canonical `run_status`/`attempt_status` a uchovat konfliktní evidence dle `2026-10-20_audit-lifecycle-canonical-status-conflict-evidence.md`.

## Implementation
1. Zachytit pracovní stav root i dotčených nested repozitářů a source digests; zachovat souběžně rozpracované změny. Porovnat skutečné prerequisites s oběma producer kontrakty a ověřit schválení novějších rozhraní. Trvající identity/provenance/auth mezery ponechat blokující pro producer/live část a předat ownerovi přesný chybějící interface v témže zadání.
2. Po splnění execution prerequisite začít behavioral RED testem níže. Sdílet Moto resources pro business tabulky, SQS/S3 a audit; používat skutečné `enqueue_document`, `worker_handler.handler`, pipeline `run_document`, listener, conditional persistence, Query a intake app. Fake pouze externí provider/blob/queue/secret ports; nezaměnit pipeline, claim, listener nebo reader za předem připravené eventy. Registraci stream→enqueue handleru ověřit samostatným rozšířením stejného harnessu; Moto stream není živá event-source mapping.
3. Připojit pouze ownerem dodané skutečné composition seams; rozšířit scénáře přes pipeline fixtures. Zachytit forwarding contextu pomocí pass-through observeru skutečných callers, porovnat `case_id/document_id/run_id/attempt_no/event_id` s uloženým eventem a HTTP evidence; žádný testem přidělený runtime run/attempt. Duplicate delivery musí zachovat claim business chování i audit idempotenci; výpadek sinku nesmí měnit business výsledek, audit read chyba musí vrátit 503.
4. Doplnit úzké integrační opravy existujících owners: worker `build.sh`/Dockerfile/requirements musí zahrnout skutečně instalovatelný audit package; intake zachovat wheel instalaci a kopírovat všechny skutečně používané route moduly. U chybějících GET/event decoderů reuse dokončené read práce, případný diff omezit na vlastní operation/DTO v jediném OpenAPI; nepřepisovat ostatní operace. Nevyrábět nový server, business stage ani druhý kontrakt.
5. V `worker-instrumentation-contract.md` a smoke runbooku zapsat capability matici sections1–10: confirmed intake/enqueue/claim; source validation; nové page outcomes; cache reuse bez nového model call/duplicitního completion; extraction; signature disabled/returned failure; publication včetně partial write; retry a attempt/run terminal. Pro každou uvést actual caller, success/failure/retry fragment a identitu, test/evidence nebo explicitní `unsupported: no actual producer`. Partial publish nesmí vyrobit RunFinished; absence/lost terminal znamená unknown, explicitní capability not_instrumented nesmí vzniknout pouze z absence dat. Lost/late/duplicate pozorování ověřit fault injection do transportu audit zápisů produkovaných workerem, bez ručního event seedu.
6. Před in-place AWS TEST nasazením zjistit účet/region a skutečné owner resources `wonderfulkb-trigger-worker`/enqueue a `wonderfulkb-ingest`; readback resolved image digest, Lambda RevisionId, App Runner service/operation/config a existující env/IAM/table needs. Zaznamenat jen bezpečný diff/checklist (`AUDIT_TABLE_NAME`, existující auth-secret reference, scoped PutItem/Query potřeby), bez credentials a broad grants. Uchovat ověřený dostupný recovery image/ZIP a chráněnou konfiguraci přes ownera; recovery není script `deploy.sh rollback`, který maže stacky. `deploy.sh` obsahuje placeholder account a create-oriented flow, proto jej nespouštět naslepo; použít potvrzený existující in-place owner postup.
7. Sestavit immutable artifacty a manifest celého build contextu včetně package wheel/version/hash a source refs/dirty diff digest; ověřit imports z obou image bez checkout/PYTHONPATH mountu pod runtime userem. Intake build: `docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:worker-http-task-ac9bcb19 .`; worker staging `bash be-validator-agent/trigger/build.sh`, následně owner image build ze skutečného staged contextu. Dva shodné moduly nejsou provenance image. Instalaci/build provést až v implementaci.
8. Nasadit pouze guarded in-place do potvrzených TEST owners: Lambda update s aktuálním RevisionId; App Runner exclusive owner guard, žádná souběžná operace, bezprostřední porovnání konfigurace/digestu před update a readback po něm. Při driftu zastavit, při regresi obnovit ověřený recovery artifact přes stejné guards. Nepřidávat permission/scheduler/resource framework.
9. Agent provede bounded synthetic upload→existující stream/queue→worker→HTTP, ověří skutečně nasazené digests a opraví scope chyby. Při skutečném denial/runtime absenci Jackie provede přesně pojmenovaný operator krok v témže zadání a vrátí redigované příkazy, exit status, operation/revision IDs a HTTP evidence; denial neobcházet a task neuzavřít source-only.

## TDD
- Implementace TDD cyklu dle skill:tdd; důkaz uložit do `plans/checkpoints/task-ac9bcb19-d1d0-4bed-a469-f7e503825caf.red-green-proof.md`. Nyní pouze plán; skeleton nespouštět ani neměnit implementaci. Chybějící dependency/fixture/import není behavioral RED.
- Nový test: `be-validator-agent/pipeline/tests/test_processing_monitor_worker_http_integration.py`; reuse zdejší `aws_env`, `ingest`, `make_options`, `text_pdf`. Nejprve potvrdit owner interface prerequisite; skeleton používá dnešní reálné importy, po schválení pouze upravit oficiální composition config, nikoli fabrikovat identity.
- Focused příkaz z rootu: `env PYTHONPATH=be-validator-agent:be-document-processing/src:be-intake/app be-document-processing/.venv/bin/python -m pytest -q be-validator-agent/pipeline/tests/test_processing_monitor_worker_http_integration.py`.

```python
import importlib.util
import json
from pathlib import Path

import boto3
from fastapi.testclient import TestClient
from trigger import common, worker_handler
from .conftest import BUCKET, REGION, text_pdf


def test_real_worker_observations_reach_http(aws_env, ingest, make_options, monkeypatch):
    # External resources are Moto; no event is constructed or seeded here.
    ddb = boto3.resource("dynamodb", region_name=REGION)
    ddb.create_table(
        TableName="test-worker-audit", BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"} for k in ("pk", "sk")],
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"},
                   {"AttributeName": "sk", "KeyType": "RANGE"}],
    )
    ingest("c1", "d1", text_pdf(["Benign synthetic contract document with sufficient native text."]))
    sqs = boto3.client("sqs", region_name=REGION)
    queue = sqs.create_queue(QueueName="worker-http") ["QueueUrl"]
    ctx = common.Context(queue_url=queue)
    for key, value in {"API_KEY": "test-key", "RAW_BUCKET": BUCKET,
                       "DOCS_TABLE": "wonderfulkb-uw-documents",
                       "AUDIT_TABLE_NAME": "test-worker-audit",
                       "MONITOR_AUTH_SECRET_ARN": ""}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(worker_handler, "_ctx", ctx)
    monkeypatch.setattr(worker_handler, "_options", make_options())
    monkeypatch.setattr(worker_handler, "run_document", None)  # resolve actual pipeline
    assert common.enqueue_document(ctx, "c1", "d1") == "queued"
    msg = sqs.receive_message(QueueUrl=queue)["Messages"][0]
    result = worker_handler.handler({"Records": [{"messageId": msg["MessageId"], "body": msg["Body"]}]})
    assert result == {"batchItemFailures": []}
    assert ctx.get_row("c1", "d1")["processing_status"] == "completed"

    # Exercise the existing authorizer against a local SERVICE policy port.
    from processing_monitor_authorization import ServiceDocumentAuthorizer
    import hashlib
    from types import SimpleNamespace
    policy = {"schema_version": 1, "credentials": [{
        "credential_id": "test", "sha256": hashlib.sha256(b"local-token").hexdigest(),
        "state": "active", "principal_type": "SERVICE", "principal_id": "test-reader",
        "grants": [{"case_id": "c1", "documents": [{"document_id": "d1", "membership": "current"}]}],
    }]}
    source = Path(__file__).resolve().parents[3] / "be-intake/app/main.py"
    spec = importlib.util.spec_from_file_location("worker_http_intake", source)
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)
    main.app.state.lifecycle_authorize_read = ServiceDocumentAuthorizer(
        SimpleNamespace(get_secret_value=lambda **kw: {"SecretString": json.dumps(policy)}),
        "arn:aws:secretsmanager:eu-central-1:123456789012:secret:local-worker-http", ctx.documents,
    )
    with TestClient(main.app) as client:
        response = client.get("/v1/cases/c1/processing/documents/d1/runs",
                              headers={"x-api-key": "test-key", "Authorization": "Bearer local-token"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["coverage"] == "partial"
    assert response.json()["items"], "RED: actual worker emits no auditable run observations"
```

| Test | RED | GREEN |
|---|---|---|
| `test_real_worker_observations_reach_http` | Business completed, GET200 items empty: missing actual producer integration | GET obsahuje skutečný run a evidence z téhož worker volání |
| Rozšíření stejného testu: caller→store→GET identity | Chybějící/nepředaný schválený context | Přesná shoda identity a zachované immutable context přes warm calls |
| Branch/fault parametrizace | Chybějící supported observations nebo nesprávně domyšlený terminal | Níže uvedené branch assertions, bez fabricated events |

## Testing
- Hermeticky rozšířit skeleton o document/run events, attempts, steps, pages, lifecycle detail/audit dle skutečně dodaných routes; u chybějící route zaznamenat read-owner blocker, ne obcházet registraci mountem test-only routeru. Local SERVICE policy je fixture externího secret portu, nikoli důkaz live entitlementu.
- Pro každou podporovanou section pokrýt krátký success/failure/retry fragment; disabled signature nesmí znamenat provedenou kontrolu, returned failure nesmí znamenat success, cache reuse musí mít nulový přírůstek fake model callů. Extraction bez skutečné stage zůstane unsupported. Partial publication, ztráta audit zápisu i pozdní/duplicate delivery nesmí vytvořit úplný/nejnovější lifecycle.
- Ověřit real conditional put/read round-trip, idempotenci a bounded document Query; transport fault wrapper smí zadržet/dropnout pouze skutečné producer zápisy. HTTP 403 pro neplatnou identitu/shared-key-only, 404 pro cizí/neexistující document scope, private/no-store včetně chyb, read503 místo empty success; scope-bound cursor odmítne jiný operation/run/attempt, legitimní empty continuation zůstane zachována. Žádný whole-history Scan/scan-until-filled.
- Spustit focused test, poté dotčené pipeline/trigger/intake a audit suites projektovým Pythonem; trigger suite spouštět z `be-validator-agent/trigger` s korektním PYTHONPATH, známou `test_backfill.py` collection chybu zaznamenat odděleně. Ověřit YAML/routes/fixtures pomocí `be-document-processing/tests/test_monitor_openapi_observation_contract.py` a existujících route testů; neopakovat implementaci page mapperu.
- Povinná registrovaná brána přesně: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` (timeout 300 s). Zachovat selhání i následné opravy jako samostatnou evidence.
- V `worker-http-deployment-smoke.md` zapsat konkrétní existující upload URL z owner readbacku, fixture SHA256 a lokální generator/version, source/wheel/image digests, instalaci/build/import příkazy, guarded update příkazy a skutečné výstupy. Live default cap: nejvýše 1 benignní PDF/1 page/1 upload POST, max 20 GET celkem včetně negativních kontrol, 10 minut, žádné ruční queue send/replay/reprocess, žádná nová placená inference. Před POST prokázat, že podporovaná cesta na fixture nevolá placené providers ani navazující case-step; není-li to možné bez změny business/config scope, explicitní fixture/provider blocker a konkrétní krok pro Jackie místo spuštění. Automatic retry rozpočet převzít z existující queue a nesnižovat/měnit; nevyvolávat live fault scénáře.
- Live ověřit source→resolved artifact→deployment revision→skutečné worker invocation→audit identity→autorizovaný HTTP partial observation, nikoli pouze health/403. Vést ledger POST/GET/write IDs bez obsahů/tokenů; ambiguous POST nereplayovat. Zapsat cleanup pouze existujícím supported operátorem na přesné fixture IDs; pokud není delete operátor, evidovat ponechanou scoped fixture, nic nevymýšlet. Zachovat Case Client fixture a jeho dřívější deployment/POST rozpočty.
- Vyplnit evidence tabulku níže po každém kroku; nepřepisovat historické failed/inconclusive záznamy. Datum/verze reference je povinné, minulou reprodukovatelnost neodvozovat z dnešního checkoutu.

| Level | Požadovaný důkaz při implementaci | Stav tohoto plánování |
|---|---|---|
| source | owner interfaces + refs/dirty digests + capability matrix | Prozkoumáno; producer identity/build prerequisite blokuje |
| hermetic | focused RED/GREEN + caller/store/HTTP identity assertions | Neprovedeno |
| installed | oba skutečné artifact imports bez checkoutu, runtime user, wheel digest | Neprovedeno |
| deployed | TEST owner/recovery, revision guard, resolved deployed digests/config | Neprovedeno |
| live-function-verified | bounded synthetic worker invocation a stejné identity přes live HTTP | Neprovedeno; runbook ani lokální GREEN nejsou náhrada |

## Files
| Soubor | Plánovaná změna |
|---|---|
| `be-validator-agent/pipeline/tests/test_processing_monitor_worker_http_integration.py` | Nový full-path test ve skutečném fixture layoutu; žádné event seeding helpers |
| `be-validator-agent/trigger/{common.py,worker_handler.py}`, `pipeline/run.py` | Pouze integrace již schválených owner seams a narrow fixes; missing execution design je prerequisite |
| `be-validator-agent/trigger/{build.sh,Dockerfile,requirements-worker.txt}` | Package inclusion a skutečný staged artifact import |
| `be-intake/app/{main.py,processing_monitor_lifecycle_routes.py,processing_monitor_authorization.py,Dockerfile}`, `be-intake/tests/` | Reuse existující auth/routes/image; jen integračně zjištěné own-scope chyby |
| `be-document-processing/src/document_processing/audit/` | Reuse event/listener/store/query/reducer/page mapper; pouze prokázané chybějící boundary/decoder diff |
| `be-document-processing/contracts/openapi-processing-monitor.yaml` | Jen vlastní operation/DTO drift, zachovat ostatní práci |
| `plans/monitoring/{runtime-producer-context-contract.md,worker-instrumentation-contract.md,worker-http-deployment-smoke.md}` | Zachovat historické blockers; připojit owner řešení, capability matrix a skutečný smoke evidence/runbook |
| `plans/checkpoints/task-ac9bcb19-d1d0-4bed-a469-f7e503825caf.*.md` | Red/green, guards/recovery references a oddělené runtime výsledky bez secrets |

## Progress
- [x] Opravit při planning retry titulní header na `# Plan YYYY-MM-DD: …`; zachovat povolené přesné `##` nadpisy a původní kanonickou cestu.
- [x] Ověřit `inspect_plan_artifact` projektovým Pythonem: `status=valid`, canonical parent `plans/`, všech sedm povolených sekcí; samostatně zkontrolovat všechny nadpisy a nepřítomnost status/TODO/WIP markerů.
- [x] Vytvořit kanonický plán pro `task-ac9bcb19-d1d0-4bed-a469-f7e503825caf`.
- [x] Prozkoumat skutečné callers/package/auth/build a monitoring kontrakty; PlantUML v repozitáři nenalezen.
- [x] Připravit konkrétní TDD a podmíněnou implementaci se skutečným deployment/live dokončením.
- [ ] V implementační fázi vyřešit execution-owner prerequisites, poté provést TDD, gates, artifact imports a guarded AWS TEST smoke; nyní nebyly provedeny.
