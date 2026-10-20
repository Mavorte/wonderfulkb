# [acceptance-fix] Monitoring cache reuse: dokončit požadovanou validační, izolační a fail-open test matici: goal-001: Monitoring cache reuse: dokončit požadovanou validační, izolační a fai

Auto-created by the monitor because the original task `task-73ee7806-e314-4dbf-9474-8b1228b9be04` was accepted as done
but did not fully meet all acceptance goals.

## Primary goals (from original task)

- goal-001: Monitoring cache reuse: dokončit požadovanou validační, izolační a fail-open test matici

### [BLOCKING] finding-001 - required_implementation_missing / correctness

**Scope:** `goal-001`  
**Claim:** The required PageCacheReused validation, isolation, no-I/O, and bounded fail-open characterization matrix is incomplete.

**Observed**
The supplied focused test covers basic completed/failed roundtrips, changed-payload idempotence, selected invalid values, and a pure Decimal mapping, but contains no cache-event tests for run/attempt/page/document isolation, omitted required-argument TypeError behavior, constructor cache/model/S3/environment sentinel checks, complete forbidden payload fields such as blocks/tables/storage keys, or the real existing file_received fail-open seam and its explicitly bounded responsibility.

**Why this matters**
These are named deliverables of goal-001 rather than optional suite breadth; their absence leaves the requested cache contract proof materially incomplete even though the central event implementation already exists.

**Required action**
Add focused hermetic PageCacheReused tests for every missing matrix branch, including exact missing-argument exception semantics, scoped isolation, full payload non-leakage, constructor no-I/O sentinels, and an honest concrete reference or characterization of the existing file_received-only fail-open boundary without inventing a cache producer API.

**Evidence**
- file: `be-document-processing/tests/test_monitor_cache_reused_events.py:1-89`
- plan: `plans/tasks/2026-10-20_complete-cache-contract-proof-0923.md`
- artifact: `plans/checkpoints/task-73ee7806-e314-4dbf-9474-8b1228b9be04.checkpoint.md`

### [BLOCKING] finding-002 - required_tdd_proof_missing / evidence

**Scope:** `goal-001`  
**Claim:** Mandatory task-scoped TDD proof was not supplied.

**Observed**
The immutable manifest sets tddRequired to true, the canonical task requires a task-specific genuine RED/GREEN applicability proof, and the caller supplied '(no TDD proof supplied)'; the checkpoint also leaves the TDD applicability and focused matrix step incomplete.

**Why this matters**
Without the required proof there is no caller-supplied evidence of the mandated RED/GREEN cycle or an honest characterization-only applicability decision for already-correct behavior.

**Required action**
Provide the task-scoped red-green proof with the required same-command RED/GREEN evidence or documented applicable characterization path, preserving genuine output and explaining which assertions exposed missing behavior versus existing behavior.

**Evidence**
- artifact: `TDD proof/provenance: no TDD proof supplied`
- file: `plans/checkpoints/task-73ee7806-e314-4dbf-9474-8b1228b9be04.checkpoint.md:1-10`
- plan: `plans/tasks/2026-10-20_complete-cache-contract-proof-0923.md`


## Context

- Original task: `task-73ee7806-e314-4dbf-9474-8b1228b9be04`
- Reason: `acceptance_incomplete`
- The original task's code changes are preserved. Continue from that state.

## Instructions

Use the concrete goals and findings above to repair the untrustworthy task outcome. Make the minimum implementation and test changes needed, and verify the repaired behavior.

## Important: do not repeat completed work

The previous attempt partially succeeded. Review what is already committed before making changes. Do NOT revert or redo completed work. If the previous approach caused the failure, try a different approach.

## Original plan

Read the original plan at `/Users/michal/Projects/wonderfulkb/plans/2026-10-20_task-73ee7806-e314-4dbf-9474-8b1228b9be04_monitoring-cache-reuse-dokon-it-po-adovanou-valida-n-izola.md` for full context. Focus only on the unmet goals listed above.

## Recent learnings from previous attempt


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


### 2026-10-20_green-pro-bezpe-n-odm-tnut-neprokazuje-funk-n-read-route.md

```
---
title: "GREEN pro bezpečné odmítnutí neprokazuje funkční read route"
date: 2026-10-20
category: test-failures
component: backend
tags: [tdd, monitoring, verification]
file_type: rules
---

# GREEN pro bezpečné odmítnutí neprokazuje funkční read route

RED→GREEN testy prošly pro fail-closed chování a routes byly registrované, ale endpointy stále nevracely požadované bounded observations. Při hodnocení dodávky rozlišovat důkaz bezpečného odmítnutí od důkazu funkčního čtení; ten vyžaduje autorizovanou odpověď, dekódování `ResultPublished` a živé HTTP ověření.

## Context
Extracted from task: 
```


### 2026-10-20_glob-ln-api-kl-nesta-k-autorizaci-case.md

```
---
title: "Globální API klíč nestačí k autorizaci case"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, authorization, fail-closed]
file_type: rules
---

# Globální API klíč nestačí k autorizaci case

Intake API klíč prokazuje přístup k API, ale ne oprávnění volajícího číst auditní data konkrétního case nebo dokumentu. Lifecycle HTTP routes proto lokálně vracely `403` s `Cache-Control: private, no-store`. Před povolením odpovědi `200` je nutné napojit důvěryhodnou vazbu caller→case/document; samotný globální klíč jako autorizační kontrolu nepoužívat.

## Conte
```

## Implementation session log excerpt (last 50 lines)

```
 expanded `PageCacheReused` test matrix and fixed a round-trip defect: `from_item` now converts persisted `artifact_ids` lists back to tuples. Focused tests pass (17), the full backend suite passes (209), and backoffice tests (17) and build pass.

**Delivery is incomplete:** the proof helper created RED/GREEN evidence at `be-document-processing/plans/checkpoints/task-73ee7806-e314-4dbf-9474-8b1228b9be04.red-green-proof.md`, but the required artifact path is the monorepo-level `plans/checkpoints/...`. A subsequent root-level capture did not produce a proof because tests already passed. I did not manually copy or reconstruct proof; the required-path acceptance artifact is therefore missing.

A learning was saved at `learnings/architecture/2026-10-20_page-cache-reused-artifact-roundtrip.md`.

```

## TDD proof provenance for this acceptance fix

Do not create or fabricate a fake RED after the original implementation exists. Reuse and link the historical genuine RED from the parent or previous proof when applicable, then capture fresh GREEN verification under this follow-up task.
