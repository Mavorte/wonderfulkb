# Plan 2026-10-20: Monitoring pages HTTP — endpoint, fixture, runtime

## Progress
- [x] Canonical path allocated for task-2932fbee-4ac8-47eb-981b-73bbcc17b40f.
- [x] Inspected route/fixture/reader/auth seams, contracts and previous failed proof.
- [x] Defined implementation gates, TDD and live acceptance steps; implementation not started.
- [x] Corrected canonical H1 after `invalid_header` recovery; retained the existing task plan.

## Analysis
- `be-intake/app/main.py` has upload/list only; its shared x-api-key guard and `require_case` existence lookup do **not** authorize caller→case. No checked-in `processing_monitor_routes.py`, shared document-scope/no-store/read-error adapter or step router exists. First establish the actual trusted identity→case authorization and document ownership interface plus permitted synthetic caller; if unavailable, document exact missing interface/owner and block route exposure/deployment (no permissive substitute or source-complete claim).
- `be-document-processing/src/document_processing/audit/audit_queries.py:read_document` already executes one consistent, bounded document Query and returns last-evaluated continuation, but its token is document_events-scoped only; route adapter must bind pages/run/attempt/operation without changing the shared reader or scanning. `audit_page_observations.py:to_page_observations` already maps page start/terminal (+ independently delivered cache reuse); reuse it, restrict this operation to the brief's three event types, preserve multiple observations/terminal-only fragments.
- `be-intake/tests/test_monitor_file_received.py:intake` is a **module-local** fixture, no `be-intake/tests/conftest.py`; import it explicitly in focused test. `be-document-processing/.venv/bin/python` imports pytest/FastAPI/boto3/httpx with `PYTHONPATH=be-document-processing/src`, but `multipart` is missing; install the intake-pinned `python-multipart` into that venv and check main import before RED. Old `plans/checkpoints/task-335cb0a3-814a-4a7c-a12a-80bdb3bdfc42.red-green-proof.md` records fixture-not-found, not behavioral RED; preserve it and failedinfra evidence.
- `be-intake/app/Dockerfile` builds a wheel and installs the audit subset; it copies only `main.py` and `content_hashes.py`, so add the owned route module(s) to the artifact. `be-intake/README.md` and `plans/monitoring/file-received-build-contract.md` document local image build, not an App Runner deploy command. Discover current owner/config/revision and supported test deployment interface before modifying the service. Read-specific authorization blocker recorded in `plans/monitoring/task-9d34c790-5c01-46ba-96d0-bc7f45740763-blocker.md`.
- Knowledge: `learnings/test-failures/intake-monitoring-red-multipart-explicit-fixture.md`, `learnings/architecture/2026-10-20_bounded-monitoring-read-plan-semantics.md`, `learnings/architecture/2026-10-20_keep-page-observation-mapping-pure-and-window-scoped.md`; no repo-local critical-patterns file or PlantUML found. Relevant skills: `tdd` for implementation proof, `wful` only if platform operations become necessary, `save-learning` after delivery.

## Approach
- Resolve the trusted case authorization/document-scope decision and shared HTTP read foundation with its owner before opening a case-scoped GET. Reuse the proven foundation if it appears; otherwise specify required input/output, principal trust source, document lookup and failure policy as a concrete blocker, not a fake implementation. Keep the single existing FastAPI service.
- Make pages a small domain router: validate attempt_no positive, limit 1–100 and operation-bound opaque cursor; decode/validate case/document/run/attempt/operation before passing the inner document cursor to `read_document`; wrap its returned last **evaluated** cursor even for zero matching items. Filter just that one window, map typed event `to_item()` through `to_page_observations`, allowlist StepStarted(page_transcription), PageCompleted, PageFailed and known fields; do not replay or infer status, total, duration, method/model on budget failures.
- Ensure page terminal event is also one observation in steps GET if a real steps implementation is available; do not produce StepFinished/StepFailed as its duplicate. Update only pages and step observation DTO/allowlist in `be-document-processing/contracts/openapi-processing-monitor.yaml` to reflect actual typed fields (optional sequence/known duration/method/model, terminal-only and empty continuation); preserve every other operation. Cache reuse is separately owned and must not be newly introduced by this pages slice.

