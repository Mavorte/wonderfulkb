# Plan 2026-10-20: Monitoring worker: skuteční producenti a worker→HTTP důkaz

## Progress
- [x] Získat kanonickou cestu plánu pro `task-b0db5177-2f43-4036-b080-af1ca7d143d5`.
- [x] Opravit příčinu `invalid_header`: zachovat stejný soubor a použít první řádek `# Plan YYYY-MM-DD: title`; ověřit také přesný allowlist všech sekcí.
- [x] Ověřit aktuální execution interface, producenty, HTTP/auth a artifact owners.
- [x] Doplnit konkrétní implementační kroky, behavioral TDD a runtime gates.
- [x] Ověřit plán pomocí `km_tasks.task.artifacts.inspect_plan_artifact`: `status=valid`; samostatně ověřit všech sedm povolených sekcí a syntaxi Python skeletonu přes `ast.parse`, bez spuštění testů.
- [ ] Při implementaci provést RED/GREEN, instalaci, guarded deployment a bounded live proof; současný plán není runtime evidence.

## Analysis
- Reuse `trigger/processing_execution_context.py:ExecutionContext`, `processing_execution_claims.py:allocate/claim`, `common.py:enqueue_document/claim_document`; existují confirmed send a atomic claim+ordinal, build již zahrnuje execution moduly i audit. Nevytvářet druhý allocator.
- Doplnit chybějící orchestration hooks v `pipeline/run.py`; `execution_context` se již předává explicitně, ale stage/terminal producers zde nejsou. `trigger/tests/test_audit_instrumentation.py` má pouze signature assertion, nikoli behavioral proof.
- Ošetřit source dispatcher: přímé volání `ctx.audit_listener` po business commitu může při vadném injected listeneru vyhodit chybu, i když standardní listener izoluje sink chyby.
- Aktualizovat historické capability tvrzení v `runtime-producer-context-contract.md` a `worker-instrumentation-contract.md` podle nových symbolů; nepřepisovat původní historickou evidence.
- Reuse serverový credential→SERVICE principal→case grant a exact document membership v `be-intake/app/processing_monitor_authorization.py`; ověřit jeho skutečné runtime nastavení zvlášť.
- Vytvořit chybějící `plans/monitoring/worker-http-deployment-smoke.md`; intake Dockerfile již instaluje audit wheel a existující route moduly, prokázat až finální image import.

## Approach
- Zachovat existující orchestration, audit package, read API a owner deployment postupy.
- Před každou změnou znovu porovnat aktuální stage-owner source a testy; převzít dodané hooky, doplnit jen chybějící caller/injection a nezdvojovat eventy. Samotná existence event DTO/readeru není producer capability.
- Použít `mvp-reference-20261019.md`, proposal `proposal-20261019-150954-c8891f` / `slice-retry-terminal` a jediný `be-document-processing/contracts/openapi-processing-monitor.yaml`; jejich historické source mezery konfrontovat se skutečnými symboly výše.
- Aplikovat learnings `2026-10-20_worker-claim-identity-vs-confirmed-retry-and-caller-isolation.md`, `2026-10-20_atomic-execution-ledger-resource-transaction-serialization.md` a `2026-10-19_case-client-source-contract-vs-deployed-state.md`: owner-issued identity, caller fail-open i po commitu a oddělená source/deployed evidence. Recall při této revizi použil backend `local`, collection `wonderfulkb-learnings`, diagnostic `Collection not found: wonderfulkb-learnings`; fallback není blocker.
- Pro auth fixture použít `2026-10-20_worker-http-plan-auth-fixture-secret-reference.md`: skutečný `AuthorizationSecretSource`, platné lokální ARN a fake pouze Secrets Manager transport. Pro plán aplikovat `2026-10-20_steps-plan-retry-validate-header-and-exact-sections.md`: canonical validator doplnit vlastní kontrolou všech nadpisů. Relevantní monitoring PlantUML v `docs/` nebyl nalezen; nevyrábět nový diagram ani architekturu.
- Použít skilly `tdd` pro behavioral proof, `validate-implementation` pro finální API/architekturu a `save-learning` po dokončení; registrované gates z injected project context zachovat. Pro budoucí AWS operace použít AWS MCP a příslušné serverless/container/IAM skilly podle skutečné změny; AWS CLI přes Bash nespouštět.

