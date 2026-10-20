# Plan 2026-10-20: Monitoring MVP lifecycle read API

## Analysis
- Intake lifecycle router module is not present; the existing integration point is `be-intake/app/main.py` and existing monitor routes/tests. Keep the new domain router in `processing_monitor_lifecycle_routes.py` and wire it minimally.
- `audit_queries.read_document` performs one bounded Query (limit 1–100), returning typed events and a scope-bound continuation token. The pure `audit_lifecycle_observations.reduce_observations` already emits partial summaries and preserves ambiguity; adapt mappings at the HTTP boundary without changing the shared reader.
- Reuse `audit_page_observations.py`, shared auth/scope/no-store/error behavior, and the single OpenAPI file. Do not infer per-case permission from API-key authentication or case existence.
- Reference the exact reducer contract in `plans/tasks/2026-10-20_monitor-mvp-23-lifecycle-window-reducer.md`, the monitoring proposal, and learnings on bounded summaries, trusted authorization, and deployed-read evidence. Deployment must target the existing `wonderfulkb-ingest` App Runner service in eu-central-1 and remain guarded; confirm actual owner, supported deployment path, fixture, and recovery artifact before changes.

## Approach
- Add runs collection, run detail, and audit snapshot operations to the existing intake application. Each request evaluates exactly one document window; detail filters that window and returns unknown/partial with continuation when no matching observations are present.
- Keep summaries strictly observation-based: allowlisted fields and evidence IDs only, publication separate from run terminal state, no inferred latest/total/percent or completed history. Bind cursors to operation and relevant case/document/run scope; reject cross-operation tokens.
- Preserve trusted identity/auth seam, private no-store on success and errors, and map required source-read failures to 503. If authorization or source capability is absent, document the precise blocker rather than adding a fallback.
- Update only the owned operations/DTOs in the existing OpenAPI YAML. Preserve unrelated operations and prior work.
- Package the audit module into the existing intake artifact, run local and registered gates, then guardedly install/deploy and verify image/revision/digest plus bounded authenticated direct HTTP behavior using an authorized synthetic fixture. Record IDs, request counts, assertions, and any live-content limitation in `plans/monitoring/`; rollback only through verified recovery and revision guards.

## Implementation
1. Inspect actual intake composition, existing shared reader/auth seams, package/build/deploy process, live target owner/configuration, and synthetic fixture. Establish recovery artifact and deployment revision/concurrency guards before rollout.
2. Use focused FastAPI tests first under TDD. Verify route reuse, operation-bound cursor adapter, one Query per operation, partial/unknown results, auth/scope/error and no-store behavior.
3. Implement/wire the dedicated lifecycle router, reuse the pure reducer and bounded reader, map only supported observations, and package the audit dependency in intake.
4. Narrowly align the owned OpenAPI operations/DTO semantics; validate the spec and preserve all other operations.
5. Run focused tests, package/build checks, and registered `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` gate.
6. Guardedly deploy to the existing AWS test target; confirm installed package, deployed image/revision/digest, and rollout health. Perform bounded authenticated route-level HTTP checks for schema, scope, continuation, cache headers, and negative auth/scope. Do not replay ambiguous writes or claim live event coverage absent actual producer evidence.
7. Fix implementation/package/router issues in scope and repeat local checks and guarded deployment/smoke as needed. Save task-specific runtime evidence; report SOURCE / INSTALLED / DEPLOYED / LIVE-FUNCTION-VERIFIED distinctly, with exact operator blocker if permissions/interfaces prevent completion.

## Testing
- Focused FastAPI/fake-reader coverage: runs/detail/audit agreement for the same window; retry with two attempts; terminal-only run; partial publication separate from final status; conflicting/late fragments remain unknown or ambiguous; empty continuation; query count one; token operation/scope mismatch; availability states; required read failure 503; auth/scope and private no-store including errors.
- Preserve existing event, attempt, steps, pages GET behavior and run full registered test/build gate.
- Validate OpenAPI semantics and package inclusion. Hermetic HTTP checks do not count as live evidence; directly exercise deployed changed routes using an authorized synthetic case/document and record safe IDs/status/schema assertions.
- Live verification is bounded: confirm deployed artifact/revision/digest and target, then verify new observations only when supported by existing fixture/event evidence; never represent manual audit writes as producer-to-HTTP proof.

## TDD
**Workflow:** Use skill:tdd; create the focused test before implementation, capture a genuine implementation-specific RED, implement to GREEN, and retain proof under `plans/checkpoints/task-57f572d9-1dda-45cd-b37c-d5fa9d183d59.red-green-proof.md`.

**Test file:** `be-intake/tests/test_processing_monitor_lifecycle_views.py`  
**Framework:** pytest + FastAPI `TestClient`, consistent with existing intake monitor tests.  
**Run command:** `be-intake/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_lifecycle_views.py`  
**Edit hint:** New focused test module; use existing intake fixture and fake/spy audit reader.

```python
from fastapi.testclient import TestClient


def test_lifecycle_routes_return_partial_observations_and_preserve_publication(intake):
    main, _, _, _, _, _ = intake
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/cases/case-test/processing/documents/doc-test/runs",
            headers={"x-api-key": "test-key"},
        )
    assert response.status_code == 200  # RED: lifecycle route not yet registered
    body = response.json()
    assert body["coverage"] == "partial"
    assert body["runs"][0]["status"] != body["published_results"][0]["outcome"]
    assert response.headers["cache-control"] == "private, no-store"
```

| Test | RED | GREEN |
|---|---|---|
| Runs lifecycle observations and publication separation | Missing lifecycle route/DTO assertion fails | Returns partial observations, separate publication outcome, and private no-store |
| Run detail and audit use same bounded window | Missing route or reader called more than once | Matching summaries/continuation and exactly one evaluated Query window |
| Invalid cursor and protected scope | Missing operation-bound rejection/auth seam fails | Mismatched token rejected; unauthorized scope denied without cacheability |
| Required reader error | Missing source error mapping fails | HTTP 503, never empty-success |

## Files
| Path | Change |
|---|---|
| `be-intake/app/processing_monitor_lifecycle_routes.py` | New lifecycle routes/DTO mapping and operation-bound cursor adapter |
| `be-intake/app/processing_monitor_routes.py`, `be-intake/app/main.py` | Minimal router integration only, as actual composition requires |
| `be-intake/tests/test_processing_monitor_lifecycle_views.py` | Focused TDD coverage |
| `be-document-processing/contracts/openapi-processing-monitor.yaml` | Narrowly align owned lifecycle operation/DTO semantics only |
| Intake package/build configuration | Ensure existing audit package is installed in the current intake artifact |
| `plans/monitoring/` | Task-specific guarded deployment and live HTTP evidence |

## Progress
- [x] Canonical plan path created.
- [x] Contract, reducer, reader, existing test layout, proposal, and relevant learnings inspected.
- [ ] Implement lifecycle read routes and focused TDD cycle.
- [ ] Align contract, package, and registered checks.
- [ ] Guardedly deploy and verify the changed routes live, or record concrete access/interface blocker and operator handoff.
