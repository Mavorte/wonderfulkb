# [acceptance-fix] Monitoring MVP: detekce podpisů ve stávajícím steps API: goal-001: Monitoring MVP: detekce podpisů ve stávajícím steps API

Auto-created by the monitor because the original task `task-095a56a6-1e34-4c79-9649-07a109f27928` was accepted as done
but did not fully meet all acceptance goals.

## Primary goals (from original task)

- goal-001: Monitoring MVP: detekce podpisů ve stávajícím steps API

### [BLOCKING] finding-001 - required_implementation_missing / correctness

**Scope:** `goal-001`  
**Claim:** The signature-read increment must be installed, guardedly deployed to the existing AWS test App Runner service, and positively verified through authenticated HTTP before the task is complete.

**Observed**
The task checkpoint marks deployment/live verification step 5b BLOCKED, states the final candidate was NOT DEPLOYED, and records that no bearer retrieval or HTTP verification occurred; the deployed image was confirmed to lack the signature allowlist.

**Why this matters**
The caller's task contract explicitly says source/local green is insufficient and requires DEPLOYED plus LIVE-FUNCTION-VERIFIED status in this same delivery. The supplied material therefore establishes an undelivered required behavior despite the completed source implementation and valid RED/GREEN proof.

**Required action**
Complete the guarded in-place rollout of the final candidate to the existing wonderfulkb-ingest AWS test target, verify the deployed digest/revision and healthy operation, then perform the bounded authenticated positive signature-observation HTTP checks and record the truthful deployed/live evidence.

**Evidence**
- file: `plans/checkpoints/task-095a56a6-1e34-4c79-9649-07a109f27928.checkpoint.md:5-17`
- file: `plans/tasks/2026-10-20_monitor-mvp-19-signature-read.md`


## Context

- Original task: `task-095a56a6-1e34-4c79-9649-07a109f27928`
- Reason: `acceptance_incomplete`
- The original task's code changes are preserved. Continue from that state.

## Instructions

Use the concrete goals and findings above to repair the untrustworthy task outcome. Make the minimum implementation and test changes needed, and verify the repaired behavior.

## Important: do not repeat completed work

The previous attempt partially succeeded. Review what is already committed before making changes. Do NOT revert or redo completed work. If the previous approach caused the failure, try a different approach.

## Original plan

Read the original plan at `/Users/michal/Projects/wonderfulkb/plans/2026-10-20_task-095a56a6-1e34-4c79-9649-07a109f27928_monitoring-mvp-detekce-podpis-ve-st-vaj-c-m-steps-api.md` for full context. Focus only on the unmet goals listed above.

## Recent learnings from previous attempt


### 2026-10-20_signature-read-public-code-image-provenance-and-runtime-blockers.md

```
---
title: "Signature read: veřejný failure kód, image provenance a čerstvé runtime blockers"
date: 2026-10-20
category: tooling
component: backend
tags: [monitoring, signature, tdd, docker, deployment, provenance, budgets]
file_type: rules
---

# Signature read: ověřit celou allowlist → veřejný DTO → image cestu

Při task-095a56a6-1e34-4c79-9649-07a109f27928 reader již dekódoval signature_detection, ale steps observations stage zahazovaly a document/run StepFailed coarsenoval SIGNATURE_DETECTION_FAILED na PROCESSING_FAILED. Úzká oprava potřebovala tři OBSERVATION_FIELDS položky v processing_m
```


### 2026-10-20_attempts-final-image-provenance-after-concurrent-signature-changes.md

```
---
title: "Attempts GET: souběžné změny vyžadují nové ověření finálního artifactu"
date: 2026-10-20
category: tooling
component: backend
tags: [monitoring, attempts, docker, provenance, deployment]
file_type: rules
---

Při task-dc9a8eab byl nový attempts GET ověřen skutečným RED404 a GREEN31. Po prvním Docker build/smoke přibyl souběžný signature allowlist ve sdíleném facade, step routeru, YAML a smoke. Hashový readback odhalil rozdíl vůči již sestavenému image. Zachovat cizí změny, znovu sestavit final image a spustit instalovaný ASGI smoke jako UID10001 bez sítě; následný plný gate prošel7
```

## Implementation session log excerpt (last 50 lines)

```
etadata membership; bounded audit Query je prázdný. Není doložen skutečný signature event/run/attempt.
3. Aktuálně nasazený image signature steps allowlist ještě neobsahuje.

Žádný rollout, live HTTP request ani cloud write nebyl proveden. Pro Jackieho je připraven přesný same-delivery postup včetně artifact digestů, recovery a image-only config diffu.

### Artefakty
- [Evidence a operator handoff](plans/monitoring/task-095a56a6-1e34-4c79-9649-07a109f27928-signature-read-evidence.md)
- [RED/GREEN proof](plans/checkpoints/task-095a56a6-1e34-4c79-9649-07a109f27928.red-green-proof.md)
- [Checkpoint](plans/checkpoints/task-095a56a6-1e34-4c79-9649-07a109f27928.checkpoint.md)

Review má stav **NEEDS_FIX** kvůli nedokončené runtime dodávce. Learning byl uložen; task nebyl označen jako dokončený.

```

## TDD proof provenance for this acceptance fix

Do not create or fabricate a fake RED after the original implementation exists. Reuse and link the historical genuine RED from the parent or previous proof when applicable, then capture fresh GREEN verification under this follow-up task.
