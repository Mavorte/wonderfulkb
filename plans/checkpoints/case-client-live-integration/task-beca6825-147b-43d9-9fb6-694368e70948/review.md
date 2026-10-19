# Review Report: task-beca6825-147b-43d9-9fb6-694368e70948

## What was implemented
Two component tools implement allowlisted Lambda deployment/rollback and a read-only-by-default HTTP integration runner, with private backups, redacted errors, revision checks, disabled redirects, bounded SDK calls, and a persistent write ledger. Offline guard tests and canonical RED/GREEN evidence accompany the tools. This is an independent interim review of the supplied source/evidence snapshot, not final live acceptance.

## Scope and evidence
- Reviewed only `be-case-client/tools/case_client_test_deploy.py`, `be-case-client/tests/integration/case_client_api_integration.py`, `be-case-client/tests/test_case_client_live_tools.py`, the specified sanitized `manifest.json`, and `plans/checkpoints/task-beca6825-147b-43d9-9fb6-694368e70948.red-green-proof.md`, against the specified authoritative plan.
- No git operations, AWS calls, credential/private-backup reads, code edits, or test executions were performed by this reviewer. The sole review output is this file.
- Canonical proof lines 5–75 record five behavioral assertion failures; lines 78–108 record 14 passing focused tests. The currently reviewed test file contains an additional usage-plan selection test (lines 169–187), so that test is not covered by this captured GREEN result.
- Manifest lines 5–8 and 34 record a blocked deploy/build action and zero deploy attempts. Lines 15–26 still describe the original Node.js runtime and absent Python backend bindings; lines 7–9, 30 and 33 show no cases, fixtures, or completed live scenarios. The original HTTP baseline is recorded as passing at line 29.
- Baseline 65 tests, SAM lint, and frontend gates were reported as passing by the caller; their independent outputs are outside this review's evidence scope. Missing `pip`, missing IAM `ConditionCheckItem`, and SCP-blocked role-user enumeration are caller-reported blockers. No IAM mutation is proposed by this review; the reviewed deploy tool contains none. Any future `uv` fallback requires review of the actual resulting change and build evidence.

## Goals met/unmet
- [MET] Fixed account/profile/region/function/URL checks, explicit write opt-in, private backup hashing/permissions, safe exception rendering, disabled HTTP redirects, and single-attempt POST transport are present.
- [MET] Normal successful Lambda update paths use revision preconditions, waiters, and hash readback; a detected foreign revision stops mutation.
- [MET] The supplied manifest truthfully remains BLOCKED rather than asserting deployment/live success.
- [UNMET] Reliable recovery at the end of the live time budget (finding R1).
- [UNMET] Artifact-bound and validation-complete live scenario evidence (R2 and R3).
- [UNMET] Task-wide accounting covering failed build/deploy attempts and their elapsed time (R4).
- [UNMET] Verified original-service recovery after rollback (R5).
- [UNMET] Successful Python artifact build/deployment, required live matrix, final hash/config readback, and final evidence re-review are not yet demonstrated.

## What's missing vs plan
The implementation still needs the guard/evidence corrections below and actual bounded deployment/live results before the plan's acceptance condition can be satisfied. The present build/access blockers are not evidence that deployment or rollback succeeded. No fix plan is created, per the caller's explicit restriction.

## Findings by severity

### P1 — Critical

#### R1 — The live deadline prevents the reserved rollback
- **File:** `be-case-client/tools/case_client_test_deploy.py:118–124,308–316`.
- **Issue:** Rollback calls the same `reserve()` function as forward work. Once `live_started_at` is 60 minutes old, `reserve()` raises before any restoration, even when the fifth deploy slot was deliberately left free. A failed live run at or beyond the cutoff therefore cannot use the supported rollback command to restore the original service.
- **Risk:** The task's mandatory stop-and-restore path can leave a nonfunctional Python replacement deployed precisely when forward debugging must stop.
- **Fix:** Stop forward work at the deadline while permitting one explicitly reserved, separately bounded recovery operation, retaining the total attempt cap, identity checks, and revision preconditions. Add an offline boundary test showing that expired forward work is denied but an owned-revision rollback can proceed within its reserved allowance.

### P2 — Important

