# Plan 2026-10-20: Monitoring lifecycle evidence and identity validation

Rozšířit pure lifecycle reducer a jeho focused kontrakty pouze pro nevyřešené případy identity/evidence.

## Progress

- [x] Prověřit reducer, focused tests, review 0923 a relevantní learnings.
- [x] Vymezit implementační a ověřovací kroky.

## Analysis

- `audit_lifecycle_observations.py` zahazuje terminál bez `run_id`, přijímá pro `AttemptStarted` jen `attempt_number` a kontroluje konfliktní `(event_id, sequence)` až uvnitř odvozených skupin.
- Canonical `AttemptFinished` používá `run_id` + `attempt_no` + `attempt_status`. Canonical `AttemptStarted` neposílá `legacy attempt_number`; rozporné dodané ordinal hodnoty nesmí vybrat legacy hodnotu.
- Review `plans/checkpoints/monitoring-parallel-20261020/lifecycle-review-0923.md` chybnou diagnózu dvou různých validních attempt čísel v témže runu výslovně neopakovat: samostatné pokusy nejsou samy o sobě konflikt.
- Zachovat stávajících 18 testů/assertions, evidence caller availability, `run_status`, partial coverage, opaque token a zákaz syntetického attemptu z `RunFinished`.
- Relevantní pravidla: `learnings/architecture/2026-10-20_lifecycle-reducer-canonical-attempt-identity-followup.md`, `learnings/architecture/2026-10-20_bounded-audit-lifecycle-summaries-preserve-uncertainty.md`, `learnings/tooling/project-venv-for-contract-pytest-proof.md`, `learnings/tooling/tdd-proof-cycle-validation.md`.

## Approach

- Přidat kompatibilní unscoped/unknown evidence reprezentaci do summary tak, aby AttemptFinished bez `run_id` zůstal viditelný bez domyšlené run identity; zachovat partial/unknown sémantiku.
- Validovat canonical attempt ordinal pole společně. Při rozporu canonical/legacy hodnot nebo jiné contradictory supplied identity nepřiřadit jistý attempt; legacy alias sám nikdy nebude fallback.
- Deduplikovat ekvivalentní stejnou event identitu; při stejném event ID + sequence a rozdílném payloadu uchovat obě evidence jako konflikt. Konflikt řešit napříč scope/attempt groupingem, nikoli zaměňovat za dva legitimní event IDs nebo dvě různá attempt čísla.
- Žádná změna event/store/router ani runtime integrace; žádné absolutní latest inference.

## Implementation

1. V testech nejprve přidat RED případy pro unscoped terminal evidence, canonical/legacy ordinal rozpor, a shodnou event identitu s payloadem měnícím attempt scope/číslo.
2. U identity-conflict případů ověřit obě pořadí vstupu, zachování obou evidence položek, partial coverage a next token; ověřit také dvě různá event ID pro attempt 1/2 jako dva nezávislé validní attempty.
3. Upravit reducer malým public-contract rozšířením a order-independent normalizací/validací; zachovat všechny stávající assertions.
4. Dokončit GREEN a zaznamenat nový proof pouze pod tímto task ID; nepřepisovat staré proof ani verdict.

## Testing

- Genuine RED/GREEN přes skill `tdd`, stejný focused argv a projektový interpreter.
- Focused: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_lifecycle_observations.py`
- Backend suite: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests`
- Registered gates: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; report unrelated failures distinctly.
- Jen source/test evidence: žádné live/runtime/deployment tvrzení.

## TDD

**Test file:** `be-document-processing/tests/test_monitor_lifecycle_observations.py`  
**Framework:** pytest  
**Run command:** `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_lifecycle_observations.py`

Přidat před implementací tyto charakterizační testy. Unscoped evidence pole je součástí zvoleného kompatibilního public summary contractu.

```python
def test_unscoped_attempt_terminal_is_retained_without_inventing_run():
    terminal = event("t", "AttemptFinished", 3, attempt_no=1, attempt_status="failed")
    result = lifecycle.reduce_observations([terminal], next_token="cursor")
    assert result.runs == ()
    assert result.attempts == ()
    assert result.unscoped_evidence == (lifecycle.Evidence("t", 3, "AttemptFinished"),)  # RED: currently discarded
    assert result.coverage == "partial" and result.next_token == "cursor"


def test_contradictory_started_ordinals_do_not_select_legacy_number():
    started = event("s", "AttemptStarted", 2, run_id="r", attempt_no=1, attempt_number=2)
    result = lifecycle.reduce_observations([started], next_token=None)
    assert result.attempts == ()  # RED: currently summarizes attempt_number=2 as certain


def test_same_event_identity_conflict_across_attempt_scope_is_order_independent():
    first = event("t", "AttemptFinished", 3, run_id="r", attempt_no=1, attempt_status="failed")
    conflict = event("t", "AttemptFinished", 3, run_id="r", attempt_no=2, attempt_status="failed")
    for observations in ([first, conflict], [conflict, first]):
        result = lifecycle.reduce_observations(observations, next_token="opaque")
        assert result.coverage == "partial" and result.next_token == "opaque"
        assert len(result.conflicts) == 1  # RED: conflict currently split into certain attempts
        assert len(result.conflicts[0].evidence) == 2
```

| Test | RED | GREEN |
|---|---|---|
| Unscoped terminal | No retained public evidence | Evidence retained without run/attempt identity |
| Contradictory started ordinals | Legacy value creates certain attempt 2 | No certain attempt selected |
| Conflict across attempt scope, both orders | Identity conflict split into certain groups | One conflict with both evidence entries; token/partial preserved |

Implement genuine RED/GREEN according to skill `tdd`; do not broaden the owned file set.

## Files

| File | Change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_lifecycle_observations.py` | Preserve unscoped evidence; validate contradictory ordinal identity; retain identity conflicts independent of order/scope. |
| `be-document-processing/tests/test_monitor_lifecycle_observations.py` | Add focused characterization cases while retaining current assertions. |
| `plans/2026-10-20_task-59a2a44c-6136-465a-b2a7-2be7a6a6911a_monitoring-lifecycle-zachovat-unscoped-evidence-a-odm-tnout.md` | This plan. |
