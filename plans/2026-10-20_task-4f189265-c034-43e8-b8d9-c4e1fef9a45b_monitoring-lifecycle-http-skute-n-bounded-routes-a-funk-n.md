# Plan 2026-10-20: Monitoring lifecycle HTTP acceptance repair

## Progress
- [x] Inspect parent plan, denial proof, code, contract and historical deployment evidence.
- [x] Identify existing reader/reducer and the missing authorization and publication-read seams.
- [x] Correct canonical plan header and specify functional TDD and guarded live verification.
- [ ] Implementation agent: prove trusted authorization, functional routes and deployment on test target.

## Analysis
- Existing `be-intake/app/processing_monitor_lifecycle_routes.py` registers three unconditional 403 routes; `main.py` global API key authenticates service only; `require_case` checks existence, not entitlement. Keep denial until trusted caller→case and document membership are established; prior parent proof only establishes denial.
- Reuse `audit_queries.read_document` (one consistent bounded Query, limit 1–100, document-bound continuation) and `audit_lifecycle_observations.reduce_observations` (partial, canonical `run_status`, evidence/attempt/publication). Reader currently does not decode `ResultPublished`; confirm event contract and add narrow decoder support if owned.
- Preserve existing uncommitted/modified workspace files; original plan and evidence are historical, not deployment or functional proof. OpenAPI lifecycle operations already exist in `be-document-processing/contracts/openapi-processing-monitor.yaml`.
- `openapi-processing-monitor.yaml` run/audit DTOs currently advertise `lifecycle`, `terminal`, `publication` and event-ID-only evidence unlike reducer `state`, `terminal_state`, `published_results`, full evidence and availability; align only these three DTOs to actual mapper output. `ResultPublished` exists in YAML but no supported event class/reader dispatch in audit package: publication branch needs producer-owned event shape and reader round-trip before claiming it.
- Parent evidence `plans/monitoring/task-a67c7b62-949e-4720-b1a2-51fcc3502cec-lifecycle-http-evidence.md` records local image only, AWS `NoCredentials`, and 0 live calls. Parent `plans/checkpoints/task-a67c7b62-949e-4720-b1a2-51fcc3502cec.red-green-proof.md` RED/GREEN is route-registration/403 only; preserve it untouched. Learnings `learnings/security-issues/task-a67c7b62-lifecycle-http-authorization-gate.md`, `learnings/architecture/2026-10-20_lifecycle-acceptance-dto-drift-functional-proof.md`, `learnings/architecture/2026-10-20_bounded-monitoring-read-plan-semantics.md` and `learnings/tooling/2026-10-20_planning-retry-canonical-header-validation.md` govern case scope, DTOs, cursor and plan header. Skill discovery: use `tdd` for functional proof, `task-evidence` for parent proof provenance, `save-learning` at task end. No matching PlantUML was identified by parent research.

## Approach
- Confirm owning authorization interface and deployed service identity before enabling reads; bind continuation to route operation and run scope without changing the shared reader contract.
- Reuse canonical reducer over each single finite page and map distinct runs, detail, document-audit partial DTOs without inventing completeness.
- Resolve exact trusted request identity and case entitlement owner plus document-in-case lookup and 403/404 masking from deployed service; inject that authorized scope as a narrow route dependency (tests replace only trusted provider). An arbitrary header, `uploaded_by`, shared API key or merely existing case/document is not entitlement. If no trusted provider exists, record owner/interface blocker; leave current deny behavior in place and do not mark goal complete.
- Use scoped/versioned token wrapping reader `next_token` with exact operation/case/document/run; strict decode and 400 on malformed/mismatched tokens. Keep limit 1–100, one document Query per authorized request, retain last evaluated cursor on empty filtered detail, and use partial coverage/unknown availability unless evidence proves otherwise. Required read/decode failure becomes 503, never empty 200. Keep `private, no-store` for all statuses.

## Implementation
1. Inspect deployed identity provider/document ownership, service owner and audit table connection; define typed authorized scope and policy. Verify existing fixture, target service and deployment workflow before touching cloud; absence is an explicit blocker rather than a synthetic authorization shortcut.
2. First append focused functional tests in `be-intake/tests/test_processing_monitor_lifecycle_views.py` at the confirmed trusted-provider boundary; use `skill:tdd` to capture RED only if it genuinely fails on missing authorized behavior, link the historical parent RED without fabricating a replay, then capture fresh GREEN with identical focused argv. Verify fixture imports before capture.
3. Replace 403-only handlers in `be-intake/app/processing_monitor_lifecycle_routes.py` with authorized dependency, one reader call, strict scoped token adapter and allowlisted reducer-to-JSON mappers. Keep existing router inclusion and Dockerfile copy in `main.py`/`Dockerfile`; change them only for real required wiring/table config and preserve other endpoints.
4. Reconcile actual publication producer contract with `audit_events.py`, `audit_queries.py` and lifecycle reducer: if supported, add narrow `ResultPublished` persistence decoder/dispatch and readback test (including any publication identifier used by reducer); if absent, document exact producer-owned gap and do not claim live publication. Narrowly align lifecycle DTOs in the one OpenAPI YAML to observed fields and partial semantics; remove stale prose asserting the route is unavailable only when it becomes functional.
5. Run focused tests and package/image import. Inspect existing App Runner `wonderfulkb-ingest` in eu-central-1 with authenticated AWS access (use approved login flow if needed): target ARN, owner, image digest/revision, env/IAM and supported deploy procedure. Retain verified recovery digest/config; build/push artifact with source→image provenance, compare current revision immediately before guarded in-place update, wait boundedly for healthy rollout and read back deployed digest/config. On conflict/denial stop; rollback only if revision remains ours. Keep synthetic writes within existing authorized bounded budget, no ambiguous POST replay.
6. Direct authenticated GET runs, detail and audit on known entitled synthetic case/document, verify evidence IDs, independent publication/terminal facts if present, exact-scoped cursor and no-store; check missing/denied scope and unauthenticated responses. Record target/starting/ending revision, digest, verified recovery, fixture IDs, GET/POST counts, assertions and any blockers in `plans/monitoring/task-4f189265-c034-43e8-b8d9-c4e1fef9a45b-lifecycle-http-evidence.md`; label SOURCE/INSTALLED/DEPLOYED/LIVE-FUNCTION-VERIFIED separately. Keep historical evidence unchanged; if actual permission/provider blocks deployment, give Jackie the precise bounded operator continuation without calling it success.

