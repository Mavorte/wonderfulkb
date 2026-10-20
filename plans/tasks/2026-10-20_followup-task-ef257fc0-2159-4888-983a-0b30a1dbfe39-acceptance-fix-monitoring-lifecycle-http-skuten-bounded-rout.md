# [acceptance-fix] [acceptance-fix] Monitoring lifecycle HTTP: skutečné bounded routes a funkční end-to-end ověření: goal-001: Monitoring l: goal-001: [acceptance-fix] Monitoring lifecycle HTTP: skutečné bounded routes a 

Auto-created by the monitor because the original task `task-4f189265-c034-43e8-b8d9-c4e1fef9a45b` was accepted as done
but did not fully meet all acceptance goals.

## Primary goals (from original task)

- goal-001: [acceptance-fix] Monitoring lifecycle HTTP: skutečné bounded routes a funkční end-to-end ověření: goal-001: Monitoring l

### [BLOCKING] finding-001 - required_implementation_missing / correctness

**Scope:** `goal-001`  
**Claim:** The lifecycle runs, run-detail, and document-audit routes must be usable through the service's real trusted principal-to-case and document authorization boundary.

**Observed**
The route implementation only consults an optional app.state.lifecycle_authorize_read callback and denies when it is absent; main.py never installs a production provider. The target-task checkpoint confirms that no caller-to-case/document provider exists and keeps deployment/live verification blocked. The 200-path tests install a hermetic callback themselves, so they do not supply the missing service integration.

**Why this matters**
A test-injected authorization seam proves adapter behavior but does not deliver authorized lifecycle HTTP behavior in the actual application. In normal application construction every lifecycle request remains denied before the bounded reader is called.

**Required action**
Implement and wire the approved monitoring SERVICE principal and explicit case/document grant lookup in the application composition root, preserving fail-closed behavior and denial-before-read, then exercise the routes through that real boundary.

**Evidence**
- file: `be-intake/app/processing_monitor_lifecycle_routes.py:35-55`
- file: `be-intake/app/main.py:48-51`
- artifact: `plans/checkpoints/task-4f189265-c034-43e8-b8d9-c4e1fef9a45b.checkpoint.md:2-8`
- file: `be-intake/tests/test_processing_monitor_lifecycle_views.py:31-52`

### [BLOCKING] finding-002 - required_implementation_missing / correctness

**Scope:** `goal-001`  
**Claim:** Lifecycle detail and audit responses must preserve supported ResultPublished observations as publication facts in the bounded window.

**Observed**
The contract and reducer expose ResultPublished and published_results, but audit_events.py defines no ResultPublished event class and audit_queries._event_from_item has no ResultPublished dispatch. A bounded read containing that documented event therefore raises Unsupported audit event type, which the HTTP adapter converts to 503 instead of returning publication observations. The target checkpoint also explicitly says the publication producer/decoder is absent.

**Why this matters**
Publication is part of the required lifecycle response. Advertising and mapping published_results cannot make the route functional when the canonical reader cannot decode the underlying event type.

**Required action**
Add the verified producer-owned ResultPublished event contract, persistence round trip, and reader dispatch, then map its stable publication identity and evidence without conflating publication with terminal run state.

**Evidence**
- file: `be-document-processing/contracts/openapi-processing-monitor.yaml:238-257`
- file: `be-document-processing/src/document_processing/audit/audit_queries.py:82-97`
- file: `be-document-processing/src/document_processing/audit/audit_events.py:1-425`
- artifact: `plans/checkpoints/task-4f189265-c034-43e8-b8d9-c4e1fef9a45b.checkpoint.md:6-8`

### [BLOCKING] finding-003 - verification_evidence_missing / evidence

**Scope:** `goal-001`  
**Claim:** The acceptance repair explicitly requires a guarded deployment to the existing AWS test target and direct authenticated live HTTP verification of the changed lifecycle routes with revision, artifact, recovery, and fixture provenance.

**Observed**
The supplied target-task checkpoint leaves the deployment/live step open, records AWS NoCredentials and the missing authorization provider, and states that zero cloud requests were made. No task artifact supplies a target revision, deployed image digest, verified recovery artifact/configuration, authorized synthetic fixture ledger, or direct live runs/detail/audit HTTP assertions.

**Why this matters**
Local TestClient behavior, package/image import, and the passed Test Gate do not establish that the required artifact was deployed or that the changed routes work through the real authorization and audit infrastructure.

**Required action**
After the production authorization and publication-read gaps are resolved, perform the guarded in-place test deployment and record source-to-image and target revision provenance, verified recovery state, entitled synthetic fixture IDs, and bounded authenticated live HTTP assertions for runs, detail, audit, cursor scope, denial, no-store, and read-failure behavior.

