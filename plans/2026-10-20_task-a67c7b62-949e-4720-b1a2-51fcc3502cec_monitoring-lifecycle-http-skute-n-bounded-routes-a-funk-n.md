# Plan 2026-10-20: Monitoring lifecycle HTTP

## Analysis
- Current `be-intake/app/main.py` mounts only uploads/document listing; `guard` checks a global key and `require_case` checks existence on upload, with no trusted caller→case/document-read authorization. Monitor event/steps/pages test files also contain undelivered 200 sketches; never convert shared key or case existence into case entitlement. Inspect actual deployed composition/owner before rollout; missing trusted seam is a concrete security blocker.
- `be-document-processing/src/document_processing/audit/audit_queries.py:read_document` performs one consistent bounded document Query (1–100) and returns a document-bound last-evaluated cursor. Add operation/path-scope cursor adapter only in the lifecycle route; retain the reader unchanged. `audit_lifecycle_observations.reduce_observations` is the canonical partial reducer (runs.state, attempts.terminal_state, publications.evidence). `RunFinished.run_status` is the canonical terminal field; do not use sketch-only `status`/`outcome` fields. Currently the reader dispatch does not include `ResultPublished`: establish actual supported publication producer/decoder capability before claiming live publication observations; if absent, record exact interface blocker, never turn read errors into empty results.
- `be-intake/tests/test_processing_monitor_lifecycle_views.py` imports the local `intake` fixture, but is only a legacy sketch. `be-intake/app/Dockerfile` installs the audit wheel but copies only main/content_hashes; add the lifecycle module to its existing runtime copy when ready. `be-intake/template.yaml` describes IAM but not the App Runner service/deploy workflow; recover actual image/config/owner and guard the running revision before deployment.
- `be-document-processing/contracts/openapi-processing-monitor.yaml` already defines the three operations but lifecycle DTO enums differ from reducer facts. Narrowly reconcile owned operation/DTO and `observed_at`/partial/availability semantics without rewriting unrelated paths. `plans/tasks/2026-10-20_monitor-mvp-23-lifecycle-window-reducer.md` governs reducer scope; `learnings/security-issues/monitor-steps-red-does-not-authorize-case-read.md`, `learnings/architecture/2026-10-20_bounded-monitoring-read-plan-semantics.md` and `learnings/test-failures/intake-monitoring-red-multipart-explicit-fixture.md` govern auth/window/TDD setup. No PlantUML diagram was found.

## Approach
- Confirm or obtain the existing trusted request identity→case entitlement, document-in-case lookup, shared bounded-reader/table and private,no-store/error policy interface; reuse it rather than constructing a second auth/reader framework. If truly absent, document exact owner/interface and hold route exposure/rollout until integrated; default denial must not be reported as success.
- For each authorized runs/detail/audit call, read precisely one evaluated document window and pass `event.to_item()` allowlisted observations to the reducer. Filter detail in-memory by run_id; absent run observations on a known document yield explicit unknown partial data with continuation, not 404 inferred from the window. Carry evidence IDs/sequence, separate publication from run terminals, and never infer latest/totals/complete history or synthetic attempts.
- Wrap reader token with versioned operation + case/document/(run) scope, reject mismatches and invalid encoding as 400, preserve raw last-evaluated continuation even for empty filtered windows. Preserve explicit availability only with capability/config evidence; required read failure→503 and private,no-store on all responses, including 4xx/503.
- Verify the existing App Runner `wonderfulkb-ingest` target in eu-central-1, installation/build provenance, current revision/config, deploy interface, authorized synthetic fixture and verified recovery artifact before any guarded in-place deployment. Keep all synthetic writes bounded in a task-wide ledger; only directly observed producer→HTTP facts count as live-content evidence.