## Implementation
1. Zachytit root/nested Git status, source refs a dirty-file digests, inventář stage→symbol→caller→listener→test→artifact; zachovat rozpracovanou práci ostatních owners. Existující pure page/lifecycle mappery a jejich focused testy pouze reuse. Chybějící symbol uvést přesně, ne nahradit audit seedem.
2. Jako první změnu vytvořit focused test níže a získat accepted behavioral RED přes `skill:tdd`. Připravit lokální project venv a nutné test závislosti před capture; collection/import/setup error neuznat jako požadovaný RED.
3. Rozšířit existující audit listener o nedodané stage/runtime metody a fail-open dispatch; validaci, stabilní event IDs, allowlist/serialization a persistence držet uvnitř audit package. Izolovat i chybu listener lookup/factory/metody po commitu, nikoli jen `AuditStore.put`; neměnit business výsledek, pořadí zápisů, původní exception ani retry. Kontext předávat explicitně po dobu execution, nikdy přes warm-cached Options identity/global/env.
4. Doplnit skutečné callers podle následující matice; čas měřit monotonic na skutečném kroku, bezpečné error codes mapovat bez obsahu/tracebacků. Options může držet listener dependency, nikoli per-run mutable identity. Žádné nové business stages kvůli coverage.

| Boundary / caller | Konkrétní integrace a negativní assertion |
|---|---|
| `common.enqueue_document`, `claim_document` | Reuse RunQueued až po confirmed send, AttemptStarted jen po atomic successful claim; rejected/ambiguous send a lost claim nesmí emitovat tyto success observations. |
| `pipeline.run.run_document`: download/size/PDF/source checks | Ohlásit jen skutečně provedenou source validation; neexistující hash/config validation neoznačovat supported. Předčasné `_fail` větve mají pouze doložitelný failure fragment. |
| `transcribe_scans`, `pdfmod.extract_pages` | Kontext do skutečných page/transcription a extraction callers; page terminal bez duplicitního StepFinished. Text-layer, blank, no_vision a budget rejection neoznačovat za nový model call. |
| Cache hit v `transcribe_scans` | PageCacheReused jen po skutečném přečtení/validaci použité cache, current attempt/page; žádný nový PageCompleted/Step terminal/model call. `_try_reuse` dokumentového výsledku nevydávat za page-cache producer. |
| `_signatures`, redaction branch | Rozlišit disabled/kept-existing, detector failure a returned failure od úspěchu. Emitovat pouze reálnou detekci; redaction-owned detekci připojit jen přes skutečný owner interface, jinak přesný unsupported symbol. |
| `run_document`, `_finish_reused`, `_fail` | Publication dokončena až po všech povinných vlastněných S3/report/analysis a případných job/document writes na dané větvi; fail-open `_register_hash` není nová mandatory business operace. Partial write neemitovat ResultPublished ani RunFinished. Samotný návrat row není publication proof. |
| `worker_handler.process_document`, `_remember`, `handler` | AttemptFinished při skutečném návratu či exception se stejným claim kontextem; RunFinished jen při doloženém skutečném run terminálu. Exception→queued/batch failure sama není potvrzené RetryEnqueued. |
| SQS redelivery / `dlq_handler` | Inspektovat skutečný retry confirmation a owner terminal identity; `queue_case` je downstream case message, nikoli document retry. RetryEnqueued pouze při doložené potvrzené retry hranici. Pokud SQS-managed redelivery žádnou takovou caller hranici nemá, označit ji unsupported a předat konkrétní execution-owner interface blocker; neměnit queue/retry mechanismus. DLQ run terminal vázat jen na prokázanou current generation; nevyvozovat attempt z receive count/času/UUID ani nevytvářet claim pro max-attempt terminal. |