## Testing
- Focused command (from `be-intake`): `env PYTHONPATH=../be-document-processing/src ../be-document-processing/.venv/bin/python -m pytest -q tests/test_processing_monitor_lifecycle_views.py`; fake provider returns an authorized scope, reader spy verifies one Query and no read on denied request. Assert run summary `state`, attempts `terminal_state`, full evidence, terminal-only/unknown/ambiguous/conflict behavior, separate publication, same-window consistency, empty filtered continuation, cursor cross-operation/run rejection and 400/401/403/404/503/no-store.
- Run audit storage/reader/reducer tests and intake regressions; validate owned OpenAPI response schemas; build Docker and import installed modules as image user. Execute canonical registry gate exactly: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`. Preserve existing unrelated sketch failures as failed evidence rather than repainting green.
- Inspect deployed image digest/revision and exercise changed routes over actual HTTP on entitled fixture; test 503 with hermetic injected read failure, not cloud fault injection. `/healthz`, local TestClient and empty 200 alone do not prove end-to-end behavior.

## TDD
- Append to `be-intake/tests/test_processing_monitor_lifecycle_views.py` (pytest/FastAPI TestClient; existing `intake` fixture import). First capture assertion RED below against current unconditional 403 only if implementation still lacks functional 200; do not claim parent route-registration RED proves functional behavior or manufacture a new RED after functionality exists. If trusted provider's confirmed interface differs, adapt fixture at provider boundary before RED while keeping an assertion failure, not an import/setup failure. Implementace TDD cyklu dle skill:tdd; save new proof to `plans/checkpoints/task-4f189265-c034-43e8-b8d9-c4e1fef9a45b.red-green-proof.md` and cite preserved parent proof. Identical RED/GREEN argv from `be-intake`: `env PYTHONPATH=../be-document-processing/src ../be-document-processing/.venv/bin/python -m pytest -q tests/test_processing_monitor_lifecycle_views.py`.

```python
# Append below existing test; replace fake provider with the confirmed trusted seam.
from unittest.mock import patch

def test_authorized_lifecycle_window_uses_bounded_reader(intake, monkeypatch):
    import processing_monitor_lifecycle_routes as lifecycle
    from document_processing.audit.audit_queries import AuditPage
    from document_processing.audit.audit_events import RunQueued

    main, *_ = intake
    # Only a hermetic trusted provider may issue this scope; production must prove entitlement.
    monkeypatch.setattr(main.app.state, "lifecycle_authorize_read",
                        lambda request, case_id, document_id: (case_id, document_id), raising=False)
    event = RunQueued(schema_version=1, case_id="case-test", document_id="doc-test",
                      event_id="evt-1", sequence=1, type="RunQueued",
                      occurred_at="2026-10-20T10:00:00Z", run_id="run-1")
    with patch.object(lifecycle, "read_document", create=True,
                      return_value=AuditPage([event], None)) as reader:
        with TestClient(main.app) as client:
            response = client.get("/v1/cases/case-test/processing/documents/doc-test/runs",
                                  headers={"x-api-key": "test-key"})
    assert response.status_code == 200  # RED: existing route always returns 403
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["coverage"] == "partial"
    assert response.json()["items"][0]["run_id"] == "run-1"
    assert reader.call_count == 1
```

| Focused case | RED before implementation | GREEN after implementation |
|---|---|---|
| Authorized runs skeleton | 403 != 200 | 200 partial; run-1 evidenced; reader called once |
| Authorized detail/audit + continuation | 403 instead of bounded DTO | same-window partial summaries and last evaluated cursor |
| Scope/token/read failure | absent behavior | 400 wrong operation/run token, denial without Query, read error 503; no-store |

## Files
- `be-intake/app/processing_monitor_lifecycle_routes.py`: trusted scope, operation cursors, single reader/reducer and DTOs.
- `be-intake/tests/test_processing_monitor_lifecycle_views.py`: append authorized focused HTTP coverage; retain denial test.
- `be-intake/app/main.py`, `be-intake/app/Dockerfile`: only necessary provider/table wiring or packaging adjustment after verifying ownership.
- `be-document-processing/src/document_processing/audit/audit_events.py`, `audit_queries.py` and relevant audit readback test: only if verified publication producer requires decoder support.
- `be-document-processing/contracts/openapi-processing-monitor.yaml`: narrowly reconcile lifecycle DTOs.
- `plans/checkpoints/task-4f189265-c034-43e8-b8d9-c4e1fef9a45b.red-green-proof.md`, `plans/monitoring/task-4f189265-c034-43e8-b8d9-c4e1fef9a45b-lifecycle-http-evidence.md`: follow-up proof and guarded deployment/live ledger.