## Implementation
1. Identify authorized document reader/auth interface and supported App Runner deployment owner, current target and synthetic fixture; stop with a named blocker if not available. Install pinned intake test dependency into project venv; verify import/fixture collection without capturing it as RED. Keep all pre-existing proof files intact.
2. First edit `be-intake/tests/test_processing_monitor_page_routes.py` with explicit fixture import and focused failing behavior, then use `skill:tdd` to capture genuine new-task RED and GREEN using identical argv. Save canonical `plans/checkpoints/task-2932fbee-4ac8-47eb-981b-73bbcc17b40f.red-green-proof.md` through the skill-approved interface.
3. Add `be-intake/app/processing_monitor_page_routes.py`; minimally wire via `processing_monitor_routes.py`/`main.py` only after real shared auth/document-scope/no-store/error/reader seam exists. Convert read failures to 503, scope to trusted 403/404 policy, invalid request/token to 400, always `Cache-Control: private, no-store`, including validation/auth errors. Do not modify `audit_queries.py` or introduce a new store/index.
4. Add the domain module to `be-intake/app/Dockerfile` copy/package; narrowly correct YAML page/steps DTO where mismatched. Check unchanged prior routes and event read behavior.
5. Run focused and package regression gates, then inspect supported deployment path, image provenance, existing App Runner config and owner. Retain verified recovery image/config, guard against concurrent revision change, build/install and deploy in-place to existing `wonderfulkb-ingest` in eu-central-1 with bounded rollout/health wait; preserve env/IAM/auth. For unsupported permission/interface, record digest, target, config diff, recovery and exact narrow Jackie operator step within this task; do not claim deployment or defer it to a new task.
6. Perform bounded authenticated HTTP assertions against approved synthetic case/document/run/attempt on the changed pages and steps DTO: actual observation IDs and fields, isolation/continuation and private,no-store, negative auth/scope. Reuse proven existing synthetic event, never replay ambiguous POST or claim worker→HTTP from a manual audit insert. Capture request/write counts, actual deployed revision/image digest and operation time. Correct in-scope package/router defects, retest and guardedly redeploy; rollback to verified artifact if necessary. Record SOURCE / INSTALLED / DEPLOYED / LIVE-FUNCTION-VERIFIED separately; content branch without producer remains unverified.

## TDD
- Target: `be-intake/tests/test_processing_monitor_page_routes.py`; preserve old failed fixture sketch as history while replacing it with executable behavioral tests. Prepare environment with the pin in `be-intake/app/requirements.txt`; verify `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -c 'import multipart, pytest, fastapi, boto3, httpx, document_processing'` and focused fixture collection first. Never use system Python fallback.
- Initial skeleton (after real authorized fixture identity is supplied; `intake` is explicitly imported, and `docs.get_item` reflects the existing authorized synthetic document):

```python
from fastapi.testclient import TestClient
from test_monitor_file_received import intake  # pytest fixture; no shared conftest


def test_pages_exposes_scoped_partial_window(intake):
    main, _, docs, _, _, _ = intake
    docs.get_item.return_value = {"Item": {"case_id": "case-test", "document_id": "doc-test"}}
    # Supply the established trusted authorized caller through the real auth seam here.
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/cases/case-test/processing/documents/doc-test/runs/run-test/pages",
            params={"attempt_no": 1, "limit": 1},
            headers={"x-api-key": "test-key"},
        )
    assert response.status_code == 200  # RED: missing route currently returns 404
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["coverage"] == "partial"
```

- Run **same argv** for RED/GREEN: `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_page_routes.py`. RED requires a collected, actually authorized test failing at route behavior (404 vs 200), never import/fixture/auth setup failure. If trusted identity seam not yet available, hold before recording RED rather than manufacturing a green policy.
- Extend focused tests before implementation of each behavior: two pages completed/failed (budget failure method/model absent), terminal-only and repeated page observations; run/attempt isolation; unrelated evaluated events yielding `items=[]` **and** next_token, then following window; count exactly one Query per request/no Scan; reject malformed attempt/limit/token and cross-run/attempt/operation token; 401/403/404/no-store including error paths, reader failure 503; verify one page terminal in steps GET without duplicate step terminal.
- RED→GREEN checkpoints: `test_pages_exposes_scoped_partial_window`: 404→200 with partial/no-store; `test_pages_empty_window_continues`: missing route→empty items + scope-bound evaluated cursor + exactly one Query; `test_pages_rejects_cross_scope_cursor`: missing validation→400; `test_pages_reader_failure`: incorrect empty/500→503; `test_pages_denied_scope`: shared-key leakage→policy 403/404. Save canonical proof under current task ID.

## Testing
- Run focused pages/steps and existing monitoring tests with project venv, then relevant intake and audit package suites without excluding failing tests; keep registered `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` unchanged. Review OpenAPI semantic focused test and `git diff --check`; report all actual failures without relabeling infrastructure failures as behavioral RED.
- Validate wheel import and main router in built linux/amd64 image as runtime UID, with network disabled for local import; verify source/image digest before test rollout. Hermetically verify read503, no cloud fault injection.
- In `plans/monitoring/` write task-specific redacted runtime evidence: exact target/owner/revision, recovery, image/package digests, config diff, guarded rollout result, fixture IDs/counts, HTTP status/header/ID/schema/continuation assertions and blocker or rollback. `/healthz`, local TestClient and 200 empty alone do not establish live functionality; do not publish secrets/document contents.

## Files
- `be-intake/tests/test_processing_monitor_page_routes.py`: explicit fixture import and real matrix; existing fixture owner `test_monitor_file_received.py` unchanged.
- `be-intake/app/processing_monitor_page_routes.py`: owned operation-bound page read/filter/DTO; `be-intake/app/processing_monitor_routes.py` and `main.py`: minimal shared router integration **only once trusted seam exists**.
- `be-intake/app/Dockerfile`: include new module(s) in installed runtime image.
- `be-document-processing/contracts/openapi-processing-monitor.yaml`: narrowly align page/step observation schemas; keep one YAML.
- `plans/checkpoints/task-2932fbee-4ac8-47eb-981b-73bbcc17b40f.red-green-proof.md`, `plans/monitoring/` task-specific evidence: produced during implementation, never replacing predecessor proof.
