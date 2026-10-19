# [acceptance-fix] Case Client: nasadit GET /cases a prokázat funkčnost přes HTTP: goal-001: Case Client: nasadit GET /cases a prokázat funkčnost přes HTTP

Auto-created by the monitor because the original task `task-7700299e-f977-4acd-a1fe-b7409c3bca5d` was accepted as done
but did not fully meet all acceptance goals.

## Primary goals (from original task)

- goal-001: Case Client: nasadit GET /cases a prokázat funkčnost přes HTTP

### [BLOCKING] finding-001 - required_implementation_missing / correctness

**Scope:** `goal-001`  
**Claim:** The task delivers the guarded API Gateway GET /cases deployment flow and global HTTP acceptance scenarios.

**Observed**
The supplied checkpoint leaves implementation, offline verification, guarded deployment, and live HTTP acceptance unfinished, and the complete task-scoped diff contains no change to be-case-client/tests/integration/case_client_api_integration.py and no additive put_method/put_integration/create_deployment flow in the deploy helper.

**Why this matters**
The goal explicitly requires the agent to deploy GET /cases and prove it over HTTP; changing the ledger identity and local route declarations does not deliver those required behaviors.

**Required action**
Implement the guarded additive Gateway method/integration/stage deployment and the required global pagination, auth, token, and original-operation HTTP scenarios, then complete the authorized deployment workflow.

**Evidence**
- artifact: `plans/checkpoints/task-7700299e-f977-4acd-a1fe-b7409c3bca5d.checkpoint.md:2-9`
- file: `be-case-client/tools/case_client_test_deploy.py:33-43`
- artifact: `caller-supplied-task-scoped-diff:includedPaths`

### [BLOCKING] finding-002 - implemented_behavior_incorrect / correctness

**Scope:** `goal-001`  
**Claim:** Preflight validates all five protected API methods, including both POST /cases and GET /cases.

**Observed**
The delivered preflight route declaration is a Python dictionary containing /cases twice. The later GET entry overwrites POST, so iteration cannot validate POST /cases and does not represent five methods.

**Why this matters**
The task specifically requires replacing the duplicate-key mapping with an ordered list of path/method pairs so all original methods remain protected while GET /cases is added.

**Required action**
Represent required routes without key collision and validate both POST /cases and GET /cases independently, together with the other three methods.

**Evidence**
- file: `be-case-client/tools/case_client_test_deploy.py:190-196`
- file: `be-case-client/tests/test_case_client_live_tools.py:284-286`

### [BLOCKING] finding-003 - verification_evidence_missing / evidence

**Scope:** `goal-001`  
**Claim:** A sanitized live report proves the deployed GET /cases behavior over HTTP within the authorized ledger.

**Observed**
No supplied artifact reports a Gateway deployment identity, global limit=1 traversal across both fixture clients, token/auth outcomes, original-operation regressions, ledger consumption, or matching Lambda hashes. The checkpoint instead states that no live AWS calls were made and the live ledger remained unused.

**Why this matters**
Live deployment and HTTP proof are explicit deliverables of this goal; local source changes and local test output are not deployed evidence.

**Required action**
Supply the required sanitized live deployment and HTTP acceptance report with Gateway readback, scenario outcomes, ledger usage, and unchanged Lambda hash/config evidence.

**Evidence**
- artifact: `plans/checkpoints/task-7700299e-f977-4acd-a1fe-b7409c3bca5d.checkpoint.md:2-9`
- plan: `plans/tasks/2026-10-19_case-client-deploy-global-get-and-test.md:Ověření`

### [BLOCKING] finding-004 - required_tdd_proof_missing / evidence

**Scope:** `goal-001`  
**Claim:** The mandatory RED/GREEN proof demonstrates test-first implementation of the task's Gateway deployment and HTTP-runner behavior.

**Observed**
The supplied RED has one failure only for deploy.TASK using the previous task ID, and GREEN follows after changing that identity. It does not show a failing-then-passing cycle for five-method preflight, Gateway mutation/readback/rollback, or global HTTP accounting and scenarios; the checkpoint also says the new focused cycle could not be captured.

**Why this matters**
The manifest declares tddRequired true and the task requires task-specific RED/GREEN evidence for the missing functional changes, not merely for switching the continuation ledger identity.

**Required action**
Capture valid task-scoped RED and GREEN evidence for the required deployment-helper and HTTP-runner behaviors while preserving prior proof history.

**Evidence**
- artifact: `plans/checkpoints/task-7700299e-f977-4acd-a1fe-b7409c3bca5d.red-green-proof.md:1-46`
- artifact: `plans/checkpoints/task-7700299e-f977-4acd-a1fe-b7409c3bca5d.checkpoint.md:3-9`
- artifact: `manifest.json:33-34`


## Context

- Original task: `task-7700299e-f977-4acd-a1fe-b7409c3bca5d`
- Reason: `acceptance_incomplete`
- The original task's code changes are preserved. Continue from that state.

## Instructions

Use the concrete goals and findings above to repair the untrustworthy task outcome. Make the minimum implementation and test changes needed, and verify the repaired behavior.