#### R2 — Cached scenario passes are not bound to the deployed artifact
- **File:** `be-case-client/tests/integration/case_client_api_integration.py:106–108,315–323,350–355`; `be-case-client/tools/case_client_test_deploy.py:319–329`.
- **Issue:** Any scenario already marked `PASS` is skipped on later runner invocations. Deployment retains the same `scenarios` map, and the runner neither checks the current Lambda hash/revision nor associates scenario results with an artifact. Following an integration fix/redeploy, a write run can skip all prior scenarios and assign `live_matrix = 'PASS'` for a different implementation.
- **Risk:** Final hash readback could establish artifact B while the required behavior evidence actually belongs to artifact A. This is especially important for the planned build/deploy/test repair loop.
- **Fix:** Associate evidence with a verified artifact hash/revision and run identity; invalidate or explicitly mark stale scenario results after deployment. Preserve the task-wide budgets, fixtures, and POST ledger when refreshing evidence. Revalidate known objects without reposting, and report scenarios that cannot be newly demonstrated within the remaining budget as BLOCKED. Test a redeploy with preexisting PASS entries.

#### R3 — Resuming a recorded POST bypasses failed response validations
- **File:** `be-case-client/tests/integration/case_client_api_integration.py:189–194,217–225`.
- **Issue:** The runner persists `state='201'` and `case_id` before checking UUIDv4, caller-ID rejection, status, exact nested Decimal metadata, and immediate GET equality. If any of those assertions fails, the next invocation enters the existing-ID branch and returns a GET result without performing those checks. A previously failed create/detail scenario can consequently become PASS without the failing behavior being fixed or retested.
- **Risk:** Resumption converts incomplete/failed evidence into successful evidence, independently of the artifact-cache issue in R2. A later GET also cannot prove that the original GET was immediate.
- **Fix:** Persist response receipt separately from completed validation and reuse a common validator for recoverable checks. Keep failed or unobserved timing/creation assertions explicitly unresolved; do not claim that later GET recovery proves the original immediate-read requirement. Add an offline regression where a 201 response has incorrect UUID/metadata, then resume with its known ID and confirm the scenario cannot silently become PASS.

#### R4 — Build failures and build time escape task-wide accounting
- **File:** `be-case-client/tools/case_client_test_deploy.py:118–124,303–306,319–324`; `be-case-client/tests/integration/case_client_api_integration.py:321–329`; `manifest.json:5–8,29–35`.
- **Issue:** The deploy counter and `live_started_at` are first reserved only after `build()` returns. A failed build is reported as a blocked deploy action but consumes neither an attempt nor task time. Baseline HTTP work likewise does not initialize the task clock. The current manifest concretely shows a blocked deploy/build action with `deploy_attempts: 0` and no `live_started_at`.
- **Risk:** Repeated build/deploy attempts can exceed the plan's task-wide five-attempt/60-minute live-debugging boundary while counters still appear compliant.
- **Fix:** Persist the task clock before the first live phase and reserve the forward deploy attempt before invoking the build/deploy workflow, including failed attempts, while preserving the recovery slot. Check elapsed time again before mutation. Add coverage for a failing build consuming its reserved attempt and for baseline/build elapsed time reducing the remaining live allowance.

#### R5 — Rollback reports restoration without proving original service recovery
- **File:** `be-case-client/tools/case_client_test_deploy.py:276–278,308–317,339–342`; `be-case-client/tests/integration/case_client_api_integration.py:324–331`.
- **Issue:** Rollback verifies ZIP hash and update status, then records `restored-code-and-config` and prints PASS. It does not compare all restored configuration fields (including the full original environment) with the private snapshot, or run/record the original HTTP baseline against the restored service. The separate baseline option stores `original_http_baseline`, not rollback-specific recovery evidence. The current restore test checks call arguments and waiter count only (`test_case_client_live_tools.py:101–120`).
- **Risk:** A successful control-plane operation is reported as completed recovery even if the original API remains broken or the restored configuration differs. Plan implementation step 11 explicitly requires config readback and the original smoke to demonstrate restoration.
- **Fix:** Compare the restored runtime, handler, role, architecture, and environment with the private original snapshot without exposing environment values. Then run the bounded original auth/protected-GET smoke and record a separate rollback-verification result. If either verification is missing/fails, retain BLOCKED and describe recovery as unverified instead of completed. Cover config mismatch and failed recovery smoke offline.

### P3 — Minor
None raised; this review is limited to actionable P1/P2 findings.

## Goals unmet
- R1–R5 remain open in the reviewed snapshot.
- Build completion and a compatible deployable artifact are unproven.
- No successful Python deployment, required live matrix, or final artifact/config binding is demonstrated in the supplied manifest.
- Access blockers reported by the caller remain unresolved; withholding IAM mutation when role users cannot be enumerated is consistent with the plan.
- Final live evidence re-review is pending and must evaluate the actual resulting artifact, scenarios, gates, and any required recovery evidence.

## Verdict: NEEDS_FIX
