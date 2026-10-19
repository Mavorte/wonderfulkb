# Plan: Case Client guarded GET /cases acceptance repair

## Analysis
- Preserve the existing handler/repository/OpenAPI/SAM global-list implementation. Extend only the deployment helper, HTTP runner and focused tests; retain unrelated working-tree changes. Use `git diff` and committed history as the baseline; Git lifecycle remains host-owned.
- Replace `case_client_test_deploy.py:193`'s duplicate-key dictionary: it omits POST `/cases`. Add the absent Gateway mutation flow; `preflight()` currently demands GET before deployment can create it.
- Extend `case_client_api_integration.py`: `Transport` currently lacks a manifest, `write_matrix()` would seed new clients, and no global HTTP scenarios exist. Reuse its secret handling, Decimal decoder, pagination, rate limiter and regression assertions.
- Preserve the inspected ledger `plans/checkpoints/case-client-list-all-live/case-global-72fa-20261019-1909/manifest.json`: counters are currently 0/0/0, stored `task_id` is `task-72fa674d-3c01-4e53-b5f7-cc12a1be4615`, and the helper's `TASK` is `task-7700299e-f977-4acd-a1fe-b7409c3bca5d`. Record this lineage and the current follow-up additively; do not normalize IDs or create a replacement ledger.
- Apply `plans/checkpoints/case-client-list-all-live/authorized-contract-20261019.md` with the newer limits in `plans/tasks/2026-10-19_case-client-deploy-global-get-and-test.md`: 3 forward cycles + 1 recovery, 60 minutes from first mutation, 12 POST attempts, 200 HTTP attempts, concurrency ≤2 and rate ≤2/s, cumulatively across retries.
- Reuse the four created clients and known cases in `plans/checkpoints/case-client-live-integration/host-case-live-20261019-1820/manifest.json`; retain its different fixture `run_id`. Import references/read-only fixture data, never its old budget, deadline, PASS flags or Node.js recovery snapshot.
- Apply recalled rules from `learnings/architecture/2026-10-19_case-client-live-tools-evidence-and-task-wide-budgets.md` and `2026-10-19_case-client-global-scan-cursor-and-live-evidence.md`: prove deployed hashes and route-bound cursors; never retry an ambiguous POST. Recall used local fallback, collection `wonderfulkb-learnings`, diagnostic `Collection not found`; use the supplied corrected cwd diagnosis over the older `learnings/tooling/tdd-proof-cycle-validation.md` explanation.
- Use `be-case-client/openapi-case-client.yaml` and the authorization contract for response/security assertions; preserve global Scan's unordered, non-snapshot semantics and client-list newest-first behavior. No PlantUML files were found; no architecture/schema change is required.

## Approach
1. Implement the functional changes test-first using `skill:tdd` with this follow-up's own proof; keep all parent/root/component proofs intact.
2. Reuse the current helper for snapshot/build/Lambda revision guards and add a narrow Gateway flow; reuse the runner for bounded HTTP proof and original-operation regression.
3. Complete offline gates, guarded deployment and live acceptance against the existing authorized target; finalize only with matching artifact/readback evidence and complete scenario results.