## Important: do not repeat completed work

The previous attempt partially succeeded. Review what is already committed before making changes. Do NOT revert or redo completed work. If the previous approach caused the failure, try a different approach.

## Original plan

Read the original plan at `/Users/michal/Projects/wonderfulkb/plans/2026-10-19_task-7700299e-f977-4acd-a1fe-b7409c3bca5d_case-client-nasadit-get-cases-a-prok-zat-funk-nost-p-es-http.md` for full context. Focus only on the unmet goals listed above.

## Recent learnings from previous attempt


### Ověřená oprava provozní diagnózy (host20:01)
Původní learning nesprávně připisuje odmítnutí validátoru. Read-only reprodukce skutečným nainstalovaným helperem: kompletní parent proof v ROOT/plans/checkpoints přijímá nový cyklus; jiný parent proof v be-case-client/plans/checkpoints má jen RED a vrací přesně pozorovanou chybu. Helper vybírá evidence root podle cwd. Žádný historický proof neměň ani nemaž. Zde použij vlastní TASK_ID follow-upu a explicitní shell cd do kořene před KAŽDÝM capture; tento postup funguje se současným helperem a nevyžaduje jeho nové --project-root rozšíření.

## Implementation session log excerpt (last 50 lines)

```
helper rejected the existing task proof with `existing proof is not a valid complete proof for this task` when starting a new cycle. I left that proof unchanged and did not proceed with production edits or AWS operations.

I added focused tests in `be-case-client/tests/test_case_client_live_tools.py` and recorded the blocker in `plans/checkpoints/task-7700299e-f977-4acd-a1fe-b7409c3bca5d.checkpoint.md`. The required root-level RED/GREEN proof has **not** been captured, and deployment and live HTTP acceptance remain incomplete. The task ledger is still at 0 deploy attempts, 0 POST attempts, and 0 HTTP requests.

Saved a learning at `learnings/tooling/tdd-proof-cycle-validation.md`. The proof validation issue must be resolved before continuing the required RED→implementation→GREEN workflow.

```

## Konkrétní proveditelný TDD postup pro tento acceptance fix (nahrazuje starší konfliktní provenance instrukce)

Historický parent RED/GREEN pro změnu deploy.TASK je pouze historie, NE důkaz pěti routes/Gateway/HTTP scénářů. Tyto funkce dosud neexistují; pravý RED před jejich implementací není falešná post-hoc evidence. Implementuj TDD pomocí skill:tdd pro VLASTNÍ aktuální TASK_ID. Green helper vyžaduje vlastní odpovídající RED, nepředávej mu jen parent proof.

Z kořene `/Users/michal/Projects/wonderfulkb` je ověřený focused command:
```
cd /Users/michal/Projects/wonderfulkb && TASK_ID=task-28c88643-682f-4fa4-873f-aeebc8701a1b python3 /Users/michal/.config/opencode/skills/tdd/scripts/proof-capture.py red -- /Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m unittest discover -s be-case-client/tests -p test_case_client_live_tools.py
```
Green použije identický child argv a vlastní TASK_ID. Pokud už VLASTNÍ proof existuje, nejdřív jej přečti a použij jen podporovaný resume/new-cycle postup podle skillu; žádné přepisování. Vždy explicitně `cd` root i pro green/read. Nekopíruj parent proof a nezakládej druhou kopii v komponentě.

Host focused check:26testů,4errors kvůli CHYBĚJÍCÍM funkcím/parametru `gateway_methods`, `required_routes`, `Transport(manifest=...)`; imports/env fungují, síť je zakázaná mockem. Rozšiř testy tak, aby RED reprezentoval chybějící zamýšlené chování (např. jasný assert existence seam před jeho použitím), ne collection/env chybu; neměň význam assertions jen kvůli zelené. Pokud část chování už je implementovaná, zachovej její pravý původ a nepřipravuj umělý RED; nový RED vztahuj jen k novým chybějícím větvím.

Cloud kontext je přesný: reuse stávající ledger `plans/checkpoints/case-client-list-all-live/case-global-72fa-20261019-1909/manifest.json`, continuity `case-global-72fa-20261019-1909`. Záznam je taskově vázán na root7700299e; follow-up zachová lineage/provenance a kumulativní counters, NE reset nebo nový budget podle svého task ID. Capture ID je vlastní follow-up ID, cloud ledger je sdílené autorizované pokračování. Limits3forward+1rollback,60min od první mutace,12POST200HTTP≤2req/s/concurrency2 beze změny. Nevyžaduj neexistující nový approved-ledger kontext. Funkční implementace a kontrolované live nasazení zůstávají v rozsahu; žádné IAM změny a žádná tvrzení o hotovém deploy bez HTTP důkazu.

Použij konkrétní boto3/CLI/helper instrukce z `plans/tasks/2026-10-19_case-client-deploy-global-get-and-test.md`, ale ignoruj jeho historický TASK_ID pro capture a nepřebírej již překonanou diagnózu learningu. V canonical plánu odstraň pokyn ke GREEN-only a `cd be-case-client` pro capture; sestav nový celý postup před implementací.
