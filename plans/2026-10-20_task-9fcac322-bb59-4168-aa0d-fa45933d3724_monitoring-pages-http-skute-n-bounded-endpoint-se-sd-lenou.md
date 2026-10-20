# Plan 2026-10-20: Monitoring pages HTTP: skutečný bounded endpoint se sdílenou case autorizací a test deploymentem

## Analysis
- Reuse `processing_monitor_routes.authorized_document/read_authorized_window` and SERVICE middleware in `main.py`; the pages module and steps handler are absent in the inspected checkout. Re-read actual diff before edits, preserving concurrent changes.
- Reuse the repaired explicit `intake` fixture and authorized `monitor` fixture from `test_processing_monitor_routes.py`; the current pages test uses only an API key and cannot demonstrate route behavior. Preserve task-335cb0a3/task-2932fbee checkpoints and historical proof unchanged.
- Filter mixed document events before `audit_page_observations.to_page_observations`: it requires run/attempt on every input and already supports PageCacheReused. Explicitly exclude cache reuse in this slice without removing its existing package support/tests.
- Correct only pages DTO and steps page branches in the sole YAML: current PageObservation lacks StepStarted, sequence is optional, PageFailed omits duration/method/model, and StepObservation excludes page terminals. Keep general event schemas and other operations intact.
- Record the existing ordering discrepancy: proposal read-api specifies `occurred_at,event_id`, reader uses `EVENT#event_id`. Preserve evaluated order and disclose the discrepancy; do not claim chronological acceptance or change the reader/index.
- Apply `learnings/architecture/2026-10-20_monitor-pages-image-copy-and-bound-cursor.md` and `2026-10-20_steps-http-current-auth-and-observation-dto.md`: wrap reader tokens, use entitled behavior RED, copy the router into the image. Recall used local backend, collection `wonderfulkb-learnings`, diagnostic `Collection not found`; retain separation of event-contract and live-producer claims from recalled audit-store/AttemptStarted rules.
- Recheck current AWS authentication during implementation; `plans/handoffs/aws-runtime-readiness-20261020.md` reports expired SSO, while historical document-events evidence reports NoCredentials. Neither establishes current capability or deployed success.

## Approach
- Follow proposal `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md`, sections read-api/delivery/slice-page-outcome and approved 20 October 10:01 SERVICE grants.
- Keep the pages adapter in `processing_monitor_page_routes.py`; use one existing AuditStore/read_document call and pure page mapper, without stored projections, producer/OCR changes, business writes, analysis/run.json or changes to `audit_queries.py`.
- Integrate page terminals into the steps owner's `processing_monitor_step_routes.py` from task-252c7fcd; obtain/reconcile that prerequisite in this delivery before final GREEN/live proof. Do not create a competing steps implementation. If the owner seam remains unavailable, record the exact dependency and keep the task incomplete.
- Use `skill:tdd` for implementation, `validate-implementation` and `code-review` after implementation, `write-review-report` to persist review findings, and `acceptance` only with the actual caller manifest. Run `save-learning` last. Use `aws-containers` for App Runner/ECR work and `signing-in-to-aws` only if authentication needs restoration; AWS operations go through AWS MCP, not shell AWS CLI.