## Implementation
1. Inspect runtime composition and owner interfaces for trusted caller/case authorization, document membership, read table, and existing 403/404 policy; record missing seams as blockers with concrete owner integration steps. Identify existing synthetic fixture, allowed POST budget, actual target/config, current revision, recovery image/digest, and supported deployment command without retrieving secrets into evidence.
2. Load `skill:tdd`; use the current task ID for new RED→GREEN proof, retain old RED/setup artifacts untouched. Fix local dependency/import setup with `be-document-processing/.venv/bin/python` and `be-intake` package cwd; use the same exact focused argv for RED/GREEN. Establish trusted fixture/context before asserting authorized 200; never fake it via shared key.
3. Implement `be-intake/app/processing_monitor_lifecycle_routes.py` with operation cursor adapter, DTO allowlist and canonical reducer. Minimal `main.py` router wiring only after secure seam exists; update Dockerfile copy for the module. Do not rewrite `audit_queries.py`, create another reducer/reader, or synthesize producer events. If real publication is not decodable by the existing reader, identify narrow ownership/interface fix and test it before claiming coverage.
4. Align only owned operations/DTO in the single OpenAPI YAML. Run focused and existing event/attempt/steps/pages regressions, package/image import, API validation, and registered `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; record actual results rather than promoting old RED evidence.
5. With trusted auth and supported deploy interface confirmed, snapshot verified recovery image/config; build/push/install via existing workflow, check image digest and revision/concurrency guard before update, wait boundedly for rollout/health, read back deployed digest/revision/config, preserve other env/IAM. On failure roll back only if target revision is still ours; never overwrite a foreign revision.
6. Issue bounded direct authenticated HTTP GETs to changed runs/detail/audit and altered DTO on a known authorized synthetic case/document: schema/IDs/filter/partial/continuation, no-store, actual denied scope and missing auth. Verify one actual observed event only if pre-existing fixture/producer evidence supports it; otherwise mark live-content branch unverified. Read-failure→503 stays hermetic (no cloud fault injection). Fix in-scope router/package errors, re-run gates and guarded redeploy/smoke as needed; never replay ambiguous POST.
7. Record task-specific evidence in `plans/monitoring/` (source/artifact SHA256, target/revision/config diff/recovery, installation and rollout timestamps, fixture IDs and request/write counts, safe HTTP status/header/schema assertions, rollback/blocker). Distinguish SOURCE / INSTALLED / DEPLOYED / LIVE-FUNCTION-VERIFIED; if permissions or trusted seam block rollout, give Jackie the exact bounded operator step under standing authorization and retain task open. Finish review/acceptance using applicable manifests and run `save-learning` last.

## Testing
- Focused fake/read-spy FastAPI: retry two attempts, terminal-only run, unknown/ambiguous/conflicting/late fragments, publication independent of terminal, scope/availability, consistency across three routes for equal windows, empty filtered continuation, one Query/request, cursor cross-operation/run rejection and 1/100/invalid limits, 4xx/503 + no-store. Confirm existing event/attempt/steps/pages tests are not treated as delivered HTTP evidence.
- Check installed wheel and standalone image import (no bind mount), OpenAPI schemas/operation IDs, all relevant processing and intake tests plus exact registered backoffice gate. Verify deployed digest/revision and changed HTTP responses directly against known authorized fixture; `/healthz` or local TestClient alone does not satisfy runtime acceptance.

## TDD
- **Test file:** `be-intake/tests/test_processing_monitor_lifecycle_views.py` (replace old sketch; import `intake` from `test_monitor_file_received`, no conftest). **Framework:** pytest + FastAPI TestClient. **Command (identical RED/GREEN argv, from `be-intake` cwd):** `env PYTHONPATH=../be-document-processing/src ../be-document-processing/.venv/bin/python -m pytest -q tests/test_processing_monitor_lifecycle_views.py`. Verify pytest/FastAPI/Moto/multipart imports first; install pinned intake requirements in existing processing venv if needed. Implementace TDD cyklu dle skill:tdd; new proof `plans/checkpoints/task-a67c7b62-949e-4720-b1a2-51fcc3502cec.red-green-proof.md`.

```python
from fastapi.testclient import TestClient
from test_monitor_file_received import intake


def test_lifecycle_route_requires_trusted_case_scope_and_private_denial(intake):
    main, *_ = intake
    path = "/v1/cases/case-test/processing/documents/doc-test/runs"
    assert any(getattr(route, "path", None) == path for route in main.app.routes)  # RED: route absent
    with TestClient(main.app) as client:
        response = client.get(path, headers={"x-api-key": "test-key"})
    assert response.status_code in (403, 404)  # shared key alone cannot grant case read
    assert response.headers["cache-control"] == "private, no-store"
```

| Focused case | Genuine RED before change | GREEN after trusted integration |
|---|---|---|
| Registered guarded runs route (skeleton) | Path assertion fails (route absent), not fixture/setup failure | Registered route denies absent trusted case context with no-store |
| Authorized runs/detail/audit with actual trusted fixture | Routes absent / assertion on partial canonical reducer output fails | Same-window summaries, unknown detail, independent publication, evidence and continuation |
| Cursor/reader/auth failures | No operation-bound rejection, secured reader, or 503 mapping | One Query, 400 mismatched token, 403/404 scope, 503 read failure, private errors |

## Files
| Path | Planned change |
|---|---|
| `be-intake/tests/test_processing_monitor_lifecycle_views.py` | Replace sketch with genuine focused domain HTTP tests |
| `be-intake/app/processing_monitor_lifecycle_routes.py` | New guarded bounded lifecycle router/DTO/cursor adapter |
| `be-intake/app/main.py`, `be-intake/app/Dockerfile` | Minimal integration and package copy |
| `be-document-processing/contracts/openapi-processing-monitor.yaml` | Align only lifecycle operations and DTOs |
| `plans/monitoring/`, `plans/checkpoints/task-a67c7b62-949e-4720-b1a2-51fcc3502cec.red-green-proof.md` | New safe deployment/live and RED/GREEN evidence |

## Progress
- [x] Canonical plan path initialized; source, contract, prior sketch, test fixture, build and security learnings inspected.
- [ ] Implementation task: identify trusted seam and deployment owner, capture genuine RED→GREEN.
- [ ] Implementation task: run gates, install, guardedly deploy, prove new HTTP behavior or record exact blocker.

## Progress
- [x] Canonical plan path initialized.
- [ ] Resolve actual HTTP/auth/deploy ownership and relevant learnings.
- [ ] Specify focused TDD and guarded runtime verification.
