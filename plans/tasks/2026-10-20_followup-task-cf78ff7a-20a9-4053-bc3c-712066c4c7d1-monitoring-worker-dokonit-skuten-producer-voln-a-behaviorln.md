# [acceptance-fix] Monitoring worker: dokončit skutečná producer volání a behaviorální důkaz: goal-001: Monitoring worker: dokončit skutečná producer volání a behaviorální dů

Auto-created by the monitor because the original task `task-d1fa9938-e6eb-4a39-90d1-c580b4e79ad0` was accepted as done
but did not fully meet all acceptance goals.

## Primary goals (from original task)

- goal-001: Monitoring worker: dokončit skutečná producer volání a behaviorální důkaz

### [BLOCKING] finding-001 - required_implementation_missing / correctness

**Scope:** `goal-001`  
**Claim:** The task requires actual worker caller instrumentation using authoritative execution context and a single injected fail-open audit listener.

**Observed**
The supplied checkpoint says implementation is blocked by the absent authoritative interface, the focused RED intentionally remains failing, and no GREEN or source producer change is claimed.

**Why this matters**
A blocker description and RED test do not deliver the required producer calls; the target goal therefore remains unimplemented rather than merely unverified.

**Required action**
Provide the authoritative execution-owner context interface, instrument the supported real worker callers without changing execution semantics, and deliver the required caller-level behavior.

**Evidence**
- file: `plans/tasks/2026-10-20_complete-worker-audit-integration-0908.md:9-12`
- file: `plans/tasks/2026-10-20_complete-worker-audit-integration-0908.md:23-29`
- artifact: `plans/checkpoints/task-d1fa9938-e6eb-4a39-90d1-c580b4e79ad0.checkpoint.md:5-11`

### [BLOCKING] finding-002 - required_tdd_proof_missing / evidence

**Scope:** `goal-001`  
**Claim:** The caller-declared mandatory TDD workflow requires a genuine RED-to-GREEN proof with the same focused command.

**Observed**
The supplied proof contains only a RED phase, and the checkpoint explicitly states that GREEN is unavailable and the focused test remains failing.

**Why this matters**
With tddRequired=true, a RED-only record is an incomplete mandatory TDD proof and cannot establish the required implemented behavior.

**Required action**
After the prerequisite interface exists and implementation is delivered, capture a valid GREEN phase using the same argv and retain the complete RED-to-GREEN proof.

**Evidence**
- file: `plans/tasks/2026-10-20_complete-worker-audit-integration-0908.md:12`
- file: `plans/tasks/2026-10-20_complete-worker-audit-integration-0908.md:34-35`
- artifact: `plans/checkpoints/task-d1fa9938-e6eb-4a39-90d1-c580b4e79ad0.red-green-proof.md:1-29`
- artifact: `plans/checkpoints/task-d1fa9938-e6eb-4a39-90d1-c580b4e79ad0.checkpoint.md:5-11`


## Context

- Original task: `task-d1fa9938-e6eb-4a39-90d1-c580b4e79ad0`
- Reason: `acceptance_incomplete`
- The original task's code changes are preserved. Continue from that state.

## Instructions

Use the concrete goals and findings above to repair the untrustworthy task outcome. Make the minimum implementation and test changes needed, and verify the repaired behavior.

## Important: do not repeat completed work

The previous attempt partially succeeded. Review what is already committed before making changes. Do NOT revert or redo completed work. If the previous approach caused the failure, try a different approach.

## Original plan

Read the original plan at `/Users/michal/Projects/wonderfulkb/plans/2026-10-20_task-d1fa9938-e6eb-4a39-90d1-c580b4e79ad0_monitoring-worker-dokon-it-skute-n-producer-vol-n-a.md` for full context. Focus only on the unmet goals listed above.

## Recent learnings from previous attempt


### task-a67c7b62-lifecycle-http-authorization-gate.md

```
---
title: "Lifecycle HTTP: fail-closed GREEN není doručená read funkcionalita"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, authorization, tdd, aws, app-runner]
file_type: rules
---

# Lifecycle HTTP: fail-closed GREEN není doručená read funkcionalita

V `be-intake/app/main.py` globální `x-api-key` pouze ověřuje volajícího služby; `require_case` ověřuje existenci case, ale neváže konkrétního volajícího na konkrétní case. Bounded audit reader `audit_queries.read_document` zná pouze case/document a cursor, nikoliv oprávnění. Route může bezpečně vrátit 403 s `
```


### 2026-10-20_page-cache-reused-artifact-roundtrip.md

```
---
title: "PageCacheReused artifact round trips"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, dynamodb, serialization, tdd]
---

# PageCacheReused artifact round trips

Audit event `artifact_ids` is normalized to a tuple on construction, but DynamoDB serializes it as a list. `PageCacheReused.from_item` must convert that list back to a tuple so read values preserve event equality. An assertion comparing the event directly to the persisted read result detects this contract mismatch; when a test also checks the persisted first-write item, compare the normalized event 
```


### 2026-10-20_bounded-lifecycle-reducer-identity-and-evidence.md

```
---
title: "Bounded lifecycle reducer identity and evidence"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, lifecycle, evidence, identity]
---

# Bounded lifecycle reducer identity rules

Attempt terminal observations without `run_id` can be retained as unscoped evidence without fabricating a run or attempt summary. For `AttemptStarted`, validate supplied canonical and compatibility ordinal fields together: a disagreement is uncertainty, and must not allow a legacy value to select a different attempt. Keep distinct event identities and distinct attempt ordinals indepe
```

## Implementation session log excerpt (last 50 lines)

```
authoritative execution context. Adding producers now would require inventing identity or changing execution semantics, so I made no production changes.

The focused test and genuine RED proof are saved at `be-validator-agent/trigger/tests/test_audit_instrumentation.py` and `plans/checkpoints/task-d1fa9938-e6eb-4a39-90d1-c580b4e79ad0.red-green-proof.md`. The proof has no GREEN phase because the required interface is absent; the test remains failing for that reason.

**Verification:** pipeline tests passed (31); the backoffice tests passed (17) and build bundled 5 functions. `git diff --check` passed. The RED condition is the documented blocker, not an unrelated test failure. I saved the learning to `learnings/architecture/worker-audit-producers-require-owner-issued-execution-identity.md`.

```

## TDD proof provenance for this acceptance fix

Do not create or fabricate a fake RED after the original implementation exists. Reuse and link the historical genuine RED from the parent or previous proof when applicable, then capture fresh GREEN verification under this follow-up task.
