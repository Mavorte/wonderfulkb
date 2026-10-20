# Monitoring pages HTTP — task-2932fbee-4ac8-47eb-981b-73bbcc17b40f

## Delivery status

| Gate | Result |
| --- | --- |
| SOURCE | Blocked: no trusted caller-to-case authorization or shared document-scope HTTP reader interface in the intake service. Only the focused test fixture import was repaired. |
| INSTALLED | No task-specific artifact installed. Existing project venv imports `multipart`, pytest, FastAPI, boto3, httpx and `document_processing`. |
| DEPLOYED | Not attempted; no safe new route exists to deploy. |
| LIVE-FUNCTION-VERIFIED | Not attempted. No HTTP requests or synthetic writes. |

## Blocking interfaces

`be-intake/app/main.py` `guard()` validates a single service-wide `x-api-key`. `require_case()` validates syntax and case existence and is called only for upload; it has no authenticated caller identity, case entitlement decision, or document-in-case read policy for the requested principal. The app has no `processing_monitor_routes.py`, steps GET, or common authenticated read adapter. `be-intake/tests/test_monitor_file_received.py` supplies a mock case row, not an authorized synthetic caller. Supplying that mock to a pages test would manufacture a false authorization proof. Required owner input: an actual trusted principal source and caller→case entitlement interface, a document membership lookup and 403/404 masking policy, an authorized synthetic caller/case/document fixture, and a shared no-store/error/bounded-reader route seam. Do not use a client-provided identity claim or shared API key alone as the authorization decision.

AWS CLI `aws sts get-caller-identity --query '{Account:Account,Arn:Arn}' --output json` returned `NoCredentials`; `aws --version` reports `aws-cli/2.38.1`. The documented test target is `wonderfulkb-ingest` App Runner in eu-central-1, but actual account, owner, current revision/image/config, supported deployment interface and verified recovery artifact cannot be established from this session. `be-intake/README.md` documents only a local Docker build, not an App Runner rollout. AWS login needs user confirmation under the sign-in workflow. No target changes or credentials were written. A guarded operator deployment step cannot be safely specified until the auth seam and target/current revision/recovery are verified; Jackie should supply/confirm those inputs within this task before the operator action.

## Verification performed

- `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -c 'import multipart, pytest, fastapi, boto3, httpx, document_processing; print("intake imports available")'`: passed.
- `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest --collect-only -q be-intake/tests/test_processing_monitor_page_routes.py`: one test collected after explicit import of the existing module-local `intake` fixture. Its shared-key caller is **not** an authorized fixture, so this is not a behavioral RED.
- `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests`: 16 passed, 2 failed (existing absent lifecycle/steps routes return 404), 2 errors (prior module-local fixture not imported in pages/document-events sketch; pages fixture import has since been corrected). This run predates that one-line pages test fix. No failing test was excluded.
- `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests`: 189 passed.
- `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`: 17 tests passed, build bundled five functions.

No tdd proof-capture was launched: a failing 404 with only the shared key would not be a genuinely authorized route-behavior RED under the plan. The canonical RED/GREEN proof file does not exist; no GREEN or source/runtime acceptance is claimed. Prior proof/failedinfra evidence was left intact. No source digest, image digest, deployed revision or configuration diff exists for this task because no deployable production change was made.
