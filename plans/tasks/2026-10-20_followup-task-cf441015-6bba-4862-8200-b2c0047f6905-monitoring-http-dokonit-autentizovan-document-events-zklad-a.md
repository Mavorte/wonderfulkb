# [acceptance-fix] Monitoring HTTP: dokončit autentizovaný document-events základ a skutečné nasazení: goal-001: Monitoring HTTP: dokončit autentizovaný document-events základ a skute

Auto-created by the monitor because the original task `task-dfd140ba-c040-48c9-bb5f-f5c204a5d647` was accepted as done
but did not fully meet all acceptance goals.

## Schválené autorizační minimum — 20. 10. 2026 10:01
Michal výslovně schválil (Discord1562012913311551529) dodat chybějící trusted caller→case seam, nikoli čekat na neexistující externí službu. Autoritativní specifikace je `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md`, sekce read-api. Tato instrukce nahrazuje historické zákazy doplnit tuto konkrétní autorizaci a starý plán tam, kde požadoval pouze hledat existující seam; ostatní findings a gates se nemění.

Dodat serverově autentizovaný monitoring SERVICE principal s explicitním server-side case grantem. Dosavadní intake API key, existence case, browser header ani neověřené claims nejsou entitlement. Pro AWS test povolit pouze explicitně vyjmenované syntetické case IDs; žádný wildcard/all-case grant, nové UI role, auth framework, proxy ani broad IAM. Binding credentials→principal a principal→case, bezpečné uložení/rotation a fail-closed adapter jsou konkrétní reviewed implementační návrh v tomto tasku. Secrets nepatří do evidence. Stejný grant vyžaduje retained audit-only historie; ztráta business řádku sama nesmí zrušit authorizaci ani dovolit cross-case čtení. Audit-only document scope musí mít skutečný důvěryhodný důkaz, nikoli guessed key.

Chybějící/forged identita, revoked/nesprávný case grant a porucha autorizačního zdroje musí skončit fail closed PŘED audit Query. Ověřit case/document membership skutečným source seamem. Sdílená implementace v `be-intake/app/processing_monitor_authorization.py` a `processing_monitor_routes.py` musí být použitelná dalšími route moduly; žádný druhý auth reader. Domain-qualified názvy, žádný nový utils.py/state.py/common.py. Existující intake upload auth se nesmí oslabit ani neúmyslně rozšířit. Zachovat no-store a bezpečná 400/403-or-consistent-masked404/404/503 rozlišení.

Dodat autorizovanou syntetickou fixture a skutečný document-events GET v existujícím FastAPI/image včetně bounded readeru a cursor scope. Cílené TDD testy zahrnou healthy principal+grant, forged/missing identity, case mismatch, revoked grant/auth source failure bez audit-read, dvě stránky/cross-document token, audit read failure503, case/document membership a retained audit-only oprávnění. Stejná focused argv RED→GREEN přes podporovaný skill:tdd, plná relevantní Python matice a registrované test/build gates bez ignores nebo snižování assertions.

Součást dodání je instalovaný artifact, guarded AWS TEST deployment a skutečný bounded upload→FileReceived→GET důkaz pro přesně tentýž syntetický case/document s digest/revision/config recovery/provenance a účtem requests/writes. No provider/placená inference, reálné dokumenty/replay, audit insert vydávaný za producer, produkce nebo nové služby. Použít standing authorization v AGENTS.md; neobcházet skutečné denial. SOURCE/INSTALLED/DEPLOYED/LIVE_VERIFIED jsou rozdílná tvrzení; dokument blockerů ani trvalá403 nejsou funkční dodávka. Zachovat původní acceptance findings níže a historickou evidenci.

## Primary goals (from original task)

- goal-001: Monitoring HTTP: dokončit autentizovaný document-events základ a skutečné nasazení

### [BLOCKING] finding-001 - required_implementation_missing / correctness

**Scope:** `goal-001`  
**Claim:** The task requires an authenticated GET /v1/cases/{case_id}/processing/documents/{document_id}/events implementation using a trusted identity-to-case authorization seam, document membership checks, the existing bounded audit reader, and safe HTTP error/cache behavior.