**Evidence**
- artifact: `plans/checkpoints/task-4f189265-c034-43e8-b8d9-c4e1fef9a45b.checkpoint.md:2-8`
- plan: `plans/2026-10-20_task-4f189265-c034-43e8-b8d9-c4e1fef9a45b_monitoring-lifecycle-http-skute-n-bounded-routes-a-funk-n.md:implementation-steps-5-6`
- test-gate: `/Users/michal/.openclaw/workspace/km-system/state/test-gates/task-4f189265-c034-43e8-b8d9-c4e1fef9a45b-orphan-implementing.json`


## Context

- Original task: `task-4f189265-c034-43e8-b8d9-c4e1fef9a45b`
- Reason: `acceptance_incomplete`
- The original task's code changes are preserved. Continue from that state.

## Instructions

Use the concrete goals and findings above to repair the untrustworthy task outcome. Make the minimum implementation and test changes needed, and verify the repaired behavior.

## Important: do not repeat completed work

The previous attempt partially succeeded. Review what is already committed before making changes. Do NOT revert or redo completed work. If the previous approach caused the failure, try a different approach.

## Original plan

Read the original plan at `/Users/michal/Projects/wonderfulkb/plans/2026-10-20_task-4f189265-c034-43e8-b8d9-c4e1fef9a45b_monitoring-lifecycle-http-skute-n-bounded-routes-a-funk-n.md` for full context. Focus only on the unmet goals listed above.

## Recent learnings from previous attempt


### 2026-10-20_worker-audit-owner-contract-acceptance-blocker.md

```
---
title: "Worker audit hooks require an owner-issued execution contract"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, audit, worker, tdd, execution-identity]
file_type: rules
---

# Worker audit hooks require an owner-issued execution contract

The monitoring worker must not emit producer events by inventing run identities or attempt ordinals. Before instrumenting enqueue or claim callers, the execution owner must provide stable logical enqueue identity and typed send outcomes, an atomic claim-plus-attempt result, immutable per-execution context forwarding, a
```


### 2026-10-20_trigger-deploy-script-relative-path.md

```
---
title: "Rollback paths must be anchored to the deployment script"
date: 2026-10-20
category: tooling
component: backend
tags: [bash, deployment, path-resolution, testing]
file_type: rules
---

# Anchor deployment rollback paths to the script

Shell deployment scripts may be invoked from any working directory. Resolve the script directory using `${BASH_SOURCE[0]}` before changing directories, then derive rollback template paths from that absolute directory. A regression test can safely evaluate only the path assignments from a separate cwd, avoiding deployment/AWS actions.

When testing via
```


### 2026-10-20_document-events-plan-validation-vs-masked-route-proof.md

```
---
title: "Document-events plán: validní artefakt a masked-404 důkaz jsou různé brány"
date: 2026-10-20
category: tooling
component: tooling
tags: [compound-plan, monitoring, authorization, tdd, acceptance]
file_type: rules
---

Pro task-cf441015-6bba-4862-8200-b2c0047f6905 prošel inspect_plan_artifact po opravě H1 na # Plan 2026-10-20: název; samotné platné sekce nestačily. Volání používá projektový be-document-processing/.venv/bin/python, PYTHONPATH k workspace/km-system/lib a task kontext s projectDir. Výsledek valid dokládá pouze plán, nikoli implementaci nebo TDD. V plánovaném focused te
```

## Implementation session log excerpt (last 50 lines)

```
audit nečtou.

Funkční RED/GREEN důkaz je v `plans/checkpoints/task-4f189265-c034-43e8-b8d9-c4e1fef9a45b.red-green-proof.md`. Prošlo 11 intake testů, 59 auditních a kontraktových testů, 17 backoffice testů i build; lokální Docker image se sestavil a importuje.

**Nasazení a přímé HTTP ověření neproběhly.** V intake chybí skutečný poskytovatel oprávnění volající→case/dokument a AWS CLI hlásí `NoCredentials`. Přesné zbývající kroky a nulový počet cloudových požadavků jsou zaznamenané v `plans/monitoring/task-4f189265-c034-43e8-b8d9-c4e1fef9a45b-lifecycle-http-evidence.md`. Checkpoint proto zůstává otevřený.

Mohu spustit `aws login` pro ověření testovacího cíle? Současně potřebuji rozhraní nebo vlastníka důvěryhodné autorizace case a dokumentu, abych mohl bezpečně dokončit funkční nasazení.

```

## TDD proof provenance for this acceptance fix

Do not create or fabricate a fake RED after the original implementation exists. Reuse and link the historical genuine RED from the parent or previous proof when applicable, then capture fresh GREEN verification under this follow-up task.