5. Dokončit shared-state hermetický harness: fake pouze provider/blob/queue/DB transport, real source enqueue/claim, worker handler, pipeline, audit listener/store/query, existing intake FastAPI routes a credential binding/grant/membership logika. Všechny HTTP events musí pocházet z tested producers. Přidat benign lokálně generované fixtures, capture actual calls a porovnat event/run/attempt identity i durace napříč calls/persistence/GET.
6. Ověřit všechny existující monitoring GET: document/run events, attempts, steps/pages, runs/detail/audit. Reuse skutečné auth policy source seam; fake pouze Secrets Manager/provider transport. Bez trusted runtime credential→principal→case grantu předat Jackie přesný ARN/config/owner požadavek; samotný upload key není oprávnění. DTO/OpenAPI upravit jen pro vlastní chybějící pole/operace a zachovat ostatní práci.
7. Po GREEN provést relevantní Python matici a registrovaný test/build, instalovat/buildovat pomocí existujících owners. Worker `trigger/build.sh` již kopíruje audit a execution moduly do light/image; ověřit všechny nové moduly i light enqueue/DLQ imports. Intake stavět z root contextu dle jeho README, wheel skutečně nainstalovat. Finální linux/amd64 worker a intake image spustit na import proof: audit event/listener/store, handler/pipeline, `main:app` a všechny routery.
8. Vytvořit canonical source/artifact manifest: root+nested refs, dirty diff digest, kompletní build-input manifest včetně requirements/lock či resolved versions, Dockerfile/context digests, wheel/light ZIP digest, immutable image digest obou owners a import výstup. Dvě matching source files ani starý deployed digest nejsou provenance nového buildu.
9. Připravit úzký config/resource diff přes `plans/handoffs/aws-runtime-readiness-20261020.md`: `EXECUTION_TABLE`, `AUDIT_TABLE_NAME`, skutečné analysis/documents/bucket/queue binding, `PROCESSING_MONITOR_AUTHORIZATION_SECRET_ARN` a existující compatibility auth binding. Host/native owner dodá jen aktuálně nutné execution/audit resources a resource-scoped práva (execution transactions, audit Put/Query, exact secret read); žádné credentials v evidenci, další runtime tabulka/framework či broad IAM.
10. Před AWS změnou přes AWS MCP ověřit STS účet `609394381050`, region `eu-central-1` a odpovídající owner roli. Lokální tool prostředí explicitně `AWS_PROFILE=ai-hackathon AWS_REGION=eu-central-1 AWS_DEFAULT_REGION=eu-central-1`; MCP session ověřit samostatně, nepředpokládat převzetí profilu. Neprovádět nový login/default fallback; nesoulad identity či denial předat Jackie jako přesný blokující operator krok.
11. Znovu načíst existující worker/enqueue/DLQ Lambda revision/config/code, App Runner image/config/operations, stack parameters/tags a ECR digests; sanitizovat evidence. Uchovat ověřený recovery image/ZIP/config artifact. Bez probíhající cizí operace aplikovat jen in-place diff, Lambda Update* s očekávaným RevisionId, stack přes reviewed no-replacement change set; App Runner čerstvý describe + operation guard a kontrola očekávaného image/config před i po operaci. Při driftu zastavit a přepočítat diff. Nespouštět slepě `deploy.sh`: má historický profil `hackathon`, account placeholder a bootstrap/rollback kroky; reuse jeho build/native owner, nikoli destructive rollback.
12. Nasadit nový připravený artifact do existujícího AWS TEST cíle, ověřit resolved Lambda image/ZIP hash, App Runner deployment/image digest, zachované env/roles a úspěšné operation stavy. Každý vlastní reader fix nasadit a HTTP ověřit v rámci jeho dodávky; integrace nenahrazuje předchozí read-owner deployment evidence. Recovery provést guarded návratem na ověřený artifact/config, ne mazáním stacku.
13. Do `worker-http-deployment-smoke.md` zapsat skutečné podporované upload/queue operators a bezsecretové příkazy/API kroky z inspection. Použít existující vyhrazený synthetic case a lokální benign PDF; před uploadem prokázat zero-paid-provider a no-downstream-case-step pro tuto execution v nasazeném configu/calleru. Aktuální worker vždy zvažuje `queue_case` a `no_vision` je Options flag, nikoli prokázaný runtime switch: pokud bezpečnou supported cestu nelze doložit, uvést přesný config/interface blocker a nic neuploadovat. Žádný nový test mode nebo scheduler zásah.
14. Pro doloženou bezpečnou cestu zaznamenat budget nejvýše 1 nový benign upload (1 PDF, ≤2 stránky), 0 placených provider calls, 0 downstream case steps, nejvýše 20 monitoring GET během 5 minut; předem odečíst dosavadní spotřebu stejného zadání a respektovat přísnější existující owner budget, retry plánu jej neresetuje. Sledovat existující upload→stream→queue→worker→audit→HTTP, získat event/run/attempt IDs z produceru, nikoli vlastní seeding. Při ambiguous write neprovádět replay; jen bounded readback a blocker. Scope auth negative/live GET ověřit bez změn cloud fault konfigurace. Live 503 nepotvrzovat injekcí poruchy; doložit hermeticky, pokud skutečná live situace nenastane.
15. Zapsat skutečné časy, argv/API operace, exit/status, immutable digests, bounded correlation a sanitizované HTTP assertions; označit neprovedené kroky jako neprovedené. Fixture cleanup jen skutečným supported owner operátorem, jinak evidovat ponechané scoped IDs/TTL absenci; nevymýšlet delete endpoint. Jackie dokončí konkrétní runtime-inaccessible krok v témže zadání, následně znovu ověřit artifact/live výsledek. Při missing interface/denial ponechat nedokončený runtime závěr, neopravovat historii na zelenou.