## Implementation
1. Before production edits, extend `be-case-client/tests/test_case_client_live_tools.py` per the TDD section. Replace missing-symbol errors in unfinished tests with explicit seam assertions, then test actual AWS/request behavior using mocks or Stubber under the existing socket/DNS deny; do not reduce their assertions to obtain GREEN.
2. Add `required_routes()` returning ordered pairs: `('/clients','GET')`, `('/cases','POST')`, `('/cases','GET')`, `('/cases/{case_id}','GET')`, `('/clients/{client_id}/cases','GET')`. Pass session/client and `deployed` state explicitly through route validation. Check all original four independently; tolerate only a genuine missing GET before deployment, never AccessDenied, missing POST, bad auth or wrong integration. Require all five after deployment and in `verify`.
3. Validate the exact continuation/run ID, target and ledger before writes; preserve counters/deadline/history and initialize missing collections without replacing existing data. Add append-only follow-up provenance and attempt/scenario records. Serialize ledger reservations and saves across worker threads/process invocations; no resetting counters or trusting stale PASS caches. Bind reusable results to artifact, Gateway deployment and runner revision; archive previous results instead of clearing them.
4. Verify account `609394381050`, region `eu-central-1`, profile `ai-hackathon`, Lambda `wonderfulkb-case-client`, role `wonderfulkb-lambda-role`, REST API `bgm7k1ggqi`, stage `v1`, and existing table/index bindings. Use `skill:aws-sdk-python-usage` when editing boto3 code; prefer official AWS MCP for AWS inspection/readback and no AWS CLI. Keep the task-authorized Python helper as the deployment path; do not introduce a second deployment framework.
5. Snapshot the current Lambda ZIP/hash/full config/env and Gateway `/cases` methods, integration URI, stage deployment ID/settings, original four methods and API method fingerprint privately (directory 0700/files 0600). Verify the downloaded ZIP hash and snapshot ownership before mutation; do not silently reuse an older private pointer/snapshot. Reuse `build()` for Linux cp313/x86_64 and `apply_update()`/waiters/env merge with `RevisionId` checks.
6. Reserve one forward deployment-cycle attempt before its first Lambda/Gateway mutation; keep the fourth slot for recovery. Locate the existing `/cases` resource and verified POST integration URI. If GET is absent, call `put_method(restApiId=API, resourceId=..., httpMethod='GET', authorizationType='NONE', apiKeyRequired=True)` then `put_integration(..., httpMethod='GET', type='AWS_PROXY', integrationHttpMethod='POST', uri=verified_post_uri)`. A pre-existing correct GET is preserved; a conflicting GET stops the flow. Persist intent/owned effects after each operation, including partial failures.
7. Re-read Lambda revision, original methods, API fingerprint and stage immediately before Gateway publication; stop on foreign drift. Publish through `create_deployment(restApiId=API, stageName='v1')`, save returned deployment ID, then require `get_stage` to reference it and `get_method`/`get_integration` to prove all five methods. Preserve usage plan, API keys, throttling, stage settings, Lambda policy, IAM and tables. Read-compare/readback guards are not atomic API Gateway revision locks; retain exclusive task execution and stop on any detected race.
8. Extend recovery for partial/complete Gateway changes: use the reserved recovery cycle, restore the snapshot stage deployment only while it still points to this task's deployment, and delete only GET created by this task whose fingerprint still matches. Re-read before each recovery mutation; never delete a pre-existing GET or overwrite a foreign change. Restore Lambda with the snapshot revision/hash/config guards and verify original-operation HTTP smoke; preserve failed/ambiguous evidence even after recovery. For timeout ambiguity inspect owned state before any further mutation, not a blind retry.
9. Make `Transport(..., manifest=m)` share one reservation/locking path for every send, including baseline, missing/wrong-key requests, polling, pages, expected errors and concurrent POSTs. Persist HTTP and POST reservations before sending; move POST counting out of individual callers to avoid double charging and bypasses. Retain request labels/ambiguous states, limiter recheck after sleep, ≤20s bounded timeout, no redirects and no retries. HTTP baseline must not start the 60-minute mutation clock; preserve an existing mutation start and check it on all later requests.
10. Replace fixture creation in this continuation with read-only validation of the referenced fixture manifest; no `PutItem`/new clients or direct case writes. Search by actual source-fixture names/ICO rather than the new run ID; include pre-existing fixture case IDs in per-client expectations. Give new POSTs stable labels scoped to the shared continuation, not the artifact hash, so redeployment cannot replay them. Missing fixtures or an ambiguous prior POST return nonzero BLOCKED.
11. Extend `run`/`write_matrix`/`scenario` with global auth, validation, pagination and cross-route token tests. Finish all permitted writes before traversing the stable test dataset; require fixture cases from both active clients, unique IDs and complete traversal to null token. Compare fixture-scoped IDs/objects against the verified fixture inventory and client-scoped lists; process other response objects in memory without storing real-case dumps or claiming snapshot guarantees.
12. Run the Testing sequence and repair in-scope failures within remaining limits. Stop on authentication failure, AccessDenied, expiry, exhausted budget or concurrent change; use guarded recovery when owned changes make the service unhealthy. Do not mark a partial/offline-only result complete.
13. Save a sanitized live report at `plans/checkpoints/task-28c88643-682f-4fa4-873f-aeebc8701a1b.live-report.md`, referencing the shared ledger and own TDD proof. Include timestamp/target, artifact SHA256/CodeSha256, pre/post HTTP Lambda config/revision/hash, Gateway deployment/readback, fixture provenance/IDs, scenario status/counts, cumulative budgets/deadline, errors/iterations and recovery outcome. Keep keys, tokens, presigned URLs and raw private config out of evidence. Finish implementation with `skill:validate-implementation` and `skill:save-learning`; save at least one learning.