## Implementation
1. Re-read git diff including untracked domain source/tests, sibling steps work and existing evidence/budgets. From repository root verify project venv imports (`pytest`, `fastapi`, `httpx`, `multipart`, `boto3`, `moto`, `yaml`, `jsonschema`, `openapi_spec_validator`) and test collection. Install missing dependencies using existing project requirements; capture a baseline matrix before source edits, without treating its historical failures as new RED.
2. First behavior change: update `be-intake/tests/test_processing_monitor_page_routes.py` to the authorized fixture, retaining existing assertions; add the skeleton and matrix below before production changes. Capture and inspect accepted behavior RED with the new task ID.
3. Add GET `/runs/{run_id}/pages` in `processing_monitor_page_routes.py`. Reuse `validate_identifier` from authorization for run scope, required positive integer attempt_no, limit default50/range1–100 and nonempty next_token max4096. Existing validation/error handlers must return400, not422. Authorize document membership through the shared dependency before audit access.
4. Implement a local strict versioned cursor envelope `{version,operation:pages,case_id,document_id,run_id,attempt_no,reader}`. Validate exact keys/types/scope, integer-not-bool attempt and bounded decoding; validate the inner document token before Query. Pass its `reader` to `read_authorized_window` once; wrap returned page.next_token unchanged in position, including empty filtered windows. Reject document-events/steps/other-run/other-attempt envelopes before audit read. Tokens are continuation hints, never grants.
5. Convert typed events with their `to_item()` allowlists; select exact run/attempt and only page-scoped StepStarted(stage=page_transcription), PageCompleted and PageFailed before pure mapping. Do not feed FileReceived/unscoped events into the mapper. Emit each distinct observation once, with event_id/type/occurred_at/sequence/run_id/attempt_no/page_number/stage; optional duration_ms/method/model/error_code only when stored and allowed. Budget-before-call failure leaves method/model omitted or null. Encode numbers using the existing JSON encoder.
6. Keep terminal-only/start-only observations and multiple distinct events for one page. Do not require RunQueued/AttemptStarted, infer missing run/attempt404, pair timestamps, collapse to latest Page, infer totals/status/progress or turn partial/failed into success. Return exactly items/next_token/observed_at/coverage=partial. Preserve private,no-store on success and all error paths; authorization403, absent/foreign document404, invalid scope/token400 and required auth/membership/read/decode/projection failure503, with no content/raw exception logging.
7. Extend only the steps owner's pure mapping dispatch: page-scoped StepStarted and PageCompleted/PageFailed pass through the same `to_page_observations` projection once; retain source_validation behavior and steps operation-scoped cursor. No synthesized StepFinished/StepFailed or extra Query/store. Add real steps HTTP assertions, not just an isolated mapper test.
8. In `contracts/openapi-processing-monitor.yaml`, define pages-specific observation branches with required sequence/page scope, exact three types and optional observed terminal metadata. Wire PageCollection and steps page allowlist to them; preserve broader general event/cache schemas and other operations. Validate actual HTTP DTOs against this YAML, explicitly noting that cache reuse exposure is a separate increment and chronological ordering remains unresolved.
9. Register the pages router through a minimal main import/include_router; add explicit `COPY --chmod=644` for its module in the existing Dockerfile. Preserve middleware, auth configuration and wheel build. Extend installed-image smoke with a nonempty pages assertion and page-module source hash; keep previous document-events checks.
10. Capture GREEN with identical argv; run all gates below. Install/build the package and build `docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:pages-task-9fcac322 .`. Verify wheel/site-packages source hashes, final router import/registration and nonempty ASGI DTO as UID10001, network disabled, no host source mount/PYTHONPATH; the smoke harness may be supplied through stdin. Record full input-tree/wheel/image hashes including existing uncommitted inputs.
11. In this same implementation task, use AWS MCP to verify STS identity, region eu-central-1, current existing wonderfulkb-ingest App Runner TEST service ARN/URL, ECR repository, owner Jackie, running image/digest/operation and configuration. `be-intake/template.yaml` provisions role/secret, not an App Runner deploy command; obtain the existing owner procedure. Do not invent a service/framework or treat historical tool availability as authorization.
12. Retain a verified accessible recovery image and full configuration securely outside repo; record safe identifiers/hashes only. Acquire the existing owner deployment guard, reconcile inherited ledger, and recheck image/config/revision/active operations immediately before mutation. Stop/reconcile drift; preserve unrelated env, roles, secret refs and auth grants. Push the verified candidate to existing ECR with a unique task tag and verified immutable digest, then perform the guarded in-place image update through the current owner procedure.
13. Poll the actual App Runner operation bounded to15 minutes/15-second intervals; require completed rollout, RUNNING service and readback matching candidate image digest/config. Never equate accepted update with completion. On failure use verified recovery only while revision/guard still proves ownership. If runtime cannot perform an operator step, supply Jackie exact target/digest/config diff/recovery/guard and finish readback/live checks within this task; capability/auth denial is a blocker, not source-only success.
14. Before cloud writes enumerate exact existing synthetic case/document/run/attempt IDs, trusted membership provenance and current explicit case grant in task evidence. Prefer safely retained existing page events. If needed and permitted by the reconciled ledger, insert at most4 deterministic, conditional/idempotent reader-only audit fixtures: one unrelated evaluated event, page start, completed page1 and terminal-only failed page2 with unknown method/model. Use only the existing AuditStore, label reader-only proof explicitly, retain exact IDs/accounting; never claim worker producer proof. No upload, worker replay, inference or business writes; unavailable safe membership/fixture is a blocker.
15. Apply the stricter of existing remaining allowance and these task ceilings: 2 candidate rollouts,1 recovery rollout,16 live HTTP GET,20 exact fixture preflight/readback reads,4 audit insert attempts,0 upload/POST/business writes/provider calls. Default auth-policy writes0; if an exact synthetic grant must be added, at most1 guarded version update plus1 recovery using expected old VersionId, preserving all other grants. Enumerate every grant and request/write, never reset inherited budgets or consume Case Client allowance. Resolve ambiguous writes by exact readback, never blind retry.
16. Verify the live pages DTO with exact nonempty expected event IDs/types/run/attempt/page/sequence/metadata, coverage/observed_at/no-store and no content. Assert two pages, empty evaluated continuation where the safe fixture permits, wrong-attempt filtering, cross-operation/scope token400 and missing/forged grant denial. Also read the steps page terminal exactly once. Check read-error503 hermetically, without cloud fault injection. Health/empty200 alone cannot establish live functionality.
17. Save task-local evidence in `plans/monitoring/task-9fcac322-bb59-4168-aa0d-fa45933d3724-runtime-evidence.md`: separate SOURCE / INSTALLED / DEPLOYED / LIVE-FUNCTION-VERIFIED, target/config/source/wheel/image provenance, rollout timestamps, assertions, ledger and concrete unresolved blockers. Link this canonical plan in the implementation checkpoint/state via normal harness handling; do not edit task lifecycle or instruction files. Complete validation/review/registered acceptance gates and save learning last.