## TDD
- Implementace TDD cyklu dle `skill:tdd`; nový proof patří do `plans/checkpoints/task-b0db5177-2f43-4036-b080-af1ca7d143d5.red-green-proof.md`, nikoli pod starý checkpoint ac9bcb19.
- Vytvořit `be-validator-agent/trigger/tests/test_processing_monitor_worker_http_integration.py`; pytest/Moto pro stateful provider ports, TestClient pro existující FastAPI. Skeleton níže rozšířit v témže souboru o tabulku v Testing; zachovat skutečné importy/orchestration, nepřekrýt `_pipeline_run` ani `run_document` fake implementací.
- Spouštět z cwd `be-validator-agent/trigger`, s jeho `.venv`; do venv instalovat i intake test dependencies (FastAPI/httpx/python-multipart) a potřebné pipeline dependencies přes existující requirements. Přípravu prostředí dokončit před RED.

```python
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from document_processing.audit.audit_listener import FileReceivedAudit
from document_processing.audit.audit_storage import AuditStore
from pipeline import Options
from pipeline.aws import Aws
from pipeline.config import Settings
from trigger import common, worker_handler
from conftest import add_document, drain, sqs_event, text_pdf

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "be-intake/tests"))
from test_monitor_file_received import intake  # noqa: E402,F401


def test_claim_listener_failure_does_not_change_committed_result(ctx):
    add_document(ctx, "doc-test", case_id="case-test")
    queued = common.enqueue_document(ctx, "case-test", "doc-test", request_key="fixture-claim")

    class BrokenListener:
        def attempt_started(self, **values):
            raise RuntimeError("synthetic audit unavailable")

    ctx.audit = BrokenListener()
    result = common.claim_document(ctx, "case-test", "doc-test", queued.run_id, queued.generation)
    assert result == "claimed"  # RED: injected listener currently escapes after claim commit
    assert result.execution_context.run_id == queued.run_id
    assert result.attempt_no == 1


def test_actual_worker_publishes_terminal_visible_over_http(ctx, monkeypatch, request):
    # Initialize real SDK adapters inside the existing moto scope before intake patches provider factories.
    table = ctx.ddb.create_table(
        TableName="test-worker-audit", BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": n, "AttributeType": "S"} for n in ("pk", "sk")],
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"},
                   {"AttributeName": "sk", "KeyType": "RANGE"}],
    )
    store = AuditStore(table)
    ctx.audit = FileReceivedAudit(store)
    add_document(ctx, "doc-test", case_id="case-test", pdf=text_pdf([
        "Synthetic public fixture for monitoring integration only with a readable text layer.",
        "No private document or paid inference is required for this local test.",
    ]))
    settings = Settings(skip=frozenset({"classify", "embed", "signatures", "copy"}), redact=False)
    monkeypatch.setattr(worker_handler, "_ctx", ctx)
    monkeypatch.setattr(worker_handler, "_options", Options(
        settings=settings, aws=Aws(settings), no_vision=True, reuse=False, defer_copy_check=True))
    queued = common.enqueue_document(ctx, "case-test", "doc-test", request_key="fixture-http")
    delivery = drain(ctx)[0]
    assert worker_handler.handler(sqs_event(delivery["Body"])) == {"batchItemFailures": []}

    main, _, docs, _, _, _ = request.getfixturevalue("intake")
    from processing_monitor_authorization import AuthorizationSecretSource

    token = "synthetic-worker-http-only"
    policy = {
        "version": 1,
        "credentials": [{"sha256": hashlib.sha256(token.encode()).hexdigest(), "principal_id": "fixture"}],
        "principals": [{"id": "fixture", "type": "SERVICE", "enabled": True, "case_ids": ["case-test"]}],
        "retained_documents": [],
    }
    secret_arn = "arn:aws:secretsmanager:eu-central-1:000000000000:secret:local-worker-http"
    secrets = MagicMock()
    secrets.get_secret_value.return_value = {"SecretString": json.dumps(policy)}
    main.app.state.processing_monitor_authorization_source = AuthorizationSecretSource(secret_arn, secrets)
    docs.get_item.side_effect = lambda **kw: ctx.documents.get_item(**kw)
    main.app.state.processing_monitor_audit_store = store
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/cases/case-test/processing/documents/doc-test/events?limit=100",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    secrets.get_secret_value.assert_called_once_with(SecretId=secret_arn, VersionStage="AWSCURRENT")
    assert response.headers["cache-control"] == "private, no-store"
    observations = response.json()["items"]
    terminal = [event for event in observations if event["type"] == "RunFinished"]
    assert len(terminal) == 1  # RED: real pipeline/worker currently emit no run terminal
    assert terminal[0]["run_id"] == queued.run_id
    assert terminal[0]["attempt_no"] == 1
    assert terminal[0]["run_status"] == "completed"
```