## TDD
- Implementace TDD cyklu dle `skill:tdd`; append tests to `LiveToolGuards` in `be-case-client/tests/test_case_client_live_tools.py`, using its real imports and denied sockets. The historical identity-only parent GREEN is not functional proof.
- Start with the executable skeleton below inside that existing class; extend the remaining tests before RED to cover the behavior table. `inspect` is a local standard-library import; existing `deploy`, `api`, `Mock`, `patch` and `URLError` imports are reused.

```python
    def test_required_routes_preserve_five_methods(self):
        self.assertTrue(callable(getattr(deploy, 'required_routes', None)),
                        'missing ordered five-route contract')
        self.assertEqual(deploy.required_routes(), [
            ('/clients', 'GET'), ('/cases', 'POST'), ('/cases', 'GET'),
            ('/cases/{case_id}', 'GET'),
            ('/clients/{client_id}/cases', 'GET')])

    def test_http_reservation_is_durable_before_ambiguous_send(self):
        import inspect
        self.assertIn('manifest', inspect.signature(api.Transport).parameters,
                      'transport must accept the shared ledger')
        m = {'continuation_id': 'case-global-72fa-20261019-1909',
             'http_requests': 0, 'post_attempts': 0}
        http = api.Transport('fake-key', manifest=m)
        opener = Mock()
        with patch.object(deploy, 'save_manifest') as saved_deploy, \
             patch.object(api, 'save_manifest') as saved_api, \
             patch.object(api, 'build_opener', return_value=opener):
            def ambiguous_send(*args, **kwargs):
                self.assertEqual(m['http_requests'], 1)
                self.assertEqual(m['post_attempts'], 1)
                self.assertGreater(saved_deploy.call_count + saved_api.call_count, 0)
                raise URLError('offline ambiguous response')
            opener.open.side_effect = ambiguous_send
            with self.assertRaises(URLError):
                http.request('POST', '/cases', body={'client_id': 'synthetic'})
        opener.open.assert_called_once()
```

| Focused behavior | RED before implementation | GREEN contract |
|---|---|---|
| Ordered five methods and pre/post preflight | Missing seam/duplicate mapping; GET absence blocks preflight | All four originals always checked; only absent GET allowed before deploy; wrong POST/auth/URI rejected |
| Gateway mutation and readback | No additive deployment path | Exact `put_method` → `put_integration` → `create_deployment`; snapshot/reservation precede effects; five-method/stage readback matches |
| Gateway failure/recovery/concurrency | No owned partial-state recovery | Stub failures at each boundary; reject drift, retain partial intent; restore only owned stage/GET and reserve recovery once |
| Shared HTTP/POST accounting | Transport lacks manifest and durable reservations | Counts already saved at send, including 403/400/baseline/paging; 200 HTTP or 12 POST prevents send; race at final slot cannot overspend |
| Deadline/continuation/fixtures | Baseline could start clock; runner may seed/replay | Clock begins at first mutation; cumulative counters survive retries; imported fixtures never written; ambiguous POST/redeploy never replayed |
| Global HTTP scenario assertions | No global runner behavior | Fake pages include both clients; missing fixture, duplicate/lost ID, repeated token or budget exhaustion fails; assert auth/token calls and terminal token |
| Original-operation regression | Old runner expectations omit imported cases | Preserve create201/detail/Decimal, ignored caller ID/distinct UUIDs, rejected clients, client filters and newest-first pages |

- Use own canonical proof `plans/checkpoints/task-28c88643-682f-4fa4-873f-aeebc8701a1b.red-green-proof.md`; none was present at planning. If one exists at implementation start, read it: resume its valid RED or use `red --start-new-cycle` only after a complete own cycle. Never copy or edit historical proofs.
- Execute each capture with explicit root cwd, never from `be-case-client`; verify `accepted_red` plus failing child before production edits, then `accepted_green` plus child exit 0 with identical argv:

```sh
cd /Users/michal/Projects/wonderfulkb && TASK_ID=task-28c88643-682f-4fa4-873f-aeebc8701a1b python3 /Users/michal/.config/opencode/skills/tdd/scripts/proof-capture.py red -- /Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m unittest discover -s be-case-client/tests -p test_case_client_live_tools.py
cd /Users/michal/Projects/wonderfulkb && TASK_ID=task-28c88643-682f-4fa4-873f-aeebc8701a1b python3 /Users/michal/.config/opencode/skills/tdd/scripts/proof-capture.py green -- /Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m unittest discover -s be-case-client/tests -p test_case_client_live_tools.py
```

