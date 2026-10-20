# Plan 2026-10-20: Monitoring lifecycle — skutečná attempt identita a terminály

Dokončit čisté bounded-window lifecycle odvození podle skutečných retry/terminal eventů a rozšířit úplnou auditní matici bez změny event/store/router kontraktů.

## Analysis

- `be-document-processing/src/document_processing/audit/audit_lifecycle_observations.py` již seskupuje pouze `attempt_id`/`attempt_number` a počítá obecný terminal zvlášť od `attempt_status`; tím selhává canonical `AttemptFinished(run_id, attempt_no, outcome)` i konzistentní historický status.
- `be-document-processing/tests/test_monitor_lifecycle_observations.py` pokrývá šest základních případů, ne canonical scalar map, scope konflikty, availability/read failure ani úplnou ambiguity matici.
- Ověřit přesný nynější serializer a původní event kontrakt: `plans/tasks/2026-10-20_monitor-mvp-22-retry-terminal-events.md`; host-review a původní lifecycle brief jsou vstupní evidence, ne přepisované výstupy.
- Relevant learning: `learnings/architecture/2026-10-20_attemptstarted-audit-contract-preserves-producer-identity.md` — identity dodává producer; nesmí se odvozovat z receive count, audit row ani mutable timestamps. `learnings/architecture/2026-10-20_audit-envelope-decimal-round-trip.md` zdůrazňuje explicitní allowlist a striktní převody.
- TDD skill `tdd`: helper se používá pouze přes `proof-capture.py`; genuine RED musí být assertion failure, stejné argv pro RED/GREEN, vlastní task proof.

## Approach

- Zachovat public reducer API a mapovat jen skutečná canonical pole podle ověřeného `AttemptFinished` serializeru; žádný nový event kontrakt ani fallback cascade. Historické jméno přijmout jen pokud jej výslovně potvrzuje původní kontrakt.
- Jednu konzistentní terminal/status informaci sjednotit; jen odlišné skutečné výsledky nebo neřešitelný scope/status konflikt dávají `ambiguous`/`unknown` s úplnou partial evidence.
- Nededukovat pořadí z `occurred_at`, sequence nebo čísla attempt jako absolutní latest. Deduplikovat stabilní event identity, zachovat reorder/late fragments, orphan a terminal-only evidence; nesyntetizovat start, attempt ani completion celé historie.
- Rozlišit explicitně doložené availability (`not_configured`, `not_instrumented`), `unknown` při absenci a read failure jako error; žádná konfigurace ani producer readiness z absence eventů.
- Reducer zůstane pure: žádný I/O, reader loop, event/store/router/business změny; token beze změny, coverage vždy partial.

## Implementation

1. Ověřit canonical serializer a nynější veřejný scalar map; zkontrolovat dirty state a zachovat cizí práci.
2. Rozšířit pouze focused test soubor tabulkovou maticí: canonical `run_id`/`attempt_no`/`outcome`, konzistentní finished+status, skutečně konfliktní terminals, více runů/pokusů, duplikáty, reorder/late/orphan/terminal-only, missing/conflicting scope/status, result evidence scope, empty continuation, availability/read failure, žádný latest claim ani I/O.
3. Spustit focused test TDD RED přes skill helper; dependency/import/collection failure není RED. Po accepted RED opravit reducer minimální změnou a stejnou argv spustit GREEN.
4. Spustit focused test, celý `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests` a registrované `npm --prefix apps/backoffice test` a `npm --prefix apps/backoffice run build`; unrelated failures zaznamenat odděleně.
5. Uložit vlastní evidence/learning. Pure domain slice nevyžaduje deployment ani live volání.

## TDD

Implementointi on testattava bugikorjaus. Ennen reducerin muuttamista lisää focused-testit:

**Test file:** `be-document-processing/tests/test_monitor_lifecycle_observations.py`  
**Run command:** `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_lifecycle_observations.py`  
**TDD helper:** `TASK_ID=task-e7de471f-9b14-4e3d-99db-15cd8f31d8b5 python3 "$HOME/.config/opencode/skills/tdd/scripts/proof-capture.py" red -- be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_lifecycle_observations.py`; GREEN stejnou argv s příkazem `green`.

```python
from document_processing.audit import audit_lifecycle_observations as lifecycle

def test_attempt_finished_uses_canonical_attempt_no_and_outcome():
    terminal = {
        "event_id": "finished-1", "sequence": 2, "type": "AttemptFinished",
        "run_id": "r", "attempt_no": 1, "outcome": "failed",
    }
    summary = lifecycle.reduce_observations([terminal], next_token=None)
    assert len(summary.attempts) == 1  # RED: current reducer groups only attempt_id
    assert summary.attempts[0].attempt_number == 1
    assert summary.attempts[0].terminal_state == "failed"
```

| Test | RED | GREEN |
|---|---|---|
| Canonical terminal-only `AttemptFinished` | assertion: no attempt is grouped | one attempt, attempt number 1, failed outcome |
| Consistent legacy finished/status evidence (only if contract permits) | falsely ambiguous | one consistent terminal state |
| Conflicting outcomes/scope and missing evidence | incorrect certainty or lost evidence | unknown/ambiguous with partial evidence retained |
| Bounded window, continuation, availability and no-I/O matrix | missing assertions/behavior | partial coverage, opaque token preserved, distinct availability/read failure, no invented history |

Implement the TDD cycle using the loaded `tdd` skill. If the capture capability denies the request, stop and record the exact blocker; do not bypass it. Validate dependencies before proof capture and do not change the test argv between RED and GREEN.

## Testing

- Focused lifecycle file through accepted RED/GREEN proof; require normal assertion-failing RED and passing GREEN.
- Run full Python package suite without excluding failures. Keep unrelated existing collection errors distinct from this slice's focused result.
- Run registered backoffice tests and build. Preserve actual command outcomes and do not relabel failed/inconclusive history.

## Files

| Path | Planned change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_lifecycle_observations.py` | Fix attempt grouping/status reconciliation and scope/evidence uncertainty within the existing pure reducer. |
| `be-document-processing/tests/test_monitor_lifecycle_observations.py` | Add canonical contract and complete ambiguity/availability matrix. |
| `plans/checkpoints/task-e7de471f-9b14-4e3d-99db-15cd8f31d8b5.red-green-proof.md` | Own TDD evidence only; never modify historical proof. |
| `learnings/` | Save implementation learning after completion. |

## Progress

- [x] Resolve required canonical plan location.
- [x] Review current reducer, focused tests, terminal event contract, relevant learning, and TDD interface.
- [ ] Implement only the two owned source/test paths under the new task ID.
- [ ] Capture valid RED/GREEN proof and run all required verification gates.
- [ ] Save a learning and report outcomes.
