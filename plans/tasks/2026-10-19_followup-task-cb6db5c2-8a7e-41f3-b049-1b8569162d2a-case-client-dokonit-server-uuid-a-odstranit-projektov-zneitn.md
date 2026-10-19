# [acceptance-fix] Case Client: dokončit server UUID a odstranit projektové znečištění acceptance diffu: goal-001: Case Client: dokončit server UUID a odstranit projektové znečištění ac

Auto-created by the monitor because the original task `task-74486347-28bc-4131-b2c6-a05b334cec00` was accepted as done
but did not fully meet all acceptance goals.

## Primary goals (from original task)

- goal-001: Case Client: dokončit server UUID a odstranit projektové znečištění acceptance diffu

### [BLOCKING] finding-001 - implemented_behavior_incorrect / correctness

**Scope:** `goal-001`  
**Claim:** Collision retries must use up to three distinct server-generated UUID candidates before exhaustion.

**Observed**
Both DynamoDBCaseClientRepository.create_case and MockCaseClientRepository.create_case count each uuid4() result as an attempt without rejecting a duplicate candidate, so repeated generator output can retry the same occupied key three times and raise allocation failure after only one distinct candidate.

**Why this matters**
The caller-supplied plan explicitly specifies at most three distinct generated IDs. Counting duplicate candidates as separate collision attempts violates that strategy and can fail a create that should proceed to another candidate; the supplied tests cover three different IDs but not duplicate generator output.

**Required action**
Track generated candidates so collision retries operate on distinct UUIDs, while preserving a bounded fail-closed strategy, and cover duplicate generator output in both adapter behaviors.

**Evidence**
- file: `be-case-client/src/case_client_dynamodb_repository.py:269-302`
- file: `be-case-client/src/case_client_mock_repository.py:72-79`
- plan: `plans/2026-10-19_task-74486347-28bc-4131-b2c6-a05b334cec00_case-client-dokon-it-server-uuid-a-odstranit-projektov-zne.md:Approach`


## Context

- Original task: `task-74486347-28bc-4131-b2c6-a05b334cec00`
- Reason: `acceptance_incomplete`
- The original task's code changes are preserved. Continue from that state.

## Instructions

Use the concrete goals and findings above to repair the untrustworthy task outcome. Make the minimum implementation and test changes needed, and verify the repaired behavior.

## Important: do not repeat completed work

The previous attempt partially succeeded. Review what is already committed before making changes. Do NOT revert or redo completed work. If the previous approach caused the failure, try a different approach.

## Original plan

Read the original plan at `/Users/michal/Projects/wonderfulkb/plans/2026-10-19_task-74486347-28bc-4131-b2c6-a05b334cec00_case-client-dokon-it-server-uuid-a-odstranit-projektov-zne.md` for full context. Focus only on the unmet goals listed above.

## Recent learnings from previous attempt


### 2026-10-19_case-client-server-generated-uuid-collision-contract.md

```
---
title: "Case Client: server-generated UUID and bounded collision recovery"
date: 2026-10-19
category: architecture
component: backend
tags: [case-client, uuid, dynamodb, stubber, gitignore]
file_type: rules
---

# Server-generated case UUIDs with conditional DynamoDB inserts

For create-only APIs, caller-provided IDs should not silently reintroduce replay semantics. Ignore `case_id` in the POST payload and keep the repository create contract limited to the validated owner and metadata; each adapter generates a fresh UUIDv4 and the HTTP layer consistently returns `201`.

In DynamoDB, valida
```

## Implementation session log excerpt (last 50 lines)

```
r-generated-uuid-collision-contract.md`.

**Verification:** all 50 Case Client unittests passed; `compileall`, offline SAM lint, and all 5 backoffice tests passed. The backoffice build could not resolve the local `esbuild` package. An isolated fixture confirmed the existing root `.gitignore` covers the required generated paths and leaves source and evidence paths visible; it was preserved unchanged. All 28 handoff snapshots retained their manifest hashes.

Changed source paths: `be-case-client/README.md`, `be-case-client/events/create-case.json`, the four `be-case-client/src` modules, and the two Case Client test files; added `docs/quick-connect.md`, the task checkpoint and proof, and the learning. Unrelated untracked `opencode.json` and prior acceptance-run artifacts were left untouched.

```

## TDD proof provenance for this acceptance fix

Do not create or fabricate a fake RED after the original implementation exists. Reuse and link the historical genuine RED from the parent or previous proof when applicable, then capture fresh GREEN verification under this follow-up task.