- For proof diagnostics use `proof-capture.py read --task-id <own-id> --run-id <actual-run-id> --stream stdout --offset 0 --limit 4096` from the same explicit root cwd. Preserve `.tdd-test-runs` metadata and all rejected attempts; do not synthesize a RED for behavior already implemented.

## Testing
- After focused GREEN, run the exact offline gates from repository root and retain real output; investigate failures without relabeling older evidence:

```sh
/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m unittest discover -s be-case-client/tests -p 'test_*.py'
/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m compileall -q be-case-client/src be-case-client/tools be-case-client/tests
/Users/michal/.local/bin/sam validate --lint --template-file be-case-client/template.yaml
npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build
```

- Execute the existing helper/runner in this order only after the functional guards pass. Each command runs from root with `PY=/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python`; these are future implementation commands, not planning actions:

```sh
"$PY" be-case-client/tools/case_client_test_deploy.py preflight
"$PY" be-case-client/tests/integration/case_client_api_integration.py --baseline
"$PY" be-case-client/tools/case_client_test_deploy.py deploy --allow-writes --run-id case-global-72fa-20261019-1909
"$PY" be-case-client/tests/integration/case_client_api_integration.py --allow-writes --run-id case-global-72fa-20261019-1909
"$PY" be-case-client/tools/case_client_test_deploy.py verify
```

- Require global `GET /cases?limit=1` traversal without `client_id`, finishing within the shared 200 HTTP cap, with both fixture clients' expected cases, no duplicate/lost fixture IDs, public Case fields and Decimal metadata. Empty intermediate pages with tokens must continue; no global newest-first assertion or new unsupported filter.
- Require malformed token 400, client/clients token → global 400, global token → client route 400, global token with changed limit 400, and missing/invalid API key on GET `/cases` →403. Never persist opaque tokens; report scenario outcomes only.
- Require all four original operations: GET `/clients` filters/paging; POST `/cases` 201 with new UUIDs/ignored caller ID and immediate detail GET/metadata; unknown404/inactive409/blocked409; GET `/clients/{id}/cases` stable pagination/newest-first including imported fixture cases. Every poll/negative request consumes the same HTTP budget, each POST also consumes the POST budget.
- Read back Gateway stage deployment and all five method integrations after HTTP, compare preserved original methods/settings, and verify local build CodeSha256 equals Lambda before/after suite with unchanged runtime/handler/role/architecture/bindings/revision. Report nonzero BLOCKED for missing fixtures, truncated traversal, denied access or inconclusive readback; no skip counts as PASS.

## Files
| Path | Planned change |
|---|---|
| `be-case-client/tools/case_client_test_deploy.py` | Ordered routes, pre/post validation, additive guarded Gateway deploy/recovery, cumulative ledger/provenance and accurate status text |
| `be-case-client/tests/integration/case_client_api_integration.py` | Shared durable accounting, imported fixture reuse, stable POST labels, global HTTP scenarios and original regressions |
| `be-case-client/tests/test_case_client_live_tools.py` | Functional RED/GREEN tests for deployment, recovery, runner, concurrency and scenario assertions |
| `plans/checkpoints/case-client-list-all-live/case-global-72fa-20261019-1909/manifest.json` | Append continuation provenance, counters and versioned attempt/results; retain historical fields/outcomes |
| `plans/checkpoints/task-28c88643-682f-4fa4-873f-aeebc8701a1b.red-green-proof.md` | Helper-generated own-task proof, with supported cycle archives if needed |
| `plans/checkpoints/task-28c88643-682f-4fa4-873f-aeebc8701a1b.live-report.md` | Sanitized actual deployed/HTTP acceptance evidence mapped to findings 001–004 |

## Progress
- [x] Read original plan, authorization, source/diff, fixture/shared ledgers, proof history and relevant learnings.
- [x] Specify follow-up-specific TDD, functional helper/runner repairs and bounded live verification.
- [ ] Capture functional RED, implement minimal helper/runner changes and capture matching GREEN.
- [ ] Pass offline gates; perform guarded deployment and complete live HTTP suite within remaining shared limits.
- [ ] Verify actual artifact/Gateway state, save evidence and implementation learning; only then mark delivery complete.
