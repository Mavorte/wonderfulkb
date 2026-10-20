# [acceptance-fix] Monitoring lifecycle: zachovat unscoped evidence a odmítnout rozporný ordinal fallback: goal-001: Monitoring lifecycle: zachovat unscoped evidence a odmítnout rozporný 

Auto-created by the monitor because the original task `task-59a2a44c-6136-465a-b2a7-2be7a6a6911a` was accepted as done
but did not fully meet all acceptance goals.

## Primary goals (from original task)

- goal-001: Monitoring lifecycle: zachovat unscoped evidence a odmítnout rozporný ordinal fallback

### [BLOCKING] finding-001 - implemented_behavior_incorrect / correctness

**Scope:** `goal-001`  
**Claim:** Legacy attempt_number must never act as an ordinal fallback when canonical attempt_no is absent.

**Observed**
The reducer still assigns number from attempt_number for a legacy-only AttemptStarted and also falls back to attempt_number for AttemptFinished when attempt_no is absent, allowing unsupported alias-only input to create a definite attempt summary.

**Why this matters**
The canonical task explicitly says the serializer does not emit attempt_number and forbids adding that alias fallback; accepting it can turn malformed/non-canonical evidence into a certain attempt identity instead of preserving uncertainty or rejecting it.

**Required action**
Remove the legacy-only ordinal fallback for AttemptStarted and AttemptFinished; only validated canonical attempt_no may establish a definite attempt number, while contradictory or malformed scope remains explicit uncertainty/evidence.

**Evidence**
- file: `be-document-processing/src/document_processing/audit/audit_lifecycle_observations.py:115-139`
- plan: `plans/tasks/2026-10-20_complete-lifecycle-unscoped-evidence-0923.md`


## Context

- Original task: `task-59a2a44c-6136-465a-b2a7-2be7a6a6911a`
- Reason: `acceptance_incomplete`
- The original task's code changes are preserved. Continue from that state.

## Instructions

Use the concrete goals and findings above to repair the untrustworthy task outcome. Make the minimum implementation and test changes needed, and verify the repaired behavior.

## Important: do not repeat completed work

The previous attempt partially succeeded. Review what is already committed before making changes. Do NOT revert or redo completed work. If the previous approach caused the failure, try a different approach.

## Original plan

Read the original plan at `/Users/michal/Projects/wonderfulkb/plans/2026-10-20_task-59a2a44c-6136-465a-b2a7-2be7a6a6911a_monitoring-lifecycle-zachovat-unscoped-evidence-a-odm-tnout.md` for full context. Focus only on the unmet goals listed above.

## Recent learnings from previous attempt


### 2026-10-20_run-proof-helpers-from-the-directory-that-determines-their-o.md

```
---
title: "Run proof helpers from the directory that determines their output path"
date: 2026-10-20
category: tooling
component: tooling
tags: [proof-artifacts, working-directory, acceptance]
file_type: rules
---

# Run proof helpers from the directory that determines their output path

The proof helper was launched from the backend subtree and wrote its artifact beneath that subtree, but acceptance required a monorepo-level `plans/checkpoints/...` path. A later root-level capture did not recreate the RED/GREEN proof because the tests already passed. Before running proof tooling, verify how i
```


### 2026-10-20_normalize-persisted-collections-to-match-frozen-event-types.md

```
---
title: "Normalize persisted collections to match frozen-event types"
date: 2026-10-20
category: architecture
component: backend
tags: [dynamodb, serialization, round-trip, events]
file_type: rules
---

# Normalize persisted collections to match frozen-event types

DynamoDB returned `artifact_ids` as a list, while the frozen event’s public value was a tuple, so round-trip equality failed. `PageCacheReused.from_item` now converts the persisted list back to a tuple. When adding persistence round-trip tests, check both values and types for collection fields, and normalize storage representatio
```


### 2026-10-20_import-nov-ho-routeru-ov-it-v-sestaven-m-image.md

```
---
title: "Import nového routeru ověřit v sestaveném image"
date: 2026-10-20
category: tooling
component: backend
tags: [docker, packaging, smoke-test]
file_type: rules
---

# Import nového routeru ověřit v sestaveném image

Dockerfile kopíroval aplikační soubory explicitně, takže nový `processing_monitor_lifecycle_routes.py` musel být přidán do `COPY`. Po sestavení image prošel smoke test importu `main`, routeru i audit package a potvrdil registraci tří routes. U nových modulů v takovém balení opakovat import test přímo v image; lokální testy samy neověří obsah výsledného artefaktu.

## Cont
```

## Implementation session log excerpt (last 50 lines)

```
m
Implemented the lifecycle evidence and identity handling changes.

- Retained `AttemptFinished` observations without `run_id` as unscoped evidence, without inventing a run or attempt.
- Prevented contradictory `AttemptStarted` ordinals from selecting an attempt.
- Preserved same-identity conflicting payload evidence across scope changes and input order; distinct event IDs and attempt numbers remain independent.
- Added focused tests and captured accepted RED/GREEN proof at `plans/checkpoints/task-59a2a44c-6136-465a-b2a7-2be7a6a6911a.red-green-proof.md`.

Verification passed: backend suite **209 passed**, backoffice tests **17 passed**, and backoffice build bundled **5 functions**. Saved a learning at `learnings/architecture/2026-10-20_bounded-lifecycle-reducer-identity-and-evidence.md`.

```

## TDD proof provenance for this acceptance fix

Do not create or fabricate a fake RED after the original implementation exists. Reuse and link the historical genuine RED from the parent or previous proof when applicable, then capture fresh GREEN verification under this follow-up task.