```bash
# cwd: /Users/michal/Projects/wonderfulkb/be-validator-agent/trigger
TASK_ID=task-b0db5177-2f43-4036-b080-af1ca7d143d5 PYTHONPATH=..:../../be-document-processing/src python3 "$HOME/.config/opencode/skills/tdd/scripts/proof-capture.py" red --project-root /Users/michal/Projects/wonderfulkb -- .venv/bin/python -m pytest tests/test_processing_monitor_worker_http_integration.py -q
# Teprve po accepted_red provést produkční změny; GREEN použije totožné child argv.
TASK_ID=task-b0db5177-2f43-4036-b080-af1ca7d143d5 PYTHONPATH=..:../../be-document-processing/src python3 "$HOME/.config/opencode/skills/tdd/scripts/proof-capture.py" green --project-root /Users/michal/Projects/wonderfulkb -- .venv/bin/python -m pytest tests/test_processing_monitor_worker_http_integration.py -q
```

| Test | RED | GREEN |
|---|---|---|
| `test_claim_listener_failure_does_not_change_committed_result` | RuntimeError z listeneru po skutečném úspěšném claimu | Stejný claimed result/context/ordinal, business write beze změny |
| `test_actual_worker_publishes_terminal_visible_over_http` | HTTP neobsahuje žádný RunFinished z tested workeru | Jediný skutečně doložený terminal se stejnou run/attempt identity |