## TDD
- Implementace TDD cyklu dle skill:tdd. Cwd `/Users/michal/Projects/wonderfulkb`; new proof `plans/checkpoints/task-9fcac322-bb59-4168-aa0d-fa45933d3724.red-green-proof.md`. Never copy/rewrite historical proof or accept dependency/import/collection failure as RED.
- Append this executable skeleton to `be-intake/tests/test_processing_monitor_page_routes.py`; update the existing API-key-only test to `monitor` + HEADERS before capture. Expand that same file with the matrix below before production edits.

```python
from fastapi.testclient import TestClient
from test_monitor_file_received import intake  # explicit fixture dependency
from test_processing_monitor_routes import monitor, HEADERS
from document_processing.audit.audit_events import PageCompleted


def test_pages_returns_real_terminal_only_observation(monitor):
    main, _, _, _, _, table = monitor
    event = PageCompleted(
        schema_version=1, event_id="pages-terminal", sequence=7,
        case_id="case-test", document_id="doc-test", type="PageCompleted",
        occurred_at="2026-10-20T10:00:00Z", run_id="run-test",
        attempt_no=1, stage="page_transcription", page_number=1,
        method="native", duration_ms=12.5,
    )
    table.query.return_value = {"Items": [event.to_item()]}
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/cases/case-test/processing/documents/doc-test/runs/run-test/pages",
            params={"attempt_no": 1, "limit": 1}, headers=HEADERS,
        )
    assert response.status_code == 200  # RED: entitled request has no handler
    body = response.json()
    assert body["items"] == [{
        "event_id": "pages-terminal", "sequence": 7, "type": "PageCompleted",
        "occurred_at": "2026-10-20T10:00:00Z", "run_id": "run-test",
        "attempt_no": 1, "stage": "page_transcription", "page_number": 1,
        "method": "native", "duration_ms": 12.5,
    }]
    assert set(body) == {"items", "next_token", "observed_at", "coverage"}
    assert body["coverage"] == "partial" and body["next_token"] is None
    assert body["observed_at"]
    assert response.headers["cache-control"] == "private, no-store"
    table.query.assert_called_once()
    assert table.query.call_args.kwargs["Limit"] == 1
    table.scan.assert_not_called()
```

```bash
TASK_ID=task-9fcac322-bb59-4168-aa0d-fa45933d3724 python3 "$HOME/.config/opencode/skills/tdd/scripts/proof-capture.py" red -- env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_page_routes.py
TASK_ID=task-9fcac322-bb59-4168-aa0d-fa45933d3724 python3 "$HOME/.config/opencode/skills/tdd/scripts/proof-capture.py" green -- env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_page_routes.py
```

