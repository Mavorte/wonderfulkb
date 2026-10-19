# Plan 2026-10-19: Case Client: deploy GET /cases and prove it over HTTP

Extend the existing deployment helper and integration runner, then verify the protected global route on the authorized AWS test endpoint with bounded writes and preserved recovery evidence.

## Analysis

- Existing backend handler/repositories already implement global GET `/cases`; the missing work is deployment-helper support, five-method preflight, and live runner scenarios.
- `be-case-client/tools/case_client_test_deploy.py` contains reusable Linux cp313/x86_64 build, snapshot, guarded Lambda update, revision check, ledger reservation, and private-write mechanisms. Add the narrow API Gateway GET method/integration/deployment operation there; no second deploy framework or IAM changes.
- `be-case-client/tests/integration/case_client_api_integration.py` is the existing HTTP runner. Its request accounting must cover every send, including auth negatives and pagination; retain in-memory API-key handling and fixture manifest.
- Existing guard tests: `be-case-client/tests/test_case_client_live_tools.py`; existing source/template coverage includes handler, DynamoDB repository, template, and API tests.
- Authoritative behavior and infrastructure constraints: `plans/checkpoints/case-client-list-all-live/authorized-contract-20261019.md`. Task-specific newer authorization sets ledger `case-global-72fa-20261019-1909/manifest.json`, 3 forward + 1 rollback, 60 minutes, 12 POST and 200 HTTP attempts, at most 2 requests/second and concurrency 2.
- Preserve historical proof and prior ledgers. The current task already has a RED proof at `be-case-client/plans/checkpoints/task-7700299e-f977-4acd-a1fe-b7409c3bca5d.red-green-proof.md`; inspect/extend through supported proof workflow without replacing its history.
- Relevant learnings: global Scan uses an independent route-bound cursor; live source success is not deployed evidence; budgets are task-wide and ambiguous POSTs must not be retried; previous proof collisions must not be hidden.

## Approach

1. Use the existing task proof and current guard tests to establish focused RED/GREEN for missing fifth-method and continuation-ledger behavior, preserving historical evidence.
2. Implement additive Gateway preflight and guarded mutation: locate `/cases`, verify absent GET and existing POST integration URI, snapshot and reserve before mutation, add `GET` with `NONE` authorization and `apiKeyRequired=true`, AWS_PROXY POST integration to the same Lambda URI, deploy stage `v1`, and read back. Roll back only this task's change under revision/concurrency protection.
3. Replace duplicate-key route mapping with an ordered five-method representation; test all four existing routes plus GET both before and after deployment (allow absence only in pre-deploy preflight).
4. Extend the existing transport/run/write-matrix/scenario flow to account for all HTTP attempts before send and exercise global limit=1 traversal, two-client fixture inclusion, no duplicate/lost IDs, malformed/foreign token 400, missing/invalid API key 403, and regressions for all four original operations including POST 201→GET and metadata.
5. Run offline gates, then bounded preflight/baseline, deploy with the exact authorized run ID, execute live HTTP scenarios, verify deployed Lambda hash/config and Gateway state, and save sanitized ledger/report/proof under `plans/checkpoints/`.

## Implementation

- Preserve existing API key, usage plan, throttling, Lambda role, tables, function configuration, four methods, and all historical evidence. No IAM/table/schema/secret/client additions.
- Before mutation, verify account `609394381050`, region `eu-central-1`, function `wonderfulkb-case-client`, API `bgm7k1ggqi`, stage `v1`, and snapshot recovery artifact. Use profile `ai-hackathon`; never expose credentials or API key.
- Use only fresh ledger `plans/checkpoints/case-client-list-all-live/case-global-72fa-20261019-1909/manifest.json`; account deployment cycles and every HTTP/POST attempt before effect. Stop on budget exhaustion, expiry, AccessDenied, or concurrent revision/state change.
- Reuse fixture manifest `plans/checkpoints/case-client-live-integration/host-case-live-20261019-1820/manifest.json`; no direct case writes or cleanup. Never replay an ambiguous POST.
- Implement TDD via `skill:tdd`; capture task-specific proof in root `plans/checkpoints/`, retaining the existing proof unchanged.
- Final sanitized evidence records Gateway deployment identity, ledger consumption, fixture IDs/results, request outcomes, and equal Lambda hash/config before and after the HTTP suite. Report any real authorization failure as a blocker.

