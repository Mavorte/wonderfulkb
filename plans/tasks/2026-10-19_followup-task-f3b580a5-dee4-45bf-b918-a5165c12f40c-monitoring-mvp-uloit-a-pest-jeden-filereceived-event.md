# [acceptance-fix] Monitoring MVP: uložit a přečíst jeden FileReceived event: goal-001: Monitoring MVP: uložit a přečíst jeden FileReceived event

Auto-created by the monitor because the original task `task-b6ff9adf-d61b-4db0-b1ec-881674700f7f` was accepted as done
but did not fully meet all acceptance goals.

## Primary goals (from original task)

- goal-001: Monitoring MVP: uložit a přečíst jeden FileReceived event

### [BLOCKING] finding-001 - required_implementation_missing / correctness

**Scope:** `goal-001`  
**Claim:** The task requires a working FileReceived audit envelope, idempotent store, bounded document Query with scope-bound continuation, explicit disabled configuration, finite SDK timeout, and required audit table/IAM configuration.

**Observed**
The complete supplied diff adds only be-document-processing/tests/test_monitor_audit_storage.py for the product slice; it does not add audit_events.py, audit_storage.py, audit_queries.py, or any existing-template audit resource/IAM/configuration change. The checkpoint also states implementation step 4 is not completed.

**Why this matters**
The test imports an audit API that is not delivered, and the required persistence/read behavior and infrastructure therefore cannot exist in the supplied implementation.

**Required action**
Implement the narrowly scoped audit modules and required existing-template configuration so FileReceived can be conditionally stored and read via bounded, document-scoped Query with scope-bound continuation, disabled-store behavior, and finite SDK timeout.

**Evidence**
- file: `be-document-processing/tests/test_monitor_audit_storage.py:6`
- artifact: `plans/checkpoints/task-b6ff9adf-d61b-4db0-b1ec-881674700f7f.checkpoint.md:7`
- plan: `plans/tasks/2026-10-19_monitor-mvp-01-file-received-store.md`

### [BLOCKING] finding-002 - required_tdd_proof_missing / evidence

**Scope:** `goal-001`  
**Claim:** The caller requires valid RED then GREEN TDD proof for this task.

**Observed**
The supplied proof contains only a RED command that exited while loading conftest because pymupdf was missing; the proof projection says GREEN is missing and phase order is incomplete, and the checkpoint says the recorded RED is not a genuine implementation failure.

**Why this matters**
An environment import failure is not the expected behavioral RED, and no GREEN phase was captured, so the mandatory TDD proof is invalid and incomplete.

**Required action**
Provide genuine expected RED evidence followed by GREEN evidence for the focused audit-store behavior, captured under the caller-owned TDD workflow.

**Evidence**
- artifact: `plans/checkpoints/task-b6ff9adf-d61b-4db0-b1ec-881674700f7f.red-green-proof.md:7`
- artifact: `plans/checkpoints/task-b6ff9adf-d61b-4db0-b1ec-881674700f7f.checkpoint.md:5`


## Context

- Original task: `task-b6ff9adf-d61b-4db0-b1ec-881674700f7f`
- Reason: `acceptance_incomplete`
- The original task's code changes are preserved. Continue from that state.

## Instructions

Use the concrete goals and findings above to repair the untrustworthy task outcome. Make the minimum implementation and test changes needed, and verify the repaired behavior.

## Important: do not repeat completed work

The previous attempt partially succeeded. Review what is already committed before making changes. Do NOT revert or redo completed work. If the previous approach caused the failure, try a different approach.

## Original plan

Read the original plan at `/Users/michal/Projects/wonderfulkb/plans/2026-10-19_task-b6ff9adf-d61b-4db0-b1ec-881674700f7f_monitoring-mvp-ulo-it-a-p-e-st-jeden-filereceived-event.md` for full context. Focus only on the unmet goals listed above.

## Recent learnings from previous attempt


### focused-pytest-capture-environment-blockers.md

```
---
title: "Focused pytest capture environment blockers"
date: 2026-10-20
category: test-failures
component: backend
tags: [pytest, tdd, dependencies, proof-capture]
---

# Focused pytest captures and environment failures

For `be-document-processing`, the repository test `conftest.py` imports PyMuPDF before any test module runs. A focused test can therefore fail at collection with a missing dependency, which is not a valid implementation RED. Inspect the captured stderr and require the expected missing-API assertion before production edits.

This environment also has a configured package inde
```

## Implementation session log excerpt (last 50 lines)

```
arnings/test-failures/focused-pytest-capture-environment-blockers.md
[0m
Implementation is blocked before production changes. The focused tests are in `be-document-processing/tests/test_monitor_audit_storage.py`, but pytest fails while loading `conftest.py` because `pymupdf` is missing. Installing dependencies also failed: the configured package index does not provide the pinned `fastapi==0.147.0`.

The capture helper accepted that setup failure as RED, but it is **not** the expected implementation failure. I recorded the blocker in `plans/checkpoints/task-b6ff9adf-d61b-4db0-b1ec-881674700f7f.checkpoint.md` and saved the learning at `learnings/test-failures/focused-pytest-capture-environment-blockers.md`. No production code was changed, and GREEN or broader verification could not be run.

```

## TDD proof provenance for this acceptance fix

Do not create or fabricate a fake RED after the original implementation exists. Reuse and link the historical genuine RED from the parent or previous proof when applicable, then capture fresh GREEN verification under this follow-up task.
