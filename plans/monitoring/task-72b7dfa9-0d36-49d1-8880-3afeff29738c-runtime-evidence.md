# Steps HTTP delivery — task-72b7dfa9-0d36-49d1-8880-3afeff29738c

## Delivery status

| Gate | Result |
| --- | --- |
| SOURCE | BLOCKED: no trusted caller→case authorization/document-scope HTTP interface in intake; steps route not implemented. |
| INSTALLED | NO: `python-multipart==0.0.20` installed locally in the project test venv only; no new application package/image installed. |
| DEPLOYED | NO: no application artifact was built or released. |
| LIVE-FUNCTION-VERIFIED | NO: no authenticated live steps HTTP request, no live content assertion. |

## Concrete prerequisite

`be-intake/app/main.py` has a service-wide `x-api-key` comparison in `guard()` (lines 121–140). `require_case()` (lines 152–156) validates a case ID and checks case existence, and is invoked by the guard only for the upload path. It does not identify a caller, check caller membership/entitlement on the requested case, or verify document membership. No `processing_monitor_routes.py` or equivalent authenticated document-scope reader exists in `be-intake/app/`; the existing document-event, page, and lifecycle HTTP tests target routes not implemented in that app. The OpenAPI contract itself explicitly marks trusted identity-to-case authorization unavailable and does not establish a deployed route. `audit_queries.read_document()` can perform one bounded document query but its document-scoped token is not authorization and has no steps operation/run/attempt scope.

Required owner interface before exposure: trusted, authenticated caller identity and a case entitlement decision for that caller, a document-in-case lookup, policy for forbidden versus masked missing resources, no-store on success and all errors (including middleware), and an operation-bound adapter to the existing audit reader with required-read failure mapped to 503. A shared API key plus `require_case` is insufficient. Do not bind the new router to the shared-key guard or claim a 200 via a permissive mock. With no safe route to release there is no artifact digest, target revision/config diff or verified recovery artifact for this task; the planned `wonderfulkb-ingest` eu-central-1 App Runner target remains unverified here. Deployment and Jackie operator step require the interface and a build artifact first.

## Captured local evidence

- Existing focused fixture explicitly imported from `test_monitor_file_received.py`; installed pinned `python-multipart==0.0.20` in `be-document-processing/.venv` and verified `--collect-only` collects one test.
- Canonical helper accepted RED (normal child exit 1): `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_step_routes.py`; valid request for synthetic `case-test/doc-test/run-test`, attempt 1, limit 1 returns 404 instead of required 200. Actual output and timestamps are in `plans/checkpoints/task-72b7dfa9-0d36-49d1-8880-3afeff29738c.red-green-proof.md`. GREEN was not captured because publishing an unauthorized route would violate the plan's explicit gate.
- `PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests`: 189 passed.
- `PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_monitor_file_received.py be-intake/tests/test_processing_monitor_routes.py be-intake/tests/test_processing_monitor_page_routes.py be-intake/tests/test_processing_monitor_lifecycle_views.py be-document-processing/tests/test_monitor_openapi_observation_contract.py be-document-processing/tests/test_monitor_audit_storage.py be-document-processing/tests/test_monitor_page_observations.py`: 56 passed, 1 failed (lifecycle missing route 404), 2 errors (existing GET sketches cannot resolve `intake` fixture). These are independent of the focused fixture repair; no tests were excluded from this run.
- `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`: 17 tests passed, build bundled 5 functions.
- `git diff --check`: passed.

## Live fixture and request accounting

Only local, mocked `case-test/doc-test/run-test` was used. Live fixture ID: none; live HTTP requests: 0; synthetic cloud writes: 0; deployments: 0; rollback: not applicable. No worker event or live route behavior was inferred from hermetic tests or OpenAPI declarations. Previous task proof and failed-infrastructure history were preserved.