## Testing

- Focused unit tests for continuation budget, Gateway pre/post-deploy route checks, five-method preservation, API Gateway add/readback/rollback guards, and shared HTTP accounting/scenarios.
- Run exact offline gates from repository root:
  - `/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m unittest discover -s be-case-client/tests -p 'test_*.py'`
  - `/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m compileall -q be-case-client/src be-case-client/tools be-case-client/tests`
  - `/Users/michal/.local/bin/sam validate --lint --template-file be-case-client/template.yaml`
  - Registered gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- After tool changes pass offline gates: deploy helper `preflight`; integration runner `--baseline`; deploy using `--allow-writes --run-id case-global-72fa-20261019-1909`; run HTTP integration using same run ID; finish with helper `verify`.
- Live acceptance requires complete global limit=1 traversal showing cases from both fixture clients without duplicates/loss, foreign/malformed token 400, missing/invalid key 403, and all original-operation regressions. Confirm Lambda hash/config unchanged across HTTP testing and Gateway GET readback.

## TDD

**Workflow:** Use `skill:tdd` to continue the existing task's accepted RED/GREEN evidence without replacing historical proof. First add or extend tests in `be-case-client/tests/test_case_client_live_tools.py`, then capture RED and GREEN to the task checkpoint under root `plans/checkpoints/`.

**Target file:** `be-case-client/tests/test_case_client_live_tools.py`  
**Framework:** `unittest`  
**Run command:** `cd be-case-client && /Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m unittest tests.test_case_client_live_tools`  
**Edit hint:** Extend `LiveToolGuards` with route-table and API Gateway mutation/readback tests; add helper/runner tests in existing test modules if separated by current structure.

```python
def test_preflight_accepts_missing_get_only_before_deploy(self):
    with patch.object(deploy, "gateway_methods", return_value={"POST"}):
        deploy.require_routes(deployed=False)
        with self.assertRaises(deploy.GuardError):
            deploy.require_routes(deployed=True)  # RED: GET is not yet recognized as a staged method

def test_route_checks_preserve_both_cases_methods(self):
    routes = deploy.required_routes()
    self.assertEqual([method for path, method in routes if path == "/cases"], ["POST", "GET"])  # RED: duplicate dict key loses POST
```

| Test | RED | GREEN |
|---|---|---|
| Preflight route state | Missing GET cannot be represented as permitted pre-deploy state and required post-deploy state | Missing GET accepted only before deployment; deployed verification requires GET and all prior routes |
| `/cases` method enumeration | Duplicate route key omits POST or GET | Both methods are independently checked |
| Gateway mutation safety | No guarded GET method/integration/stage deployment and readback | Snapshot/reservation precede mutation; AWS_PROXY/key requirement/readback and owned-change rollback are enforced |
| HTTP shared accounting | Some scenario requests can bypass budget reservation | Every request reserves before send; global and original regressions run under caps |

## Files

| Path | Change |
|---|---|
| `be-case-client/tools/case_client_test_deploy.py` | Fresh continuation ledger/limits, ordered five-method preflight, additive guarded Gateway GET/integration/stage deploy and readback/rollback. |
| `be-case-client/tests/integration/case_client_api_integration.py` | Shared attempt accounting and global pagination/auth/token scenarios within existing runner. |
| `be-case-client/tests/test_case_client_live_tools.py` | TDD and regression coverage for ledger and route/deployment guards. |
| Existing relevant integration/unit tests | Cover five methods, runner accounting, and acceptance assertions as needed. |
| `plans/checkpoints/case-client-list-all-live/case-global-72fa-20261019-1909/manifest.json` | Fresh task ledger and sanitized results; preserve counters and history. |
| `plans/checkpoints/` | Task-specific RED/GREEN proof and sanitized live evidence. |

## Progress

- [x] Read prior implementation plan, live authorization contract, relevant learnings, and existing task proof.
- [ ] Complete TDD and implement helper/runner extensions.
- [ ] Pass offline unit, compile, SAM, and registered backoffice gates.
- [ ] Perform guarded deployment and complete live HTTP acceptance within ledger limits.
- [ ] Verify deployed hashes/config and Gateway state; save sanitized evidence.

---
*Created: 2026-10-19*
*Status: DRAFT*
