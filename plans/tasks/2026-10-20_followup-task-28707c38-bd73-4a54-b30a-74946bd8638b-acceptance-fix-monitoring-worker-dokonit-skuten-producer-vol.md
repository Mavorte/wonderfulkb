# [acceptance-fix] [acceptance-fix] Monitoring worker: dokončit skutečná producer volání a behaviorální důkaz: goal-001: Monitoring worker:: goal-001: [acceptance-fix] Monitoring worker: dokončit skutečná producer volání 

Auto-created by the monitor because the original task `task-cf78ff7a-20a9-4053-bc3c-712066c4c7d1` was accepted as done
but did not fully meet all acceptance goals.

## Primary goals (from original task)

- goal-001: [acceptance-fix] Monitoring worker: dokončit skutečná producer volání a behaviorální důkaz: goal-001: Monitoring worker:

### [BLOCKING] finding-001 - required_implementation_missing / correctness

**Scope:** `goal-001`  
**Claim:** The acceptance fix requires actual supported worker producer calls using authoritative execution context and a single injected fail-open audit listener.

**Observed**
The task checkpoint says the authoritative owner-issued context contract remains absent, Step 4 is blocked, and no production changes were made; the supplied diff adds only an introspection test for an execution_context parameter and contains no worker caller instrumentation.

**Why this matters**
A documented prerequisite blocker and a failing signature assertion do not deliver the required real producer behavior, context forwarding, or caller-level fail-open integration.

**Required action**
Supply the approved execution-owner context contract, instrument the supported real worker callers without changing queue, claim, retry, lease, or business semantics, and provide behavioral caller evidence for successful and unsuccessful claims plus failing audit sinks.

**Evidence**
- file: `plans/tasks/2026-10-20_followup-task-cf78ff7a-20a9-4053-bc3c-712066c4c7d1-monitoring-worker-dokonit-skuten-producer-voln-a-behaviorln.md:8-35`
- artifact: `plans/checkpoints/task-cf78ff7a-20a9-4053-bc3c-712066c4c7d1.checkpoint.md:2-10`
- file: `be-validator-agent/trigger/tests/test_audit_instrumentation.py:1-8`

### [BLOCKING] finding-002 - required_tdd_proof_missing / evidence

**Scope:** `goal-001`  
**Claim:** The caller-declared mandatory TDD workflow requires a valid historical RED and fresh same-command GREEN proof for the repaired behavior.

**Observed**
The supplied TDD projection is explicitly incomplete: it contains only the parent RED command with exit code 1 and no GREEN phase; the task checkpoint confirms that GREEN capture was unavailable and the focused test remains unimplemented.

**Why this matters**
With tddRequired=true, a RED-only record cannot establish the completed acceptance-fix behavior even though the caller-owned Test Gate passed.

**Required action**
After implementing the required worker producer behavior, retain the genuine parent RED provenance and capture a fresh GREEN phase with the exact same focused command in a complete task-scoped proof.

**Evidence**
- artifact: `plans/checkpoints/task-d1fa9938-e6eb-4a39-90d1-c580b4e79ad0.red-green-proof.md:1-29`
- artifact: `plans/checkpoints/task-cf78ff7a-20a9-4053-bc3c-712066c4c7d1.checkpoint.md:5-10`
- test-gate: `/Users/michal/.openclaw/workspace/km-system/state/test-gates/task-cf78ff7a-20a9-4053-bc3c-712066c4c7d1-orphan-implementing.json`


## Context

- Original task: `task-cf78ff7a-20a9-4053-bc3c-712066c4c7d1`
- Reason: `acceptance_incomplete`
- The original task's code changes are preserved. Continue from that state.

## Instructions

Use the concrete goals and findings above to repair the untrustworthy task outcome. Make the minimum implementation and test changes needed, and verify the repaired behavior.

## Important: do not repeat completed work

The previous attempt partially succeeded. Review what is already committed before making changes. Do NOT revert or redo completed work. If the previous approach caused the failure, try a different approach.

## Original plan

Read the original plan at `/Users/michal/Projects/wonderfulkb/plans/2026-10-20_task-cf78ff7a-20a9-4053-bc3c-712066c4c7d1_monitoring-worker-dokon-it-skute-n-producer-vol-n-a.md` for full context. Focus only on the unmet goals listed above.

## Recent learnings from previous attempt


### 2026-10-20_document-events-denial-red-needs-owner-policy.md

```
---
title: "Acceptance repair: document-events RED musí rozlišit policy od chybějící route"
date: 2026-10-20
category: test-failures
component: backend
tags: [monitoring, authorization, tdd, acceptance]
file_type: rules
---

# Acceptance repair: distinguish absent route RED from denied-case policy

For WonderfulKB document-events planning, the existing `be-intake/tests/test_processing_monitor_routes.py` sketch asserts 200 with only `x-api-key`, lacks the explicit import of `intake` from `test_monitor_file_received`, and omits the contract-required `coverage: partial`. A fixture setup error can
```


### 2026-10-20_lifecycle-reducer-canonical-attempt-ordinals.md

```
---
title: "Lifecycle reducer requires canonical attempt ordinals"
date: 2026-10-20
category: architecture
component: backend
tags: [lifecycle, audit, canonical-identity, tests]
file_type: rules
---

# Canonical attempt ordinals only

The lifecycle reducer must not treat `attempt_number` or `attempt_id` as an ordinal. Only a positive integer `attempt_no` can group attempt observations. Tests that characterize supported attempt grouping should therefore use `attempt_no`; alias-only events should remain without a definite attempt summary.

When changing this contract, update older fixture events
```


### audit-characterization-no-false-red.md

```
---
title: "Audit characterization must not manufacture RED"
date: 2026-10-20
category: test-failures
component: backend
tags: [tdd, audit, monitoring, proof]
file_type: rules
---

# Validating audit event matrices without falsifying TDD evidence

For test-only characterization tasks where the existing implementation already satisfies every new assertion, the proof-capture helper correctly rejects a passing RED and will not start GREEN without a task-scoped RED. Preserve the parent task's genuine failing output as provenance, then report the incompatibility honestly; do not introduce an intent
```

## Implementation session log excerpt (last 50 lines)

```
quired by the authoritative plan.** The checked-in enqueue path has no stable run identity or typed send outcome; the claim path assigns no run ID or attempt ordinal; and canonical deployed build provenance is unestablished. Adding producer calls or context forwarding now would invent execution semantics.

I preserved the parent task’s genuine RED proof and made no production changes. The required task-scoped RED/GREEN proof could not be completed: the TDD helper rejected GREEN because this task has no RED phase. I did not fabricate proof or claim behavioral completion. The checkpoint records the blocker.

**Verification:** backoffice tests passed (17); build bundled 5 functions. The learning was saved to `learnings/architecture/2026-10-20_worker-audit-integration-owner-identity-gate.md`.

```

## TDD proof provenance for this acceptance fix

Do not create or fabricate a fake RED after the original implementation exists. Reuse and link the historical genuine RED from the parent or previous proof when applicable, then capture fresh GREEN verification under this follow-up task.
