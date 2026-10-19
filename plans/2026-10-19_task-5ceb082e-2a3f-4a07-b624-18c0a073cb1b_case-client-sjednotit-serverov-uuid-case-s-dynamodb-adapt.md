# Plan 2026-10-19: Case Client server-generated UUID across DynamoDB

Implement and document the server-assigned UUIDv4 create contract across the existing mock and DynamoDB adapter while preserving client validation, strong reads, serialization, and fail-closed behavior.

## Analysis

- Current `be-case-client/src/case_client_handler.py` requires caller `case_id`; both repositories implement replay/owner-conflict semantics. DynamoDB already conditionally inserts and recovers cancellation with a strong read.
- Remote read-only inputs are `plans/handoffs/case-client-remote-20261019/`, pinned by `manifest.json` to `88c04ee6e850c147ffeba46fe626bb0acd4863f3`. Merge their intended changes by normal edits; do not replace current adapter or OpenAPI wholesale.
- Preserve current OpenAPI 1.4.0 `CaseDetails` expansion. Record its meaning for create/read as a separate unresolved question; do not implement additional detail behavior.
- Relevant prior findings: `learnings/architecture/decisions-case-client-backend-static-invariants.md` (retain mock-only no-SDK guarantee and test both SAM policy branches); `learnings/runtime-errors/rules-case-client-dynamodb-decimal-range.md` (preserve Decimal boundaries and Stubber proof); `learnings/architecture/2026-10-19_in-memory-lambda-mocks-provide-only-execution-environment-lo.md` (mock state is execution-environment-local, not durable).
- Preserve actual DynamoDB implementation, its strong `GetItem`, atomic active-client `ConditionCheck` plus conditional `Put`, least-privilege IAM, error mapping, metadata handling, and GET-by-returned-ID.
- Scope: `be-case-client/**`; only manifest-listed incoming documentation paths outside it (README/docs/plans); repo-local plan/evidence. Handoff snapshots remain read-only. No other application code, frontend, credentials, network, AWS, deploy, or live test.

## Approach

- Generate UUIDv4 server-side for every POST; ignore supplied `case_id` whether absent, valid, invalid, or repeated. Return 201 on every successful create; remove public replay-200 and caller-ID owner-conflict behavior.
- Validate `client_id` and metadata before persistence. Missing client stays 404; inactive/blocked stays 409; malformed request stays 400.
- DynamoDB: for each generated ID, perform one `TransactWriteItems` containing active-client conditional check and `attribute_not_exists(case_id)` put. On a case-key condition collision, strongly read that generated key; never return or overwrite its owner’s case. Retry with a fresh UUID at most three total generated IDs, checking client status on each transactional attempt; after three collisions return sanitized 500. Other transaction failures remain operational 5xx and are not retried. Tests must pin the exact cancellation reason interpretation and read sequence.
- Update mock with the same generated-ID/new-create semantics, under its existing lock. Keep its ephemeral execution-environment boundary explicit.
- Integrate all manifest-listed README/docs/plans content selectively; reconcile the stale deployed-version note in `docs/quick-connect.md` by retaining it as a dated deployment-status caveat, not as evidence about this source implementation.

## Implementation

