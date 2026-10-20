# Document events HTTP — task-dfd140ba-c040-48c9-bb5f-f5c204a5d647

## Prerequisite decision

BLOCKED: the legitimate service-side trusted caller identity → case read-entitlement owner/interface and an authenticated, authorized synthetic case/document fixture have not been established. `be-intake/app/main.py` `guard()` checks only the global `x-api-key`; `require_case()` checks only whether a case exists and is used on the upload path. The installed lifecycle facade in `be-intake/app/processing_monitor_lifecycle_routes.py` explicitly returns 403 until this case authorization exists. `be-intake/tests/test_monitor_file_received.py` mocks a case row but provides no caller identity or entitlement. The existing document-events test sketch expects 200 from only the shared key and lacks an imported module-local fixture: it cannot serve as authorized functional proof. The single OpenAPI contract itself says the trusted interface is unavailable (lines 6–13, 125–126); it specifies `coverage: partial` as a required field (lines 149–159), contrary to the three-key sketch.

Required owner decision: supply a trustworthy authenticated principal source and an owner-operated authorization decision for that principal and case (including denial/read-error and 403/404 masking policy), plus a safe authorized test caller/case/document fixture. The intake adapter can then validate document membership via the existing `(case_id, document_id)` keys and use the installed bounded `AuditStore.read_document` interface. A shared key, a client-supplied identity/case header, or an allow-all fixture does not provide that decision.

## Delivery states

- SOURCE: blocked before document-events production route implementation; no new route exposed.
- INSTALLED: no task-specific artifact built or installed.
- DEPLOYED: no task-specific image/revision deployed.
- LIVE_VERIFIED: no authorized document-events HTTP verification.

Cloud synthetic fixture ID: none. Cloud synthetic writes: 0. Live HTTP requests: 0. Deployments: 0. Artifact digest, target revision, config diff and verified recovery image: not established (no deployable route). No earlier evidence is relabelled. The task's canonical TDD RED/GREEN proof is not produced: a positive read based on the shared key would be an unauthorized route and an error from an unresolved fixture would be an invalid RED. Once the owner prerequisite is provided, resume this same task at the checkpoint: focused accepted RED, guarded implementation and GREEN, full gates, provenance/recovery/revision-guarded in-place test deployment, and bounded authenticated live HTTP assertions.

## Local verification (no route implementation)

- `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -c 'import fastapi, pytest, multipart, yaml, document_processing; print("dependencies ready")'` — succeeded. A direct probe without the explicit `PYTHONPATH` failed to import `document_processing`; pytest's conftest supplies the source path for its test commands. This environmental probe is not a TDD RED.
- `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_audit_storage.py be-document-processing/tests/test_monitor_openapi_observation_contract.py` — 35 passed, including validation of the existing sole OpenAPI YAML; no YAML edits.
- `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests` — 209 passed.
- `be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_routes.py` — one setup error: the pre-existing sketch has no `intake` fixture import. This is not behavioral RED and is not proof of an implemented route.
- `npm --prefix apps/backoffice test` — 17 passed; `npm --prefix apps/backoffice run build` — succeeded (five functions bundled).

The helper from skill:tdd was loaded, but was not invoked with an invalid collection/environment error or with an unauthorized 200 assertion. Its canonical proof file is absent; there is no claim of accepted RED or GREEN. No task-related production or test files were modified.
