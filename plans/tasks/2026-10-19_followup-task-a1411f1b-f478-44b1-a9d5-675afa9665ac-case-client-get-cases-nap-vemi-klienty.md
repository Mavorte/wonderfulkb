# [acceptance-fix] Case Client: GET /cases napříč všemi klienty: goal-001: Case Client: GET /cases napříč všemi klienty

Auto-created by the monitor because the original task `task-c88015bb-6b27-4a9b-916a-d22bb8308f57` was accepted as done
but did not fully meet all acceptance goals.

## Primary goals (from original task)

- goal-001: Case Client: GET /cases napříč všemi klienty

### [BLOCKING] finding-001 - required_implementation_missing / correctness

**Scope:** `goal-001`  
**Claim:** The global GET /cases implementation and required live-cycle deliverables must be delivered.

**Observed**
The task-scoped diff adds only test_global_cases_route_returns_shared_public_list; it contains no handler dispatch, repository list_cases implementation, DynamoDB Scan path, API/template/documentation/tooling changes, deployment result, or live HTTP verification required by the task.

**Why this matters**
A test that expects the new route does not implement the route. The checkpoint explicitly states implementation, broader coverage, deployment, and live verification remain untouched.

**Required action**
Implement the required global GET /cases behavior across the existing handler and repositories, update the protected API contract and existing tooling, and complete the authorized deployment and live HTTP verification.

**Evidence**
- file: `be-case-client/tests/test_case_client_lambda.py:67-76`
- artifact: `plans/checkpoints/task-c88015bb-6b27-4a9b-916a-d22bb8308f57.checkpoint.md`

### [BLOCKING] finding-002 - required_tdd_proof_missing / evidence

**Scope:** `goal-001`  
**Claim:** The caller-required TDD proof must contain a genuine behavior-driven RED followed by GREEN.

**Observed**
The supplied proof contains only a RED phase whose failure is ModuleNotFoundError for simplejson during test setup; it has no GREEN phase, and the supplied proof projection explicitly reports missing GREEN and incomplete phase order.

**Why this matters**
An environment dependency import failure does not demonstrate the newly added GET /cases expectation failing for the intended behavioral reason, and no subsequent passing phase proves the implementation.

**Required action**
Provide valid task-scoped RED/GREEN provenance with RED failing on the absent global GET /cases behavior and GREEN passing after implementation.

**Evidence**
- artifact: `plans/checkpoints/task-c88015bb-6b27-4a9b-916a-d22bb8308f57.red-green-proof.md`
- artifact: `plans/checkpoints/task-c88015bb-6b27-4a9b-916a-d22bb8308f57.checkpoint.md`

### [BLOCKING] finding-003 - verification_evidence_missing / evidence

**Scope:** `goal-001`  
**Claim:** The task requires sanitized live HTTP evidence and a verified deployment hash for the newly deployed Case Client.

**Observed**
No task-scoped live report or verified deployment hash is supplied; the checkpoint marks the authorized deployment and live HTTP verification incomplete. The canonical Test Gate passed, but it does not supply the explicitly required deployed-runtime evidence.

**Why this matters**
The task states that local green does not replace the live result and requires the existing HTTP runner to demonstrate global fixtures, pagination, API-key protection, and regressions against the deployed version.

**Required action**
Complete the authorized in-place deployment and preserve the sanitized live HTTP report and verified deployment hash covering the required scenarios.

**Evidence**
- artifact: `plans/checkpoints/task-c88015bb-6b27-4a9b-916a-d22bb8308f57.checkpoint.md`
- test-gate: `/Users/michal/.openclaw/workspace/km-system/state/test-gates/task-c88015bb-6b27-4a9b-916a-d22bb8308f57-orphan-implementing.json`
- file: `plans/tasks/2026-10-19_case-client-list-all-cases.md`


## Context

- Original task: `task-c88015bb-6b27-4a9b-916a-d22bb8308f57`
- Reason: `acceptance_incomplete`
- The original task's code changes are preserved. Continue from that state.

## Instructions

Use the concrete goals and findings above to repair the untrustworthy task outcome. Make the minimum implementation and test changes needed, and verify the repaired behavior.

## Important: do not repeat completed work

The previous attempt partially succeeded. Review what is already committed before making changes. Do NOT revert or redo completed work. If the previous approach caused the failure, try a different approach.

## Original plan

Read the original plan at `/Users/michal/Projects/wonderfulkb/plans/2026-10-19_task-c88015bb-6b27-4a9b-916a-d22bb8308f57_case-client-get-cases-nap-v-emi-klienty.md` for full context. Focus only on the unmet goals listed above.

## Implementation session log excerpt (last 50 lines)

```
N proof and run broader verification
[ ] Complete approved deployment and live HTTP verification
[ ] Read proof artifact and save learnings
[0m
Zablokoval jsem implementaci před produkčními změnami, protože povinný TDD RED důkaz není platný: první zachycené selhání bylo `ModuleNotFoundError: simplejson`, nikoli očekávané selhání GET `/cases`. Po instalaci závislostí helper odmítl RED zachytit znovu, protože už důkazní soubor existuje.

Přidal jsem zamýšlený test do `be-case-client/tests/test_case_client_lambda.py` a zaznamenal blokaci do `plans/checkpoints/task-c88015bb-6b27-4a9b-916a-d22bb8308f57.checkpoint.md`. Produkční kód jsem neupravil a nenasazoval. Důkazní soubor jsem nepřepisoval ani nemažu; potřebuji pokyn vlastníka úkolu k obnově TDD důkazu, než bude možné bezpečně pokračovat.

```

## TDD proof provenance for this acceptance fix

Do not create or fabricate a fake RED after the original implementation exists. Reuse and link the historical genuine RED from the parent or previous proof when applicable, then capture fresh GREEN verification under this follow-up task.