1. Add failing handler/mock tests for omitted ID, supplied ID ignored (including repeated same ID), distinct UUIDv4 values and 201 responses; retain invalid client/metadata and client-state cases.
2. Change shared repository protocol, request parsing, handler status flow, mock create, DynamoDB create and fixtures/events to accept only client plus metadata and generate UUIDs in the server boundary.
3. Add Stubber-backed real-handler/DynamoDB tests for exact transaction request, persisted and returned UUID, strong GET after creation, active-client enforcement, and deterministic collision retries/exhaustion without returning or overwriting existing rows. Preserve existing Decimal, no-network/no-DNS, and failure-sanitization tests.
4. Migrate existing old-contract tests rather than deleting coverage. Assert public GET reads returned UUID and verify SAM policy still grants only necessary conditional DynamoDB actions in DB mode and no DB rights in mock mode.
5. Reconcile OpenAPI 1.4.0, request event, component README, tests README, and only the other manifest-listed documentation files. Keep CaseDetails expansion and log its separate ambiguity without broadening behavior.
6. Run full Python 3.13 unittest suite, `compileall`, SAM lint, and registered gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`. Report frontend toolchain failures as-is; do not bypass. Preserve sanitized command/output evidence and obtain independent semantic acceptance. Do not claim deployed/runtime success.

## Testing

- Focused RED/GREEN tests run offline with fake credentials, disabled metadata lookup, and socket/DNS blocked; botocore Stubber must consume every expected SDK call.
- Full suite: `python3 -m unittest discover -s be-case-client/tests -p 'test_*.py' -v` (run under Python 3.13).
- Syntax: `python3 -m compileall -q be-case-client/src be-case-client/tests`.
- Template: `sam validate --lint --template-file be-case-client/template.yaml` with only offline placeholder environment if required by SAM.
- Registered gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- Inspect diff scope against `be-case-client/**` plus exact incoming manifest-listed README/docs/plans paths; verify handoff manifest hashes remain unchanged and no snapshot was edited.

## TDD

Implement the test-first RED/GREEN cycle using `skill:tdd`; save proof to `plans/checkpoints/task-5ceb082e-2a3f-4a07-b624-18c0a073cb1b.red-green-proof.md`.

Test file: `be-case-client/tests/test_case_client_lambda.py`  
Framework: `unittest` (existing handler integration tests)  
Run command: `PYTHONPATH=be-case-client/src python3 -m unittest discover -s be-case-client/tests -p 'test_case_client_lambda.py' -v`  
Edit hint: add the test method to `CaseClientLambdaTests`.

```python
def test_post_generates_new_uuid_and_ignores_supplied_case_id(self):
    body = {'client_id': ACTIVE, 'case_id': 'caller-controlled', 'metadata': {}}
    first = self.invoke('POST', '/cases', body=body, expected=201)
    second = self.invoke('POST', '/cases', body=body, expected=201)
    self.assertNotEqual(first['case_id'], second['case_id'])  # RED: current handler returns 400/reuses caller ID
    for result in (first, second):
        parsed = UUID(result['case_id'])
        self.assertEqual(parsed.version, 4)
        self.assertEqual(result['status'], 'open')
```

| Test | RED before implementation | GREEN after implementation |
|---|---|---|
| POST without `case_id` and with repeated supplied ID | Current request parser rejects omitted ID; caller ID is persisted | Both POSTs return 201 with distinct server UUIDv4 IDs, regardless of body ID |
| DynamoDB conditional collision | Existing replay path may return a key occupant | Strong read detects generated-key collision; fresh UUID attempt; no occupant returned/overwritten; bounded exhaustion is sanitized 500 |
| Existing invalid/inactive/missing client and metadata cases | Existing tests provide regression baseline | Preserve 400/409/404 semantics and exact transaction guard |

## Files

| Path | Planned change |
|---|---|
| `be-case-client/src/case_client_handler.py` | Parse client/metadata without requiring or validating caller case ID; use created-only 201 response. |
| `be-case-client/src/case_client_repository.py` | Update repository create protocol to generated-ID interface; retain shared metadata and client rules. |
| `be-case-client/src/case_client_mock_repository.py` | Generate UUIDv4 and create a new case per call under lock. |
| `be-case-client/src/case_client_dynamodb_repository.py` | Generate UUIDv4, conditional atomic insert, safe bounded collision recovery. |
| `be-case-client/tests/test_case_client_lambda.py` | Replace old replay assertions with public contract and validation regression coverage. |
| `be-case-client/tests/test_case_client_dynamodb_repository.py` | Stub exact create transaction, generated ID/readback, collision, and client validation. |
| `be-case-client/tests/test_case_client_template.py` | Preserve and verify least-privilege DB/mock policy branch assertions. |
| `be-case-client/events/create-case.json` | Demonstrate request without caller case ID. |
| `be-case-client/openapi-case-client.yaml` | Keep 1.4.0 details, align POST request, response, and server-generated UUID behavior. |
| `be-case-client/README.md`, `be-case-client/src/README.md`, `be-case-client/tests/README.md` | Document source contract, adapter/mock behavior, and offline proof limits. |
| Manifest-listed `README.md` / `docs/quick-connect.md` / `plans/*.md` paths | Selectively integrate incoming material, preserving dated deployed-state caveat and documenting CaseDetails ambiguity; do not edit other incoming paths unless their content requires harmonization within the stated exact manifest scope. |

## Progress

- [x] Canonical plan path obtained with required `plan-path.py` command.
- [x] Relevant source, read-only remote references, manifest, and prior learnings inspected.
- [x] Implementation and verification plan drafted; no application implementation performed.
