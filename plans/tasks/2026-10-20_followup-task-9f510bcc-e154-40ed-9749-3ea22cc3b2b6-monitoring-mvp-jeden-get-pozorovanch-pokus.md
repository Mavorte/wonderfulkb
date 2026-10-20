# [acceptance-fix] Monitoring MVP: jeden GET pozorovaných pokusů: goal-001: Monitoring MVP: jeden GET pozorovaných pokusů

Auto-created by the monitor because the original task `task-dc9a8eab-2900-4aca-9a80-4411cebc0472` was accepted as done
but did not fully meet all acceptance goals.

## Primary goals (from original task)

- goal-001: Monitoring MVP: jeden GET pozorovaných pokusů

### [BLOCKING] finding-001 - required_implementation_missing / correctness

**Scope:** `goal-001`  
**Claim:** The task requires the attempts GET candidate to be deployed in place to the existing wonderfulkb-ingest AWS TEST App Runner target and reach a deployed state.

**Observed**
The supplied task checkpoint states that the final candidate image was built and locally smoked, but App Runner remained on a sibling image and this task performed no push or UpdateService; Step 5 remained incomplete and the task was explicitly marked NOT COMPLETE.

**Why this matters**
The canonical task makes actual guarded TEST deployment part of this task and states that source or local-green delivery is insufficient. The supplied state is therefore missing a required delivery component, not merely missing test execution.

**Required action**
Guardedly deploy the task candidate to the specified existing App Runner TEST service, preserve and verify recovery/configuration, wait for successful healthy rollout, and record the deployed image/revision/digest.

**Evidence**
- file: `plans/checkpoints/task-dc9a8eab-2900-4aca-9a80-4411cebc0472.checkpoint.md:6-11`
- plan: `plans/tasks/2026-10-19_monitor-mvp-09-attempts-get.md:Povinné dokončení and Závazné upřesnění dodávky`

### [BLOCKING] finding-002 - verification_evidence_missing / evidence

**Scope:** `goal-001`  
**Claim:** The task requires bounded authenticated HTTP verification directly against the deployed attempts route using an authorized synthetic case/document and observed run/attempt data.

**Observed**
The supplied checkpoint states that this task made no HTTP or fixture reads and that LIVE-FUNCTION-VERIFIED remains blocked; only local ASGI/image smoke and test proof are supplied.

**Why this matters**
The canonical task explicitly rejects health checks, local TestClient, and 200-empty responses as proof of the new functionality. No supplied evidence demonstrates the deployed route's nonempty DTO, scoping/filtering, continuation, private no-store behavior, or required negative authorization/scope behavior.

**Required action**
After deployment, perform the bounded authenticated live HTTP assertions required by the task against the authorized synthetic fixture and record sanitized request counts, IDs/schema assertions, status, cache policy, target revision, and truthful content-branch outcome.

**Evidence**
- file: `plans/checkpoints/task-dc9a8eab-2900-4aca-9a80-4411cebc0472.checkpoint.md:6-11`
- plan: `plans/tasks/2026-10-19_monitor-mvp-09-attempts-get.md:Povinné dokončení items 3-6 and Závazné upřesnění dodávky`


## Context

- Original task: `task-dc9a8eab-2900-4aca-9a80-4411cebc0472`
- Reason: `acceptance_incomplete`
- The original task's code changes are preserved. Continue from that state.

## Instructions

Use the concrete goals and findings above to repair the untrustworthy task outcome. Make the minimum implementation and test changes needed, and verify the repaired behavior.

## Important: do not repeat completed work

The previous attempt partially succeeded. Review what is already committed before making changes. Do NOT revert or redo completed work. If the previous approach caused the failure, try a different approach.

## Original plan

Read the original plan at `/Users/michal/Projects/wonderfulkb/plans/2026-10-20_task-dc9a8eab-2900-4aca-9a80-4411cebc0472_monitoring-mvp-jeden-get-pozorovan-ch-pokus.md` for full context. Focus only on the unmet goals listed above.

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
d a skutečný ASGI smoke v image jako UID 10001 bez sítě: **PASS**.
- `git diff --check`: **PASS**.

### Blokery runtime dodávky
Je potřeba od Jackieho převzít existující deployment guard a potvrzený zůstatek sdíleného deploy/HTTP/fixture budgetu. Pro nonempty live proof také chybí doložená aktuální oprávněná fixture s reálným `AttemptStarted`.

App Runner stále používá předchozí run-events image. Nový candidate jsem nenasadil; žádné HTTP požadavky ani syntetické zápisy nebyly provedeny.

Podrobná evidence, artifact digesty, recovery a přesný postup pokračování jsou v:
`plans/monitoring/task-dc9a8eab-2900-4aca-9a80-4411cebc0472-attempts-evidence.md`

Povinný RED/GREEN proof i checkpoint existují. Learning byl uložen. **Stav: SOURCE ✅ / INSTALLED ✅ / DEPLOYED ❌ / LIVE-FUNCTION-VERIFIED ❌.**

```

## TDD proof provenance for this acceptance fix

Do not create or fabricate a fake RED after the original implementation exists. Reuse and link the historical genuine RED from the parent or previous proof when applicable, then capture fresh GREEN verification under this follow-up task.
