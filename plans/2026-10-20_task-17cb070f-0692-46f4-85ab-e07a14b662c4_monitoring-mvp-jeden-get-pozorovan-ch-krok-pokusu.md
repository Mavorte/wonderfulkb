# Plan 2026-10-20: Monitoring MVP — GET pozorovaných kroků

Přidat operation-bound, bounded read endpoint a jeho úzký observation DTO; dokončení zahrnuje guarded test deployment a skutečné ověření této route.

## Analysis
- `audit_queries.read_document` provádí jediný bounded document Query; jeho continuation je document-events scoped, proto route adapter musí odmítnout nevhodný token a bezpečně svázat steps cursor s case/document/run/attempt.
- `audit_page_observations.to_page_observations` je hotový pure mapper pro window-scoped page observations. Reuse jej pouze pro page eventy; nepřekrývat či nekopírovat jeho chování.
- V intake je `tests/test_processing_monitor_routes.py`; step router zatím není nalezen. Task stanoví vlastnictví v `processing_monitor_step_routes.py`, s minimálním zapojením facade.
- Stávající OpenAPI YAML a jeho focused contract tests už obsahují širší předchozí návrh; upravit pouze steps operation/DTO a zachovat ostatní hotový kontrakt.
- Relevantní pravidla: shared API key + `require_case()` samy nedokládají per-case oprávnění; chybějící trusted auth seam je blocker. Bounded reads a hermetické testy nedokládají živé eventy ani deployed HTTP chování.

## Approach
- Založit samostatný step router a připojit jej minimální změnou do existujícího intake FastAPI routeru. Reuse existující auth, case/document scope, no-store, error handling a audit reader seams.
- Validovat kladný `attempt_no`, limit 1–100 a cursor před query. Pro každý request provést právě jeden bounded document read; následně filtrovat run/attempt a explicitní allowlist pouze v tomto okně.
- Vlastní cursor ověřuje case/document/run/operation=`steps`/attempt a nese poslední vyhodnocenou pozici, i když okno nevydalo items. Nečíst dále k naplnění stránky ani nepárovat události napříč okny.
- Emitovat jen doložená observation pole; `coverage=partial`, `observed_at`, `next_token`. Neodvozovat step ID/status/trvání ani run existence. PageCompleted/PageFailed jsou pouze terminal outcome stejné stránky; žádný duplicitní syntetický StepFinished/StepFailed.
- Pokud trusted scope authorization nebo read-source seam chybí, zastavit vystavení route a zapsat přesný interface/blocker; žádný fallback.

## Implementation
1. Než se dotkne runtime kódu, založit TDD RED testy v `be-intake/tests/test_processing_monitor_step_routes.py` a zaznamenat proof dle `skill:tdd`.
2. Implementovat route adapter, parameters, one-query filtering, cursor validation/encoding, response allowlist a status/cache headers; připojit router minimálním diffem.
3. Úzce aktualizovat steps path/DTO v jediném OpenAPI YAML; zachovat unrelated operations/schemas.
4. Přidat focused testy pro start+finish/failure, oddělené attempts/runs, missing-start fragment, empty window + continuation, malformed/foreign tokens, jeden Query, scope/auth, no-store/read503. Ověřit zachování events/attempts/FileReceived kontraktů.
5. Spustit relevantní Python focused tests, OpenAPI contract tests a registrovanou gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
6. Před deploymentem zjistit skutečný AWS test target/owner, supported build path, package instalaci v intake artifactu, source→artifact provenance, aktuální revision/config a recovery artifact. Guardovat deployment revision/concurrency a zachovat konfiguraci; neprovádět broad permissions ani jiný deployment mechanism.
7. Do `plans/monitoring/` evidovat source/artifact digest, target revision, recovery/config diff, instalaci/deploy, čas a bounded synthetic fixture/write inventory. Guardovaně nasadit existující `wonderfulkb-ingest` App Runner eu-central-1; při rollout problému rollbacknout jen jos revision guard dovolí.
8. Po deploy ověřit image/revision/digest a přímo autentizované HTTP na známém autorizovaném syntetickém case/document: schema/filters/continuation/no-store, auth/scope behavior; hermeticky dokázat read failure→503. Neopakovat nejednoznačné writes ani nevyvolávat inference/queue side effects. Rozlišit deployed route od neověřené live content větve.
9. Opravit pouze nalezené chyby v tomto scope, znovu lokálně ověřit a guarded redeploy + bounded HTTP smoke. Pokud agent nemá supported deployment capability, připravit Jackieho přesný operator krok s artifact/target/recovery evidence; žádné obcházení. Uzavřít stavy SOURCE / INSTALLED / DEPLOYED / LIVE-FUNCTION-VERIFIED pravdivě.

## Testing
- Focused fake/FastAPI cases: observations allowlist, run/attempt filter, terminal-only, prázdné okno s tokenem, jeden Query, token cross-attempt/run/operation rejection, malformed attempt/token, authorization/scope, private no-store, source failure→503.
- OpenAPI checks: pouze jeden YAML; steps parametry, required fields, `coverage=partial`, absence page_number pro source_validation, explicit extendable event allowlist, partial/empty continuation semantics.
- Runtime evidence: deployed target revision/image digest + actual route HTTP assertions na bounded authorized synthetic fixture; hermetické 503 testy nahrazují cloud fault injection. Registry gate zůstává povinná.

## TDD
**Test file:** `be-intake/tests/test_processing_monitor_step_routes.py`  
**Framework:** pytest + FastAPI TestClient, podle existující monitor route tests.  
**Run command:** `pytest -q be-intake/tests/test_processing_monitor_step_routes.py`  
**Edit hint:** NEW FILE; použij existující `intake` fixture pattern po ověření její skutečné lokalizace.

```python
from fastapi.testclient import TestClient


def test_steps_requires_positive_attempt_and_returns_partial_observation_window(intake):
    main, *_ = intake
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/cases/case-test/processing/documents/doc-test/runs/run-test/steps?attempt_no=0",
            headers={"x-api-key": "test-key"},
        )
    assert response.status_code == 400  # RED: steps route/attempt validation not implemented
```

| Test | RED | GREEN |
|---|---|---|
| invalid attempt rejected | route missing/does not validate attempt | consistent 4xx and private no-store |
| bounded observations/cursor behavior (add after initial RED) | no steps response | one query, scoped filtered observations, correct continuation |

Implementace TDD cyklu dle `skill:tdd`; retain truthful RED/GREEN proof.

## Files
- `be-intake/app/processing_monitor_step_routes.py` — new step route, adapter, operation-bound cursor and allowlist.
- `be-intake/app/processing_monitor_routes.py` and app entrypoint — minimum router registration only.
- `be-intake/tests/test_processing_monitor_step_routes.py` — focused FastAPI tests.
- `be-document-processing/contracts/openapi-processing-monitor.yaml` — narrow steps operation/DTO clarification only.
- `be-document-processing/src/document_processing/audit/audit_page_observations.py` — reuse only if page observations need mapping; do not duplicate it.
- `plans/monitoring/` — task-specific deployment/live verification evidence, no secrets or document content.

## Progress
- [x] Canonical path and task brief/context read.
- [x] Read monitor/audit patterns and relevant authorization/observation learnings.
- [ ] Implement and verify the planned change; deployment and live evidence are part of completion.
