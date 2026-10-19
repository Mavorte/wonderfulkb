# Plan 2026-10-19: Case Client: GET /cases napříč všemi klienty

## Analysis

- `case_client_handler.py` currently routes `/cases` only to POST; `_query` already validates default 50 and range 1–100. `CASE_FIELDS`/`_public_case` define public projection.
- Both repositories expose `list_client_cases`; DynamoDB `_list('cases', ...)` performs client `GetItem` plus per-client GSI Query, so global listing needs a distinct list path.
- DynamoDB pagination already binds tokens to fingerprints and resumes mid-SDK page with key fields; global fingerprint/cursor must be distinct and keyed by `case_id`, with bounded Scan/time budget and no client reads.
- Existing component deploy and HTTP runner are `be-case-client/tools/case_client_test_deploy.py` and `tests/integration/case_client_api_integration.py`; extend them. The existing API preflight/template tests assume four routes and must be advanced to five protected methods.
- API documentation is `openapi-case-client.yaml`; SAM route is `template.yaml`; README documents the old four-operation contract.
- Live-cycle authority and limits: `plans/checkpoints/case-client-list-all-live/authorized-contract-20261019.md`, specifically its “Výslovně autorizovaný deploy a live integrační cyklus” section. Inspect existing live ledger and current target read-only before using any budget; preserve fixtures and history, never retry ambiguous POSTs.

## Approach

- Add an explicit global `list_cases(filters, limit, token)` repository operation. For mock, use independent `global-cases` token identity and `case_id` cursor without sorting guarantee. For DynamoDB, reuse cursor/budget helpers where safe but use Scan on the cases table only, route-bound fingerprint, `case_id` cursor, bounded pages and correct mid-page continuation.
- Route GET `/cases` to the new method, return 200 with public Case projection and `next_token`, and never attach `client_id` or look up clients. Preserve POST `/cases` and all existing operations.
- Document the GET operation and add the API-key-protected SAM route. Do not alter schema, indexes, IAM, or introduce a second deploy/test tool.
- Extend existing static/live tooling and report with global fixture inclusion, limit-1 full paging without duplicates/loss, malformed/foreign token 400, API-key 403, and regression scenarios. Keep live requests/writes, deploy attempts, deadlines and recovery within the authorized contract and existing ledger; preserve verified artifact/hash and sanitized evidence.

## Implementation

1. Before TDD, inspect canonical task proof path, current approved live ledger/fixtures/budgets and deploy target through existing read-only preflight; verify usable local Python/test tooling. Do not mutate cloud state or spend live budget during planning.
2. Use skill `tdd`: add the focused handler+mock RED test first, capture genuine RED, then implement mock/repository protocol/handler and expand handler tests for two clients, empty list, limit-1 continuation, foreign token, and allowlisted public fields.
3. Add handler+DynamoDB Stubber coverage for two clients, empty table, default/boundary limits, cross-page and mid-SDK-page resume, invalid token before SDK calls, bounded budget/error sanitization, exact Scan table/start key and absence of clients GetItem/per-client Query. Preserve existing operation regressions.
4. Update OpenAPI version and GET `/cases` contract, SAM GET event/API-key protection, README and an event example if useful; update template and deploy preflight tests to require all five methods while retaining original method/auth/integration checks.
5. Extend the existing integration runner to verify global synthetic cases across two clients, complete limit-1 paging, malformed/route-bound cursor rejection, key protection and original-operation regression. Use only authorized existing fixtures and remaining task-wide budgets; no full-table dump, no new orchestrator, no ambiguous POST replay.
6. Run focused TDD tests, full offline unittest command, compile/lint and registered gates. Then, only in implementation after review gates, perform the authorized in-place build/deploy/HTTP repair cycle with revision guards, snapshot/recovery, exact deployed hash/config readback and sanitized report. Stop and report BLOCKED on auth/permission/budget/capability failures; local green is not live proof.

## Testing

