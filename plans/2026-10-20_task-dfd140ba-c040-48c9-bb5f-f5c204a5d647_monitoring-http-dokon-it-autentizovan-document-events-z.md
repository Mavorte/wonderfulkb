# Plan 2026-10-20: Monitoring HTTP — authenticated document events

## Progress
- [x] Canonical plan path obtained.
- [x] Inspect authorization, audit reader, contract and deployment ownership.
- [x] Synthesize gated TDD, installation, deployment and verification steps.

## Analysis
- `be-intake/app/main.py:121-156` authenticates shared `x-api-key` and checks case existence only; neither binds caller identity to case. Prior host review and blocker confirm no trusted authorization owner/interface yet. First implementation decision: identify the legitimate service-side identity→case decision interface/owner and approved synthetic case/document with authenticated caller from actual contracts; if unavailable, record exact blocker in `plans/monitoring/` and stop before exposing/deploying route.
- `be-intake/tests/test_processing_monitor_routes.py` is a one-test sketch; `be-intake/app/processing_monitor_routes.py` is absent. `be-document-processing/src/document_processing/audit/audit_queries.py:63` already implements bounded document-partition Query and scope-bound continuation; reuse it.
- `be-intake/app/Dockerfile` builds and installs the audit wheel but copies only `main.py` and `content_hashes.py`; include the new route module in the existing image. `be-intake/README.md` specifies root-context Docker build.
- `plans/monitoring/mvp-reference-20261019.md` specifies current App Runner host as operational context only, not a configured default; `plans/checkpoints/acceptance-host-review-0818-read-reducer.md` and historical blocker explicitly show no deployment/live proof.
- `be-document-processing/contracts/openapi-processing-monitor.yaml:28-39,149-159` specifies this operation and requires `coverage: partial` in addition to `items`, `next_token`, `observed_at`; preserve the single YAML, validate exact DTO and document any inconsistency with the older three-key sketch. `audit_queries.py` orders by `EVENT#event_id`, not `(occurred_at,event_id)`; assess contract/order conflict without inventing a whole-history sort or changing the existing shared reader silently.
- `be-intake/tests/test_monitor_file_received.py:15` owns the `intake` fixture; import it explicitly into route tests (there is no intake tests conftest). `AuditStore.read_document` in `audit_storage.py:65` preserves disabled/error states and delegates to `audit_queries.read_document`; do not add a second reader. Related learnings: `learnings/architecture/2026-10-20_monitoring-read-api-plan-scope.md`, `learnings/security-issues/monitor-steps-red-does-not-authorize-case-read.md`, `learnings/test-failures/processing-monitor-route-test-foundation.md`.

## Approach
- First identify the actual owner, trusted caller identity and service-side identity→case entitlement decision interface, failure/denial policy and an approved authenticated synthetic case/document fixture. Check current code/operational contracts and owner evidence; shared key, `require_case`, browser headers and permissive test doubles cannot satisfy this gate. If absent, write exact missing interface/owner/fixture and SOURCE/INSTALLED/DEPLOYED/LIVE_VERIFIED blocker to a new task-specific `plans/monitoring/` evidence file; do not register/expose/deploy the route or claim completion.
- Once verified, reuse that seam in one intake facade for authorization, document membership via `docs.get_item(Key={"case_id": case_id, "document_id": document_id}, ConsistentRead=True)`, `AuditStore.read_document`, and uniform `private, no-store` for success and every route/middleware error. Preserve current auth; masked missing/foreign scope 404 (or documented consistent 403); required store failure 503; safe metadata DTO only. Validate limit 1–100, cross-document token 400, one bounded Query, partial/unknown semantics. No generic auth framework or duplicate reader.
- Inspect existing App Runner/ECR owner, supported deploy procedure, revision, environment and credential provenance before building. Retain verified recovery image/config; compare target revision before mutation; build/install wheel and module into existing image, guard in-place rollout, wait bounded health and verify digest/revision. If operator permissions deny a supported step, hand Jackie exact target, digest, config diff, recovery and remaining command in this task; perform HTTP verification after operator deployment.

