# Lifecycle HTTP delivery evidence — task-a67c7b62-949e-4720-b1a2-51fcc3502cec

## State

- SOURCE: **partial**, only fail-closed routes registered; no authorized lifecycle 200 endpoint.
- INSTALLED: **local Docker image only**; audit wheel and route module import as unprivileged image user. Image manifest-list digest `sha256:48917626681f1ab372b6e744eeb664c2f8e9884ec4a283cd6aa050e4a99f6b57`, local tag `wonderfulkb-ingest:lifecycle-deny-task-a67c7b62`. This is not a pushed/recovery artifact.
- DEPLOYED: **no**. LIVE-FUNCTION-VERIFIED: **no**. No cloud writes, synthetic POSTs, or HTTP calls; request/write ledger 0/0; no fixture IDs asserted.

## Blocking interfaces

`be-intake/app/main.py` authenticates only a single global `x-api-key`; `require_case` merely checks the existence of a case row. There is no trusted request identity → case entitlement and document-in-case authorization seam, nor a shared HTTP no-store/read-failure reader facade to reuse. Granting 200 via key + existing case would expose audit data across cases. New routes deliberately return 403, private/no-store even if a shared key is valid. They are **not** the promised bounded observations. The pure `audit_queries.read_document(table, case_id, document_id, limit, next_token)` provides one bounded read but cannot establish entitlement. It currently rejects `ResultPublished` in `_event_from_item`, so publication cannot be claimed as live-readable without an owner-supported decoder/event contract. `audit_lifecycle_observations.reduce_observations` is the canonical reducer; the old HTTP sketch's `status`/`outcome` are not its fields.

AWS CLI v2.38.1 `aws sts get-caller-identity` and `aws apprunner list-services --region eu-central-1` both failed with `NoCredentials`. Therefore actual owner/service ARN, revision/image/config, verified recovery artifact, deploy interface, authorized synthetic fixture and guarded rollout were not established. Do not push or replace a guessed revision. AWS login requires user confirmation; none was provided in this run.

Jackie's bounded operator continuation in **this task**: provide/confirm the service owner's trusted identity-to-case and document membership read authorization interface plus its 403/404 masking policy and the existing audited table/reader integration; confirm publication decoder support. After the routes actually return tested bounded observations, obtain AWS credentials through the approved authentication flow, inspect `wonderfulkb-ingest` App Runner in eu-central-1 and current image digest/config, retain a verified rollback image/config, determine supported existing build/push/deploy command, check revision guard immediately before deployment, then deploy/wait/read back digest and issue bounded authenticated GETs on an authorized synthetic case/document. No arbitrary key or case-existence fallback.

## Verification

- Fresh task RED and GREEN captured via `skill:tdd` at `plans/checkpoints/task-a67c7b62-949e-4720-b1a2-51fcc3502cec.red-green-proof.md` with identical argv from `be-intake`: `env PYTHONPATH=../be-document-processing/src ../be-document-processing/.venv/bin/python -m pytest -q tests/test_processing_monitor_lifecycle_views.py`. GREEN proves *denial only*; two intermediate rejected false GREEN attempts were preserved by the helper.
- Intake `test_monitor_file_received.py` + fail-closed lifecycle test: 8 passed.
- Processing lifecycle/retry/storage/OpenAPI focused tests: 75 passed.
- Existing intake monitor event/steps/pages sketches: one fixture setup error and two 404-versus-200 failures (undelivered prior routes); not treated as passing API coverage.
- Registered `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`: 17 tests passed and 5 functions bundled.
- `docker build -f be-intake/app/Dockerfile -t wonderfulkb-ingest:lifecycle-deny-task-a67c7b62 .` succeeded; standalone image `python -c 'import main, processing_monitor_lifecycle_routes, document_processing.audit.audit_lifecycle_observations'` succeeded, 3 guarded routes.

Source SHA256: `main.py` eac08315bbcdd805c55ba99052fe9c7be3f121b63425034ff844ef1d431a75c6; `processing_monitor_lifecycle_routes.py` 67224d174dc4f500b667dc6b85e4f08508dd5a6bc0f2757f47422d7451bbeebd; `Dockerfile` aec8a99121926c9f05ed7fdd4288ec32a9c6b4a51cf1ebde1be711908b8af6b3.
