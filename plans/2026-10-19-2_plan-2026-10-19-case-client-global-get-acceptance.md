# Plan 2026-10-19: Case Client global GET acceptance

Extend the existing live runner and deployment guard for the explicitly authorized continuation, then prove the additive protected route on the existing AWS test endpoint.

## Analysis

- Preserve parent implementation and proof `plans/checkpoints/task-a1411f1b-f478-44b1-a9d5-675afa9665ac.red-green-proof.md`.
- `be-case-client/tools/case_client_test_deploy.py` currently pins historical task/ledger constants and bounded deployment guards; `tests/test_case_client_live_tools.py` covers these guards.
- `be-case-client/tests/integration/case_client_api_integration.py` is the existing HTTP runner; extend it rather than adding an orchestrator.
- `plans/checkpoints/case-client-list-all-live/authorized-contract-20261019.md` defines global-list semantics and live scenarios. The revised task authorization supersedes its earlier numerical budgets and historical exhausted-ledger conditions.
- Fresh ledger: `plans/checkpoints/case-client-list-all-live/case-global-72fa-20261019-1909/manifest.json`; initialize counters at zero there only. Limits: 3 forward cycles + reserved rollback, 60 minutes, 12 POSTs, 200 HTTP requests, ≤2 req/s and ≤2 concurrent requests.
- Reuse four historical synthetic clients/cases; no new clients, direct case writes, edits or deletes. Preserve every historical artifact/outcome.
- Relevant learnings: protected-route tests must track additive routes; source and deployed state require separate evidence; keep live budgets/task ledger scoped; cursor length does not bound JSON nesting; use bounded Scan resume semantics.

## Approach

1. Adapt existing deployment/runner context resolution to allowlist this continuation and exact fresh-ledger limits without changing historical-context behavior.
2. Extend protected-route preflight additively for the fifth protected GET while retaining all original four route/auth assertions.
3. Extend the HTTP integration runner for global GET, bounded stable-dataset limit=1 traversal, cross-client fixture inclusion, cursor rejection, and missing/invalid-key behavior; keep all writes/accounting under existing safeguards.
4. Verify target/account/config read-only, create and verify private recovery snapshot, package Linux Python 3.13 x86_64 artifact, perform guarded deployment and only the allowed API Gateway method/stage change.
5. Capture deployed hash/config before and after HTTP suite; write sanitized results and independent acceptance evidence. Stop on current-ledger exhaustion, expiry, AccessDenied, or concurrency mismatch.

## Implementation

- Run a genuine focused RED for new continuation-context guard behavior, then implement and capture GREEN; retain all prior proof unchanged.
- Keep Lambda runtime, handler, role, bindings, tables/indexes, four existing Gateway methods, API key/usage plan and throttling intact. No IAM/schema/index/table changes or mock fallback.
- Before any live mutation verify STS/account/region and current state; protect mode-700/600 recovery artifacts outside versioned evidence and use RevisionId/concurrency guards.
- Reserve each deployment cycle and each HTTP/POST attempt before effect/send, including failed or ambiguous attempts. Never replay ambiguous POSTs or auto-renew budgets.
- Run global GET assertions using only sanitized synthetic IDs/counts; require both clients' known cases in the global response and complete bounded traversal without duplicate/lost IDs.
- Execute full original-operation regression within shared request/write budgets. If bounded traversal hits its cap, report BLOCKED nonzero rather than skip or unbounded scan.
- Run offline suite, compile checks, `sam validate --lint`, and registered `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` gate.
- Record exact target, authorization source, fresh accounting, fixtures, per-cycle substeps, outcomes, deployed hashes/config before/after, Gateway identity and safe recovery pointer in sanitized continuation evidence.

## Testing

- Focused: `python3 -m unittest be-case-client/tests/test_case_client_live_tools.py` (from repository root; adjust invocation to supported discovery form if package-path syntax is rejected).
- Full Python discovery in the existing component venv, compile all component Python, and run SAM lint validation.
- Live HTTP: existing integration runner only; exercise global public Case shape, at least two fixture clients, complete `limit=1` walk, malformed/foreign/client-scoped token rejection, 403 missing/invalid key, plus all original four-operation regressions.
- Verify identical deployed Lambda code hash/config before and after HTTP execution and inspect Gateway GET method/stage deployment readback.
- Run the registered backoffice tests/build gate. Completion additionally requires successful live report and independent acceptance.

## TDD

**Target:** `be-case-client/tests/test_case_client_live_tools.py`  
**Framework:** `unittest`  
**Run:** `cd be-case-client && /Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m unittest tests.test_case_client_live_tools`  
**Edit:** Add a focused continuation allowlist/ledger guard test beside the existing continuation budget tests. Parent endpoint behavior already has genuine RED/GREEN proof; do not recreate it.

```python
def test_authorized_continuation_uses_fresh_exact_limits(self):
    manifest = {'continuation_id': 'case-global-72fa-20261019-1909'}
    with patch.object(deploy, 'save_manifest'):
        deploy.reserve(manifest, 'post_attempts', 12)
    self.assertEqual(manifest['post_attempts'], 1)  # RED: continuation currently not recognized
```

| Assertion | RED | GREEN |
|---|---|---|
| Fresh continuation is recognized and reserves in its own ledger under exact configured limit | Rejects unknown continuation or applies historical limit | Accepts authorized continuation; over-limit reservation fails and old-context guards still pass |

Implement the focused TDD cycle using `skill:tdd`; capture fresh GREEN evidence without modifying previous proof.

## Files

| Path | Change |
|---|---|
| `be-case-client/tools/case_client_test_deploy.py` | Allowlist fresh continuation, ledger and exact cycle/time guards while preserving existing context behavior; narrow Gateway additive change/preflight support as needed. |
| `be-case-client/tests/integration/case_client_api_integration.py` | Add bounded global-list HTTP scenarios, request accounting, and sanitized assertions to existing runner. |
| `be-case-client/tests/test_case_client_live_tools.py` | RED/GREEN tests for new context/limits and additive preflight, retaining historical guards. |
| `plans/checkpoints/case-client-list-all-live/case-global-72fa-20261019-1909/manifest.json` | Fresh sanitized run ledger and completion evidence. |
| `plans/checkpoints/case-client-list-all-live/` | Store only related sanitized checkpoints/proof/report; preserve historical files. |

## Progress

- [x] Read authorization contract and identify existing runner, deploy guard, and offline guard tests.
- [ ] Implement focused RED/GREEN and runner/context extensions.
- [ ] Complete offline verification.
- [ ] Perform guarded in-place test deployment and live HTTP proof.
- [ ] Record sanitized evidence and obtain independent acceptance.