- Focused RED/GREEN test: handler GET `/cases` returns 200 and the shared cases for two fixture clients; empty list returns `cases: []`; limit 1 walks all cases exactly once; unrelated/foreign token returns 400.
- Stubber: assert Scan uses only `CASES_TABLE_NAME`; continuation key resumes within a returned SDK page; no client-table read or cases GSI Query; invalid token triggers no SDK call; sanitized Scan failures remain 500, not empty success.
- Preserve regression suite and test OpenAPI/template route and API-key protection. Required command from repository root: `PYTHONPATH=be-case-client/src python3 -m unittest discover -s be-case-client/tests -p 'test_*.py'`.
- Live evidence must demonstrate new deployed artifact hash/config before and after HTTP suite, global synthetic fixtures and pagination, API-key enforcement, and existing operation regressions. Follow the authorized contract for account/region, fixture and POST budget, HTTP attempt/rate/deadline caps, rollback and manifest; do not treat previous blocked evidence as green or overwrite it. Registered full gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.

## TDD

Implement the TDD cycle using skill:tdd. Check `plans/checkpoints/task-c88015bb-6b27-4a9b-916a-d22bb8308f57.red-green-proof.md` before creating evidence; preserve any existing proof and do not count earlier evidence as this change's RED/GREEN.

**Test file:** `be-case-client/tests/test_case_client_lambda.py`  
**Framework:** `unittest`, already used for the real handler plus in-memory mock adapter.  
**Run command:** `PYTHONPATH=be-case-client/src:be-case-client/tests python3 -m unittest test_case_client_lambda.CaseClientLambdaTests.test_global_cases_route_returns_shared_public_list`  
**Edit hint:** Append to `CaseClientLambdaTests`; RED is the currently unsupported GET method on `/cases`.

```python
    def test_global_cases_route_returns_shared_public_list(self):
        response = self.handler({
            'httpMethod': 'GET', 'resource': '/cases', 'path': '/cases',
            'queryStringParameters': None,
        }, None)
        self.assertEqual(response['statusCode'], 200)
        data = json.loads(response['body'])
        self.assertEqual(set(data), {'cases', 'next_token'})
        self.assertGreaterEqual({case['client_id'] for case in data['cases']}, {ACTIVE, OTHER})
```

| Test | RED | GREEN |
|---|---|---|
| `test_global_cases_route_returns_shared_public_list` | Existing `/cases` GET returns 405 (or the response lacks the required global list). | Status 200 includes public cases for both clients and exactly `cases`/`next_token` response keys. |

## Files

| File | Change |
|---|---|
| `be-case-client/src/case_client_repository.py` | Declare global list operation in protocol. |
| `be-case-client/src/case_client_handler.py` | Dispatch GET `/cases`, validate list query and project public cases. |
| `be-case-client/src/case_client_mock_repository.py` | Implement globally scoped mock paging with independent cursor identity. |
| `be-case-client/src/case_client_dynamodb_repository.py` | Add bounded cases-table Scan and global fingerprint/case_id resume cursor. |
| `be-case-client/tests/test_case_client_lambda.py` | TDD skeleton and global route/mock pagination/projection tests. |
| `be-case-client/tests/test_case_client_dynamodb_repository.py` | Stubber tests for Scan, no client access, pagination, malformed tokens and operational errors. |
| `be-case-client/openapi-case-client.yaml` | Add protected global GET `/cases` contract and response; update version. |
| `be-case-client/template.yaml` | Add GET `/cases` Api event and update route metadata without IAM/schema changes. |
| `be-case-client/README.md` | Document fifth operation and global Scan/page semantics. |
| `be-case-client/tools/case_client_test_deploy.py` | Extend existing protected-route preflight and bounded deploy evidence compatibly. |
| `be-case-client/tests/integration/case_client_api_integration.py` | Add bounded live global list/paging/auth/regression scenarios. |
| `be-case-client/tests/test_case_client_template.py`, `be-case-client/tests/test_case_client_live_tools.py` | Update route assertions and test deploy/live guards. |
| `be-case-client/events/list-cases.json` | Optional packaged request example for new route, if examples remain covered as a project convention. |

## Progress

- [x] Canonical plan path created before writing.
- [x] Inspected current handler/repository/tests/docs, live tooling and authorized contract read-only.
- [x] Loaded relevant Case Client learnings; local-search fallback used because QMD collection was unavailable.
- [x] Finalized implementation approach and runnable TDD skeleton.