## TDD
- Implementace TDD cyklu dle skill:tdd; check venv has FastAPI, pytest, python-multipart and package imports before capture, use supported skill interface and `plans/checkpoints/task-dfd140ba-c040-48c9-bb5f-f5c204a5d647.red-green-proof.md` only; never relabel historical failures. First make a genuine behavior RED after authorization/fixture gate; same argv for RED/GREEN. Capability denial is a blocker.
- Test file `be-intake/tests/test_processing_monitor_routes.py`; replace sketch with this executable first assertion and extend with approved authorized fixture tests after the seam is identified:

```python
from fastapi.testclient import TestClient
from test_monitor_file_received import intake  # noqa: F401  # existing pytest fixture


def test_document_events_missing_key_is_not_cacheable(intake):
    main, _, _, _, _, _ = intake
    with TestClient(main.app) as client:
        response = client.get("/v1/cases/case-test/processing/documents/doc-test/events")
    assert response.status_code == 401
    assert response.headers.get("cache-control") == "private, no-store"  # RED: guard omits header
```

- Focused argv (identical RED/GREEN): `be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_routes.py`; RED = authenticated monitoring-path error lacks required no-store, GREEN = 401 plus header. Before GREEN, add tests with real seam-shaped authorized/denied identities and actual case-document membership; expect FileReceived JSON + `coverage=partial`, two pages and foreign token 400, unauthorized 403/404, missing document 404, store exception 503, no-store for every status. Avoid 200 assertion based only on shared key. Direct synthetic probes: `PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python ...`; never system interpreter. Check input-invalidity expectations against Python TypeError versus ValueError semantics.

## Implementation
1. Inventory current auth owner/interface and approved fixture; record evidence and block safely if unresolved before any route/source exposure.
2. With seam established, write route tests first, capture genuine RED; add minimal `processing_monitor_routes.py` facade and register in `main.py` only after authorized scope check, reuse installed `AuditStore`; wire no-store on all relevant errors including guard/validation, preserve other routes. Keep any domain-qualified event route extension subordinate to this facade.
3. Compare live DTO to the read-only OpenAPI operation; document exact discrepancies (`coverage`, ordering) in task evidence and resolve within owned source only where consistent with existing audit semantics. Do not modify the YAML or add run/attempt/business endpoints.
4. Complete GREEN and regression gates; inspect actual App Runner target/source provenance, package/build installation and recovery/config before guarded deploy; verify live changed route and refine/redeploy boundedly if implementation/package/router defect appears. Use skill:wful for Wonderful platform operations if needed; preserve project-local deployment ownership and supported procedures.
5. Save task-specific redacted `plans/monitoring/` evidence: fixture IDs, bounded request/write counts, source/image digest, target revision/time, config diff/recovery, HTTP status/schema/scope assertions and explicit SOURCE/INSTALLED/DEPLOYED/LIVE_VERIFIED states; record real blockers, no content/secrets or fabricated live proof.

## Testing
- Focused intake test command above; run full audit matrix including `be-document-processing/tests/test_monitor_audit_storage.py`, `test_monitor_openapi_observation_contract.py` and related `test_monitor_*.py`; run `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests` without ignores. Validate the sole YAML read-only; run `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` as registered, keep unrelated failures separate without weakening assertions.
- Check wheel import and router in actual built image. On the actual authorized fixture: bounded authenticated GET and continuation (if present), DTO/type/ID/filter/observed_at/partial/no-store, unauthorized and foreign-scope negative HTTP; test read-error→503 hermetically. A known prior synthetic event may prove content without a new write; otherwise label live content branch unverified. Record source/image digest and deployed revision after rollout, not only `/healthz`.

## Files
- `be-intake/tests/test_processing_monitor_routes.py` — focused TDD and case/auth/error/paging evidence; reuse explicit `intake` fixture from `test_monitor_file_received.py`.
- `be-intake/app/processing_monitor_routes.py`, `be-intake/app/main.py`, `be-intake/app/Dockerfile` — authorized bounded adapter, safe registration/error headers, image copy; only after authorization gate.
- `be-document-processing/src/document_processing/audit/audit_queries.py` — inspect existing reader; modify only if owned contract discrepancy requires a scoped correction with tests, never a competing reader.
- `be-document-processing/contracts/openapi-processing-monitor.yaml` — read/validate only; `plans/checkpoints/task-dfd140ba-c040-48c9-bb5f-f5c204a5d647.red-green-proof.md` and a new task-specific `plans/monitoring/` evidence file — owned proof and deployment/blocker record.