## Testing
- Rozšířit focused file o success/failure/retry fragments pro každou skutečně supported větev; absent stage producer uvést explicitně, nenapsat fake business funkci pro zelený test.
- Porovnat NoOp/healthy/sink-failing/throwing-listener snapshots pro enqueue, claim, source, pages/cache, extraction, signatures, publication a worker return/error: stejné business writes/order/results/exceptions, claim/context identity a měřená stage durace podle kontrolovaného monotonic clock. Přidat factory/validation/serialization chyby; audit nesmí vytvářet business retry.
- Pro runtime retry použít skutečnou owner identity opakovaného claimu ve stejném runu; fake queue transport může redeliverovat původní zprávu, receive count nikdy neurčuje ordinal. DLQ/max-attempt ověřit jen s owner-attested generation a bez nového claimu; chybějící proof není inferred terminal.
- Ověřit source rejection, invalid PDF/download failure, page success/failure, validated cache hit bez provider call, extraction exception, signature disabled/returned failure, publication failure po každém povinném write a reuse branch. Business `partial` výsledek není totéž co částečně dokončený publication commit.
- Lost/late/duplicate/terminal-only observations vytvářet drop/delay/duplicate na transportu skutečných producer emissions, ne seedováním DTO. Dokázat stable event id/idempotent put, partial/unknown reducer, žádný synthetic latest/complete a žádný whole-history scan.
- HTTP matice: trusted case grant 200, shared-key-only/forged/revoked/foreign principal 403 či stávající operation-specific mask 404, neexistující/cizí document 404, authorization/membership/audit read failure 503, vždy `private, no-store`. Single bounded Query limit 1–100, empty continuation a cross-run/attempt/operation cursor rejection; žádný scan-until-filled. Kontrolovat DTO proti jedinému YAML, nepřidávat druhý kontrakt.
- Po GREEN spustit z trigger cwd `PYTHONPATH=..:../../be-document-processing/src .venv/bin/python -m pytest tests ../pipeline/tests -q`; z root pomocí příslušných project venv spustit celé `be-document-processing/tests` a `be-intake/tests` s audit src na PYTHONPATH. Neignorovat collection failures, nepřidávat skip/ignore a nezměkčit auth. Případné pre-existing chyby doložit se skutečným command/output.
- Z root spustit přesně registrovaný gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; nesubstituovat jej focused Python testy. Po každém relevantním fixu zopakovat odpovídající gate.
- V runtime evidence vést tabulku níže pro každou proposal section/capability; každá buňka musí obsahovat skutečný command/API run ID, artifact digest a outcome, nebo konkrétní blocker. Reader-only synthetic rows prokazují jen GET, nikoli producer.

| Capability | SOURCE | HERMETIC | INSTALLED | DEPLOYED | LIVE |
|---|---|---|---|---|---|
| Enqueue/claim, source/page/cache/extraction/signature/publication, retry/terminal, HTTP/auth (samostatné řádky při realizaci) | Caller/ref/diff | RED/GREEN + real path assertions | Wheel/ZIP/image import | Resolved image/config/operation | Correlated upload→worker→GET či přesný unsupported/blocker |

## Files
| Cesta | Plánovaná úzká změna |
|---|---|
| `be-validator-agent/trigger/common.py`, `worker_handler.py`, `dlq_handler.py` | Fail-open caller boundary, skutečný runtime context a doložené terminály; bez změny claim/retry/lease pravidel |
| `be-validator-agent/trigger/processing_execution_context.py`, `processing_execution_claims.py` | Reuse inspected owner interface; integrační task nepřidává allocator ani business změny |
| `be-validator-agent/pipeline/run.py` a existující stage-owner callers | Jen nedodané hooks/context injection na skutečných hranicích |
| `be-document-processing/src/document_processing/audit/audit_listener.py` a případný doménově pojmenovaný audit modul | Rozšířit jedinou existující listener/storage hranici; nevytvářet paralelní framework ani `state.py/service.py/utils.py` |
| `be-validator-agent/trigger/tests/test_processing_monitor_worker_http_integration.py` | Nový focused genuine full-path a parity harness |
| `be-validator-agent/trigger/tests`, `pipeline/tests`, `be-document-processing/tests`, `be-intake/tests` | Doplnit relevantní regresní/contract/import testy, reuse existujících mapper/auth fixtures |
| `be-validator-agent/trigger/build.sh`, `Dockerfile`, `requirements-*.txt`; `be-intake/app/Dockerfile`, requirements a existující native templates | Jen chybějící packaging/import/dependency a nutný scoped owner config diff |
| `be-intake/app/processing_monitor*_routes.py`, `processing_monitor_authorization.py`; `be-document-processing/contracts/openapi-processing-monitor.yaml` | Pouze nalezené vlastní integrační/DTO chyby; zachovat existující operations a bezpečnostní seam |
| `plans/monitoring/runtime-producer-context-contract.md`, `worker-instrumentation-contract.md` | Current symbol/capability matrix s verzí; zachovat historickou evidence |
| `plans/monitoring/worker-http-deployment-smoke.md` (nový), `plans/handoffs/aws-runtime-readiness-20261020.md` | Přesné safe operators, manifest/recovery/config handoff, bounded budget a skutečné runtime výsledky |
| `plans/checkpoints/task-b0db5177-2f43-4036-b080-af1ca7d143d5.*` | TDD helper proof a sanitizovaná source/install/deploy/live evidence; žádné ruční přepisování proof/historie |
