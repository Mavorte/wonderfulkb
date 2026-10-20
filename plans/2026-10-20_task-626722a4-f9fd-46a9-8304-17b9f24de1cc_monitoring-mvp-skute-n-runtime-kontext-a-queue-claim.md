# Plan 2026-10-20: Monitoring MVP — runtime kontext a queue claim producer

Rozhodnout proveditelnost skutečného producer napojení; případnou zdrojovou změnu provést pouze přes potvrzeného execution ownera a skutečné autoritativní identity.

## Analysis

- `be-validator-agent/trigger/common.py:147-188` je enqueue producer: mění business row na `queued`, následně posílá SQS zprávu, ale `Context.send` zahazuje response. Při send chybě retry může opakovat zprávu; run identity není v payloadu.
- `be-validator-agent/trigger/common.py:191-222` provádí podmíněný claim z `queued` nebo expired `processing` (lease 930s), ale nepřidává run/attempt identitu ani čítač.
- `be-validator-agent/trigger/worker_handler.py:55-75` volá `claim_document`, pak `run_document(..., options=options())`; `ApproximateReceiveCount` slouží jen chybovému logu.
- `be-validator-agent/pipeline/run.py:28-43,198+` již přijímá explicitní `Options`; zatím neověřená cesta pro neměnný execution context.
- Zdrojový seam je přítomen v checkoutu, ale `plans/monitoring/live-trigger-evidence-20261019.md` dokládá pouze byte shodu modulu common a worker handleru s runtime artefakty, nikoli celý image/build caller. Candidate ref `475deafc567366c2587ef4d73fbf9a31fadb59f8` není oprávněním k source replacement.
- Stávající execution rozhraní postrádá potvrzené enqueue outcome pro nejednoznačný send a atomický úspěšný claim s attempt incrementem. To je blocker pro RunQueued/AttemptStarted; nevyrábět identitu z auditů, receive count ani schválené inference o runtime tabulce/outboxu.

## Approach

- Nejprve ověřit ownership/build caller a potvrdit, zda existuje kompatibilní autoritativní run/attempt interface. Zachovat business schema, retry, DLQ, 930s lease a claim semantics.
- Pokud interface chybí, zaznamenat přesný blocker a nejmenší potřebný execution kontrakt do `plans/monitoring/runtime-producer-context-contract.md`; oddělit požadovanou změnu execution od již schváleného audit listeneru. Zastavit producer implementaci, nikoli deklarovat integraci hotovou.
- Pokud interface existuje, použít pouze stabilní event identity pro tutéž doloženou událost, emitovat RunQueued až po potvrzeném enqueue a AttemptStarted až po atomicky potvrzeném claim+attempt incrementu. Předat immutable context explicitním argumentem workerem do `run_document/Options`; žádný warm global/environment identity.
- Jeden injektovaný listener port; audit event construction/validation/serialization, I/O a fail-open izolace zůstávají v `be-document-processing/src/document_processing/audit/`. Business caller předává jen minimální hodnoty na sémantické hranici; composition root injektuje dependency.

## Implementation

1. Zkontrolovat caller, build provenance, concurrency/claim/send kód a existující listener port; zapsat doložený source/build identity bez privátního obsahu.
2. Při chybějícím execution interface vytvořit `plans/monitoring/runtime-producer-context-contract.md` s chybějícími metodami/výsledky, atomicity pro enqueue/claim, send crash/ambiguity rozhodnutím a nejmenším kontraktem. Nezměnit business runtime.
3. Pouze při potvrzeném interface, zavést TDD změny do skutečných producer/context callerů a jejich focused testů. Nepřipojovat starý DocumentWorker ani no-op/mock-only adapter jako důkaz.
4. Ověřit NoOp, funkční listener a selhávající sink: shodné business writes/pořadí, return/error chování a provider call count, kde relevantní; ověřit import direction.
5. Spustit registrované gates `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` a příslušné Python focused tests. Source tests nejsou deployed proof; deployment/live smoke není v tomto scope.

## Testing

- Hermetické caller tests: concurrent/duplicate enqueue; confirmed versus ambiguous send; concurrent/duplicate claim; failed claim bez attempt incrementu a bez AttemptStarted; dveří immutable context bez leakage; audit failure zachovává původní business chování.
- Žádné E2E success bez autoritativních identity a skutečných callerů. Zaznamenat technické blokery a přesný source/build identity; bez cloud/model/live-message/deploy zásahů.
- Full registered gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.

## TDD

Provést cyklus dle `skill:tdd` pouze po potvrzení execution interface a canonical caller; blocker fáze nesmí být nahrazena fiktivním RED/GREEN adapterem.

**Test file:** `be-validator-agent/trigger/tests/test_enqueue.py` a `be-validator-agent/trigger/tests/test_worker.py` (rozšíření testů skutečných callerů)
**Framework:** pytest, navazuje na existující trigger test suite.
**Run command:** `python -m pytest be-validator-agent/trigger/tests/test_enqueue.py be-validator-agent/trigger/tests/test_worker.py`
**Skeleton:** první TDD krok po odblokování doplní testy proti zjištěným skutečným metodám/context portu; imports/signatures se nespekulují před rozhodnutím interface.

| Test | RED | GREEN |
|---|---|---|
| confirmed enqueue emits once with stable event identity; ambiguous send does not claim confirmation | žádné RunQueued při neověřeném send výsledku / id se mění při retry | pouze potvrzený enqueue emituje a retry téže doložené události zachová id |
| only successful atomic claim increments attempt and emits AttemptStarted | failed/duplicate claim přesto zvýší čítač nebo emituje | pouze jeden úspěšný claim dostane skutečné attempt_no |
| context passes explicitly to run_document and does not leak across calls | context chybí či se zamění mezi dvěma souběžnými voláními | každý běh obdrží vlastní immutable context |
| failing audit listener is fail-open | audit chyba mění business return/error/writes | business výsledek, chyby, writes a provider calls zůstávají stejné |

## Files

| Path | Planned change |
|---|---|
| `be-validator-agent/trigger/common.py` | Pouze pokud canonical caller a schválený authoritative enqueue/claim contract existují. |
| `be-validator-agent/trigger/worker_handler.py` | Explicitní context forwarding pouze z potvrzeného claimu. |
| `be-validator-agent/pipeline/run.py` | Přijmout/propagovat immutable execution context jen pokud nezmění business semantics. |
| `be-validator-agent/trigger/tests/test_enqueue.py` | Focused tests skutečného enqueue callera. |
| `be-validator-agent/trigger/tests/test_worker.py` | Focused tests claim, attempt a context propagation. |
| `plans/monitoring/runtime-producer-context-contract.md` | Povinný blocker/contract záznam, pokud authoritative interface chybí. |

## Progress

- [x] Načteny runtime evidence, proposal isolation boundaries a relevantní learning.
- [x] Zjištěny skutečné checked-in enqueue, claim, worker a pipeline seams; chybí potvrzená autoritativní run/attempt sémantika.
- [ ] Před source implementací uzavřít canonical owner/build provenance a execution interface; při absenci sepsat přesný kontrakt blocker.