**Observed**
The task checkpoint marks the authorized route implementation step incomplete and states that no trusted caller identity/entitlement interface or authenticated synthetic fixture is available. The supplied diff adds only lifecycle routes for /runs, /runs/{run_id}, and /audit that return 403; it does not add the required processing_monitor_routes.py document-events endpoint.

**Why this matters**
The canonical goal is end-to-end delivery of the authenticated document-events HTTP foundation. A legitimate authorization prerequisite may explain the blocker, but the required endpoint behavior remains undelivered and cannot satisfy the goal.

**Required action**
Provide the owner-approved trusted caller-to-case authorization interface and authorized fixture, then implement and register the document-events route with case/document scope validation, bounded AuditStore.read_document pagination, required response DTO, 400/403-or-masked-404/404/503 behavior, and Cache-Control private, no-store on all responses.

**Evidence**
- file: `plans/tasks/2026-10-20_complete-document-events-http-0818.md`
- artifact: `plans/checkpoints/task-dfd140ba-c040-48c9-bb5f-f5c204a5d647.checkpoint.md:3-10`
- file: `be-intake/app/processing_monitor_lifecycle_routes.py:1-32`

### [BLOCKING] finding-002 - required_tdd_proof_missing / evidence

**Scope:** `goal-001`  
**Claim:** The manifest declares TDD mandatory and the task requires a genuine behavior RED followed by GREEN with the identical focused command in the task-specific red-green proof artifact.

**Observed**
No TDD proof was supplied. The task checkpoint states that RED/GREEN implementation steps remain incomplete and explicitly says no RED/GREEN proof is claimed or manually created.

**Why this matters**
With tddRequired=true, the absent required RED/GREEN provenance is independently blocking even though the implementation is also blocked by authorization.

**Required action**
After the trusted authorization prerequisite is available, execute the required TDD cycle through the supported TDD skill and provide the task-specific RED/GREEN proof showing the same focused argv and an implementation-specific RED followed by GREEN.

**Evidence**
- artifact: `manifest.json:85-86`
- artifact: `plans/checkpoints/task-dfd140ba-c040-48c9-bb5f-f5c204a5d647.checkpoint.md:3-10`
- plan: `plans/2026-10-20_task-dfd140ba-c040-48c9-bb5f-f5c204a5d647_monitoring-http-dokon-it-autentizovan-document-events-z.md:TDD`

### [BLOCKING] finding-003 - verification_evidence_missing / evidence

**Scope:** `goal-001`  
**Claim:** Successful delivery requires actual installation into the intake artifact, guarded in-place deployment to the existing AWS test App Runner target, and bounded authenticated live HTTP verification of the changed document-events route with artifact digest and deployed revision provenance.

**Observed**
The task checkpoint leaves regression/package/deployment/live verification incomplete. The supplied host review records no source or image digest, target revision, recovery/config evidence, authorized synthetic fixture, deployment, or direct live route evidence; Test Gate also has no evidence.

**Why this matters**
The canonical task explicitly rejects source-only completion. Without deployment and direct live-function evidence, the required deployed and LIVE-FUNCTION-VERIFIED outcome is not demonstrated.

**Required action**
After implementing the authorized route, build and verify the installed audit package/router in the intake artifact, perform a guarded deployment to the verified existing test target, and provide task-local redacted evidence of source/image digest, recovery/config guard, deployed revision/time, authenticated route DTO and pagination assertions, no-store headers, negative auth/scope behavior, and hermetic read-failure-to-503 behavior.

**Evidence**
- file: `plans/tasks/2026-10-20_complete-document-events-http-0818.md:Povinné dokončení: skutečné nasazení a dotažení read API`
- artifact: `plans/checkpoints/acceptance-host-review-0818-read-reducer.md:GET /events — source and deployment evidence`
- artifact: `plans/checkpoints/task-dfd140ba-c040-48c9-bb5f-f5c204a5d647.checkpoint.md:3-10`


