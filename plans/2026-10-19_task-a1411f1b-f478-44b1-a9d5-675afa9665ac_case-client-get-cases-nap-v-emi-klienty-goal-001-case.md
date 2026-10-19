# Plan 2026-10-19: [acceptance-fix] Case Client: GET /cases napříč všemi klienty

Deliver the missing global list behavior, implementation evidence, and bounded deployed-runtime evidence while preserving the earlier task's changes and history.

## Analysis

- The parent task added only `test_global_cases_route_returns_shared_public_list`; handler/repositories, API contract, tooling, deployment, and live verification remain absent per its checkpoint.
- `plans/tasks/2026-10-19_case-client-list-all-cases.md` and the original plan define the endpoint contract and target files; `plans/checkpoints/case-client-list-all-live/authorized-contract-20261019.md` governs the authorized live cycle and task-wide limits.
- Existing proof `plans/checkpoints/task-c88015bb-6b27-4a9b-916a-d22bb8308f57.red-green-proof.md` records only a setup failure (`ModuleNotFoundError: simplejson`), so it is not behavioral RED. Preserve it; do not manufacture a new RED after implementation exists.
- Global listing requires a separate repository path: DynamoDB cases-table Scan, global route-bound cursor/fingerprint and `case_id` resume position. The per-client list path performs client lookup and GSI Query and must remain unchanged.
- Applicable learnings: `learnings/architecture/2026-10-19_case-client-global-scan-cursor-and-live-evidence.md`, `learnings/architecture/2026-10-19_case-client-replan-preserves-exhausted-live-budget.md`, `learnings/tooling/2026-10-19_validate-execution-prerequisites-before-starting-a-gated-tdd.md`, and `learnings/tooling/2026-10-19_case-client-live-tool-deadline-and-budget-guards.md`.
- Relevant skills: `tdd` for evidence-aware test verification; `validate-implementation` after code changes; `acceptance` for recording final goal findings; `save-learning` at task completion.

## Approach

- Inspect current source and tests first; preserve already-completed parent changes. Inspect proof lineage and historical RED before deciding whether it applies; link genuine historical behavior RED if available, then capture fresh task-scoped GREEN.
- Complete global GET `/cases` across handler, repository protocol, mock and DynamoDB adapters; retain public projection, pagination and errors without client lookups.
- Update the protected API definition, SAM method, documentation and existing component deploy/live tooling. Keep the existing endpoint, API key policy, IAM scope, table schema and four prior operations intact.
- Run offline behavioral/regression gates before considering live mutations. For live execution, use only the existing authorized test target and its current ledger/budgets; do not treat this follow-up as a new budget or replay ambiguous POSTs.

## Implementation

1. Read current relevant files and task-scoped proof/checkpoint artifacts; verify whether implementation changes now exist. Check Python dependencies/test bootstrap before evidence capture; setup errors are not RED.
2. Implement `list_cases(filters, limit, token)` in both repositories and dispatch GET `/cases`. Mock pagination must use an independent global cursor. DynamoDB must Scan only the cases table, bound work, resume within SDK pages, validate route-bound tokens, and sanitize operational failures.
3. Add handler/mock and DynamoDB Stubber coverage for shared cases across clients, empty results, limits and pagination without duplicates/loss, malformed/foreign tokens, public fields, no client-table reads/per-client queries, and failures. Preserve existing operation tests.
4. Add the API-key-protected GET contract to OpenAPI/SAM and update README and existing static/deploy/live tooling. Keep checks for all five methods and existing authorization/integration invariants.
5. Run focused tests, full Case Client unittest discovery, compile/static/template checks and registered gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`. Record exact results.
6. Only after offline gates, follow the live contract's read-only target inspection, verified recovery snapshot, revision guards and remaining task-wide limits. Deploy in place using the existing tool, verify deployed hash/config before and after the bounded HTTP suite, preserve sanitized report and fixtures, and stop on auth, permission, concurrency or budget blockers.

## Testing

- Focused command: `PYTHONPATH=be-case-client/src:be-case-client/tests python3 -m unittest test_case_client_lambda.CaseClientLambdaTests.test_global_cases_route_returns_shared_public_list`.
- Regression command: `PYTHONPATH=be-case-client/src python3 -m unittest discover -s be-case-client/tests -p 'test_*.py'`.
- Exercise DynamoDB behavior through botocore Stubber and assert exact cases-table Scan, continuation, no client GetItem/per-client Query, and sanitized errors.
- Run template/OpenAPI/deploy-tool tests, Python compile checks, and the registered backoffice test/build gate.
- Live evidence must show global synthetic fixtures across clients, full limit-1 pagination, bad/foreign token rejection, API-key protection, and regressions for existing operations against the verified deployed hash. Retain sanitized report and exact deployment identity; local green is not live proof.

## TDD

Use skill `tdd` for evidence provenance. Do not create a fabricated RED after implementation exists. Link the historical genuine behavioral RED from the parent/previous proof only if one is found; the supplied parent proof is setup failure only. Capture fresh GREEN under this follow-up task for the focused behavior and preserve the invalid historical artifact unchanged.

**Test file:** `be-case-client/tests/test_case_client_lambda.py`  
**Framework:** `unittest`, already used by the handler tests.  
**Run command:** `PYTHONPATH=be-case-client/src:be-case-client/tests python3 -m unittest test_case_client_lambda.CaseClientLambdaTests.test_global_cases_route_returns_shared_public_list`  
**Edit hint:** Reuse the existing assertion; do not add a duplicate test solely to create a RED.

| Test | Existing RED provenance | Fresh GREEN |
|---|---|---|
| `test_global_cases_route_returns_shared_public_list` | Search parent/previous evidence for a genuine failure caused by unsupported GET `/cases`; supplied proof is invalid setup failure and cannot satisfy RED. If no genuine historical RED exists, report the TDD evidence blocker rather than fabricate it. | Run under this task after implementation; expect 200, both fixture clients, and response keys `cases` and `next_token`. |

## Files

| File | Planned change |
|---|---|
| `be-case-client/src/case_client_handler.py`, `case_client_repository.py`, `case_client_mock_repository.py`, `case_client_dynamodb_repository.py` | Implement and dispatch independent global listing with bounded Scan and pagination. |
| `be-case-client/tests/test_case_client_lambda.py`, `test_case_client_dynamodb_repository.py` | Cover handler/mock behavior and DynamoDB Scan/cursor boundaries. |
| `be-case-client/openapi-case-client.yaml`, `template.yaml`, `README.md` | Document and protect the fifth operation. |
| `be-case-client/tools/case_client_test_deploy.py`, `be-case-client/tests/integration/case_client_api_integration.py` | Extend existing route preflight and bounded live scenarios/evidence. |
| `be-case-client/tests/test_case_client_template.py`, `test_case_client_live_tools.py` | Update route and guard assertions where needed. |
| `plans/checkpoints/` task-scoped evidence | Preserve historical artifacts; add fresh GREEN/checkpoint/live report only through their supported workflows. |

## Progress

- [x] Read the original plan, task brief, checkpoint, proof artifact, and authoritative live contract.
- [x] Identify the missing deliverables and evidence constraints; no application changes made.
- [ ] Inspect current implementation and locate any genuine historical behavioral RED.
- [ ] Implement global route and offline coverage; capture valid evidence.
- [ ] Complete eligible live deployment/HTTP verification within the existing authorization and report findings.
