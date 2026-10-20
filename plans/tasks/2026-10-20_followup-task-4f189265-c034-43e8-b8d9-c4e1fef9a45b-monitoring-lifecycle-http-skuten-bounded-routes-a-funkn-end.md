# [acceptance-fix] Monitoring lifecycle HTTP: skutečné bounded routes a funkční end-to-end ověření: goal-001: Monitoring lifecycle HTTP: skutečné bounded routes a funkční end-to-en

Auto-created by the monitor because the original task `task-a67c7b62-949e-4720-b1a2-51fcc3502cec` was accepted as done
but did not fully meet all acceptance goals.

## Primary goals (from original task)

- goal-001: Monitoring lifecycle HTTP: skutečné bounded routes a funkční end-to-end ověření

### [BLOCKING] finding-001 - required_implementation_missing / correctness

**Scope:** `goal-001`  
**Claim:** The lifecycle runs, run-detail, and document-audit routes must return authorized bounded lifecycle observations through the canonical reader and reducer.

**Observed**
The supplied route module registers all three paths but every handler unconditionally returns 403; the task evidence explicitly labels SOURCE partial and states that no authorized lifecycle 200 endpoint or promised bounded observations exist.

**Why this matters**
Fail-closed denial is appropriate while the trusted authorization seam is absent, but it does not deliver the goal's functional bounded HTTP routes, operation-scoped continuation, reducer output, read-error handling, or publication observations.

**Required action**
Integrate the trusted caller-to-case and document-scope authorization seam, perform one bounded audit read per request, map the canonical lifecycle reducer into the required partial responses for all three routes, and preserve operation-bound cursors, no-store errors, and 503 behavior.

**Evidence**
- file: `be-intake/app/processing_monitor_lifecycle_routes.py:17-32`
- artifact: `plans/monitoring/task-a67c7b62-949e-4720-b1a2-51fcc3502cec-lifecycle-http-evidence.md:5-15`
- artifact: `plans/checkpoints/task-a67c7b62-949e-4720-b1a2-51fcc3502cec.checkpoint.md:3-12`

### [BLOCKING] finding-002 - verification_evidence_missing / evidence

**Scope:** `goal-001`  
**Claim:** The task explicitly requires guarded deployment to the existing AWS test target and direct authenticated live HTTP verification of the changed lifecycle behavior, with artifact and revision provenance.

**Observed**
The supplied evidence states DEPLOYED no and LIVE-FUNCTION-VERIFIED no, with no cloud HTTP calls, no synthetic fixture IDs, no target revision or recovery artifact, and no verified deployment workflow; only a local Docker image was built.

**Why this matters**
Local image import and TestClient denial do not satisfy the task's mandatory runtime acceptance, and no canonical Test Gate evidence exists to supply that missing deployment/live proof.

**Required action**
After functional routes and trusted authorization exist, record the guarded in-place deployment, source-to-image digest, target and resulting revision, recovery artifact/config, authorized synthetic fixture ledger, and bounded direct HTTP assertions for the changed routes including scope/auth/no-store behavior.

**Evidence**
- artifact: `plans/monitoring/task-a67c7b62-949e-4720-b1a2-51fcc3502cec-lifecycle-http-evidence.md:3-15`
- artifact: `plans/checkpoints/task-a67c7b62-949e-4720-b1a2-51fcc3502cec.checkpoint.md:7-12`
- plan: `plans/tasks/2026-10-20_complete-lifecycle-http-routes-0908.md:mandatory-deployment-and-live-verification`

### [BLOCKING] finding-003 - required_tdd_proof_missing / evidence

**Scope:** `goal-001`  
**Claim:** Because TDD is caller-required, the RED/GREEN proof must exercise the task's functional bounded lifecycle HTTP behavior rather than only route registration and fail-closed denial.

**Observed**
The supplied proof uses identical RED/GREEN argv and is structurally credible, but its sole GREEN test asserts that each route returns 403 and contains no runs; the task evidence expressly says this GREEN proves denial only and that no functional 200 route exists.

**Why this matters**
The proof validates a safe blocker boundary, not the required authorized runs, run-detail, and audit responses, bounded reader/reducer semantics, continuation, or error mappings. Therefore the mandatory TDD proof for the evaluation goal remains absent.

**Required action**
Capture a genuine task-scoped RED and GREEN with identical focused argv for the implemented authorized bounded lifecycle responses and required cursor/read-error semantics, preserving the existing denial proof as historical evidence.

**Evidence**
- artifact: `plans/checkpoints/task-a67c7b62-949e-4720-b1a2-51fcc3502cec.red-green-proof.md:1-78`
- file: `be-intake/tests/test_processing_monitor_lifecycle_views.py:5-23`
- artifact: `plans/monitoring/task-a67c7b62-949e-4720-b1a2-51fcc3502cec-lifecycle-http-evidence.md:17-24`


## Context

- Original task: `task-a67c7b62-949e-4720-b1a2-51fcc3502cec`
- Reason: `acceptance_incomplete`
- The original task's code changes are preserved. Continue from that state.

## Instructions

Use the concrete goals and findings above to repair the untrustworthy task outcome. Make the minimum implementation and test changes needed, and verify the repaired behavior.

## Important: do not repeat completed work

The previous attempt partially succeeded. Review what is already committed before making changes. Do NOT revert or redo completed work. If the previous approach caused the failure, try a different approach.

## Original plan

Read the original plan at `/Users/michal/Projects/wonderfulkb/plans/2026-10-20_task-a67c7b62-949e-4720-b1a2-51fcc3502cec_monitoring-lifecycle-http-skute-n-bounded-routes-a-funk-n.md` for full context. Focus only on the unmet goals listed above.

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
 Docker image se sestavil a importuje audit package i nový router. Starší monitorovací HTTP sketch testy stále obsahují nedodané předpoklady. Výsledky a přesné blokery jsou v `plans/monitoring/task-a67c7b62-949e-4720-b1a2-51fcc3502cec-lifecycle-http-evidence.md`; checkpoint zůstává otevřený.

**Nasazení ani živé HTTP ověření neproběhlo.** Kromě chybějícího trusted caller→case/document seam čtečka zatím nedekóduje `ResultPublished` a AWS CLI hlásí `NoCredentials`, takže nelze ověřit cílovou revizi a recovery artifact. `aws login` poskytne krátkodobé obnovované credentials; nainstalovaná CLI verze jej podporuje. Souhlasíte, abych spustil `aws login` pro pokračování v ověření AWS cíle? Pro funkční read route je současně potřeba určit vlastníka a rozhraní důvěryhodné case/document autorizace.

```

## TDD proof provenance for this acceptance fix

Do not create or fabricate a fake RED after the original implementation exists. Reuse and link the historical genuine RED from the parent or previous proof when applicable, then capture fresh GREEN verification under this follow-up task.
