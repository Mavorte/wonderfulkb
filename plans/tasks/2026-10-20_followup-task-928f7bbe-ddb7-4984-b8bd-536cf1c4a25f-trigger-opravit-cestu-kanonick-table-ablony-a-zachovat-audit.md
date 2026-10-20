# [acceptance-fix] Trigger: opravit cestu kanonické table šablony a zachovat audit při stream variantě: goal-001: Trigger: opravit cestu kanonické table šablony a zachovat audit při st

Auto-created by the monitor because the original task `task-d76e4d9e-8ec3-4977-b15f-c8b28368ccab` was accepted as done
but did not fully meet all acceptance goals.

## Primary goals (from original task)

- goal-001: Trigger: opravit cestu kanonické table šablony a zachovat audit při stream variantě

### [BLOCKING] finding-001 - implemented_behavior_incorrect / correctness

**Scope:** `goal-001`  
**Claim:** The rollback template reference must resolve from deploy.sh's own location to the canonical be-intake documents-table template.

**Observed**
deploy.sh sets ORIGINAL_TEMPLATE using 'cd ../../be-intake/documents-table', which is evaluated relative to the process working directory rather than the script directory.

**Why this matters**
The expression only resolves correctly when the caller happens to start in be-validator-agent/trigger; invoking the script from another working directory can fail or select the wrong path, contrary to the explicit script-directory-anchored rollback contract.

**Required action**
Derive the canonical template path from deploy.sh's directory, for example via a SCRIPT_DIR based on BASH_SOURCE[0], so rollback resolution is independent of the caller's working directory.

**Evidence**
- file: `be-validator-agent/trigger/deploy.sh:22`
- plan: `plans/2026-10-20_task-d76e4d9e-8ec3-4977-b15f-c8b28368ccab_trigger-opravit-cestu-kanonick-table-ablony-a-zachovat.md`

### [BLOCKING] finding-002 - required_tdd_proof_missing / evidence

**Scope:** `goal-001`  
**Claim:** The caller-required TDD proof must contain a genuine RED caused by the missing stream-template resource/output parity before implementation.

**Observed**
The recorded RED fails with FileNotFoundError for /Users/michal/Projects/be-intake/documents-table/template.yaml because the newly edited test used HERE.parents[2]; the checkpoint explicitly says this was a test path index error corrected before implementation. It therefore never exercised the intended missing AuditTable/output parity.

**Why this matters**
A RED caused by an erroneous test fixture path does not demonstrate that the regression test detected the pre-implementation behavior required by the task, so the supplied mandatory RED/GREEN provenance is invalid despite the later GREEN run.

**Required action**
Provide valid RED/GREEN proof using the exact focused command where RED reaches the parity assertions and fails for the pre-implementation stream-template mismatch, followed by GREEN after the implementation change.

**Evidence**
- artifact: `plans/checkpoints/task-d76e4d9e-8ec3-4977-b15f-c8b28368ccab.red-green-proof.md`
- artifact: `plans/checkpoints/task-d76e4d9e-8ec3-4977-b15f-c8b28368ccab.checkpoint.md`
- file: `be-validator-agent/trigger/tests/test_template.py:117-124`


## Context

- Original task: `task-d76e4d9e-8ec3-4977-b15f-c8b28368ccab`
- Reason: `acceptance_incomplete`
- The original task's code changes are preserved. Continue from that state.

## Instructions

Use the concrete goals and findings above to repair the untrustworthy task outcome. Make the minimum implementation and test changes needed, and verify the repaired behavior.

## Important: do not repeat completed work

The previous attempt partially succeeded. Review what is already committed before making changes. Do NOT revert or redo completed work. If the previous approach caused the failure, try a different approach.

## Original plan

Read the original plan at `/Users/michal/Projects/wonderfulkb/plans/2026-10-20_task-d76e4d9e-8ec3-4977-b15f-c8b28368ccab_trigger-opravit-cestu-kanonick-table-ablony-a-zachovat.md` for full context. Focus only on the unmet goals listed above.

## Recent learnings from previous attempt


### 2026-10-20_monitoring-openapi-vy-aduje-coverage-i-v-ste-n-implementaci.md

```
---
title: "Monitoring OpenAPI vyžaduje coverage i v částečné implementaci"
date: 2026-10-20
category: patterns
component: backend
tags: [monitoring, openapi, schema]
file_type: rules
---

# Monitoring OpenAPI vyžaduje coverage i v částečné implementaci

OpenAPI kontrakt document-events uvádí `coverage=partial` jako povinné pole, přestože starý testovací sketch očekával jen tři pole. Při implementaci a aktualizaci testů vycházet z aktuálního kontraktu; nepřebírat očekávání ze starého sketchi.

## Context
Extracted from task: Monitoring HTTP: dokončit autentizovaný document-events základ a skut
```


### 2026-10-20_chyb-j-c-fixture-nen-behavior-ln-tdd-red.md

```
---
title: "Chybějící fixture není behaviorální TDD RED"
date: 2026-10-20
category: test-failures
component: backend
tags: [tdd, fixtures, authorization]
file_type: rules
---

# Chybějící fixture není behaviorální TDD RED

Původní intake sketch selhal na chybějící pytest fixture ještě před spuštěním ověřovaného chování. Takové selhání nelze použít jako důkaz TDD RED. Pro autorizační scénář je navíc potřeba autentizovaná syntetická fixture s oprávněným volajícím a case/document; pouhé mockování existujícího case oprávnění neprokazuje.

## Context
Extracted from task: Monitoring HTTP: dokončit a
```


### 2026-10-20_sd-len-api-kl-nesta-pro-ten-ud-lost-konkr-tn-ho-case.md

```
---
title: "Sdílený API klíč nestačí pro čtení událostí konkrétního case"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, authorization, case-scope]
file_type: rules
---

# Sdílený API klíč nestačí pro čtení událostí konkrétního case

Intake `guard()` ověřuje jen sdílený `x-api-key` a `require_case()` pouze existenci case při uploadu. Ani úspěšné testy proto nedokazují, že konkrétní volající smí číst document-events daného case. Před zpřístupněním case-scoped GET je nutné důvěryhodné rozhraní pro identitu volajícího a rozhodnutí caller→case, včetně politiky zam
```

## Implementation session log excerpt (last 50 lines)

```
k-d76e4d9e-8ec3-4977-b15f-c8b28368ccab.red-green-proof.md` and a learning at `learnings/architecture/2026-10-20_trigger-stream-template-canonical-parity.md`.

**Verification:** focused test passed; backoffice tests and build passed; offline rollback-path check passed. The full trigger suite has one failure in the already-present `tests/test_audit_instrumentation.py` concerning a missing `execution_context` parameter. `cfn-lint` was unavailable.

**TDD evidence caveat:** The captured RED run failed on an incorrect test path (`HERE.parents[2]` escaped the repository); I corrected it to `HERE.parents[1]` before implementation. GREEN used the same focused command and passed. The RED output therefore does not prove the intended template-parity failure. No deployment or AWS operations were run.

```

## TDD proof provenance for this acceptance fix

Do not create or fabricate a fake RED after the original implementation exists. Reuse and link the historical genuine RED from the parent or previous proof when applicable, then capture fresh GREEN verification under this follow-up task.