## Context

- Original task: `task-dfd140ba-c040-48c9-bb5f-f5c204a5d647`
- Reason: `acceptance_incomplete`
- The original task's code changes are preserved. Continue from that state.

## Instructions

Use the concrete goals and findings above to repair the untrustworthy task outcome. Make the minimum implementation and test changes needed, and verify the repaired behavior.

## Important: do not repeat completed work

The previous attempt partially succeeded. Review what is already committed before making changes. Do NOT revert or redo completed work. If the previous approach caused the failure, try a different approach.

## Original plan

Read the original plan at `/Users/michal/Projects/wonderfulkb/plans/2026-10-20_task-dfd140ba-c040-48c9-bb5f-f5c204a5d647_monitoring-http-dokon-it-autentizovan-document-events-z.md` for full context. Focus only on the unmet goals listed above.

## Recent learnings from previous attempt


### 2026-10-20_lifecycle-acceptance-dto-drift-functional-proof.md

```
---
title: "Lifecycle acceptance repair: DTO drift and functional proof"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, lifecycle, acceptance, tdd, openapi]
file_type: rules
---

# Lifecycle acceptance repair: DTO drift and functional proof

When reopening the lifecycle HTTP acceptance task, inspect both the parent GREEN assertion and the current OpenAPI schema against the reducer output. In this repository the parent GREEN asserted only unconditional 403; it cannot stand in for authorized bounded HTTP output. The YAML run/audit DTOs advertise `lifecycle`, `termi
```


### 2026-10-20_document-events-authorization-prerequisite.md

```
---
title: "Monitoring: oprávněný case musí mít doloženou identitu a autorizační rozhodnutí"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, authorization, tdd, intake]
file_type: rules
---

V intake `guard()` ověřuje pouze sdílený `x-api-key`; `require_case()` zjišťuje existenci řádku case pouze pro upload. `test_monitor_file_received.py` mockuje existující case, nikoli oprávněného volajícího. Ani úspěšná auditní sada (209 testů) proto neprokazuje, že lze bezpečně zpřístupnit case-scoped monitoring GET. Existující `processing_monitor_lifecycle_routes.py` expli
```


### 2026-10-20_trigger-stream-template-canonical-parity.md

```
---
title: "Stream template parity must use its canonical owner"
date: 2026-10-20
category: architecture
component: backend
tags: [cloudformation, dynamodb, template-parity, rollback]
---

# Keep stream-template parity anchored to its canonical owner

The validator trigger's canonical DynamoDB table template lives at `be-intake/documents-table/template.yaml`. From `be-validator-agent/trigger/tests/test_template.py`, the repository root is `HERE.parents[1]`; `HERE.parents[2]` escapes the checkout and produces a misleading `FileNotFoundError`.

For stream-copy parity, remove only `DocumentsTable
```

## Implementation session log excerpt (last 50 lines)

```
ute by proto porušilo bezpečnostní podmínku plánu.

Blocker a stav SOURCE / INSTALLED / DEPLOYED / LIVE_VERIFIED jsou zaznamenány v `plans/monitoring/task-dfd140ba-c040-48c9-bb5f-f5c204a5d647-http-blocker.md`; checkpoint určuje pokračování. **Nebylo zachyceno RED/GREEN ani provedeno nasazení či live HTTP ověření.** Původní focused test končí chybějící fixture před testem chování, takže nejde o platný RED.

Ostatní spuštěné kontroly prošly: auditní focused testy **35**, celé document-processing testy **209**, backoffice testy **17** a build. K pokračování je potřeba od vlastníka služby důvěryhodný caller→case autorizační interface, jeho politiku zamítnutí a autentizovanou oprávněnou syntetickou case/document fixture. Poté lze v tomto tasku dokončit TDD, route a skutečné testovací nasazení.

```

## TDD proof provenance for this acceptance fix

Do not create or fabricate a fake RED after the original implementation exists. Reuse and link the historical genuine RED from the parent or previous proof when applicable, then capture fresh GREEN verification under this follow-up task.