| Test | RED | GREEN |
|---|---|---|
| `test_pages_returns_real_terminal_only_observation` | Authorized missing route returns404, not200 | Exact nonempty allowlisted terminal-only DTO; one Query |
| Existing partial-observations test with approved SERVICE precondition | Missing route404 | Original envelope/no-store assertions retained |
| Added pagination/auth/scope matrix | Missing behavior, not fixture setup failure | Exact assertions below pass without softened expectations |
- Read helper outcomes: accepted_red/nonzero child followed by accepted_green/child0 with identical argv. Add a separate supported new cycle if subsequent behavior requires it; never manually edit proof.

## Testing
- Test real FastAPI app + shared authorization/membership + actual AuditStore over mocked table boundary: start/completed page1, failed page2, terminal-only, repeated distinct page observations, budget failure unknown method/model, mixed FileReceived/unrelated stages/cache events, two runs/two attempts and absence of RunQueued/AttemptStarted. Assert no totals/latest/content fields or guessed durations.
- Test limit1 and100, invalid0/101/noninteger; missing/zero/negative/malformed attempt, invalid run ID, malformed/oversized/empty/nested-invalid cursor. Verify exact last evaluated ExclusiveStartKey, ConsistentRead, Limit and one Query per request; empty filtered page with continuation must not fetch until filled. Cross-case/document/run/attempt/steps/document-events tokens fail400 with no audit Query after valid auth/membership.
- Test missing/forged/header-claimed identity, revoked grant/case mismatch, auth-source outage/malformed policy before membership/audit reads; missing/foreign document404, retained history with current grant and trusted provenance, membership failure503 without retained fallback; audit unavailable/decode/projection failure503. Assert safe errors and private,no-store everywhere.
- Extend `be-intake/tests/test_processing_monitor_step_routes.py` with shared page projection equality and exactly one terminal per persisted PageCompleted/PageFailed, including terminal-only; retain source_validation assertions. Validate nonempty pages and steps responses against sole YAML with required sequence, finite nonnegative optional duration and safe observed metadata; preserve all prior GET/event/cache tests.
- Run focused proof first; then full matrix without ignores: `PYTHONPATH=be-document-processing/src:be-validator-agent/trigger:be-validator-agent/pipeline be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests be-validator-agent/trigger/tests be-validator-agent/pipeline/tests`. Report every failure with baseline comparison; do not relabel sibling worker/steps failures green or remove assertions.
- Run registered gate verbatim: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; run `git diff --check` and existing OpenAPI validation tests. Verify installed image and live assertions from implementation steps10–16; retain full command outcomes, not only a health response.

## Files
| Path | Concrete edit |
|---|---|
| `be-intake/app/processing_monitor_page_routes.py` | New page handler, strict cursor wrapper and safe mapper adapter |
| `be-intake/app/main.py`, `be-intake/app/Dockerfile` | Minimal router registration and explicit packaged file |
| `be-intake/app/processing_monitor_step_routes.py` | Reconcile steps owner prerequisite, add shared page branch only |
| `be-intake/tests/test_processing_monitor_page_routes.py` | Authorized genuine RED and full bounded HTTP matrix |
| `be-intake/tests/test_processing_monitor_step_routes.py` | Real steps single-terminal and projection parity assertions |
| `be-intake/tests/image_processing_monitor_smoke.py` | Installed pages route/DTO/source-hash checks, retain previous checks |
| `be-document-processing/contracts/openapi-processing-monitor.yaml` | Pages-specific DTO branches and steps page allowlist; sole specification |
| `be-document-processing/tests/test_monitor_openapi_observation_contract.py` | Narrow schema assertions for new page/steps branches |
| `plans/checkpoints/task-9fcac322-bb59-4168-aa0d-fa45933d3724.red-green-proof.md`, `plans/monitoring/task-9fcac322-bb59-4168-aa0d-fa45933d3724-runtime-evidence.md` | Helper-generated proof and honest task-local delivery ledger |
- Reuse unchanged `processing_monitor_authorization.py`, `processing_monitor_routes.py`, `audit_page_observations.py`, `audit_queries.py`, event types and existing package build; any necessary shared-facade change must be a documented minimal seam, not a rewrite.

## Progress
- [x] Resolve canonical plan path and inspect current tracked diff plus relevant untracked source/tests.
- [x] Read proposal, sole YAML, authorization/reader/mapper seams, sibling steps plan and historical proof/deployment context.
- [x] Specify TDD, full registered gates, guarded in-place deployment, bounded live assertions and evidence states.
- [ ] Implement through genuine RED→GREEN, package/install, deploy and live-verify in the subsequent implementation phase.
