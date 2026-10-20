# Plan 2026-10-20: Monitoring MVP – čisté mapování omezeného okna page observations

Vytvořit čistý, content-free mapper konečného observation okna, který zachová pouze doložené allowlisted page event fields a scope.

## Analysis

- `audit/audit_events.py` poskytuje vzor explicitního allowlistu v `to_item`; zatím definuje pouze FileReceived.
- Kontrakty: `plans/tasks/2026-10-20_monitor-mvp-12-page-outcome-events.md`, `13-attempt-pages-get.md`, `14-cache-reused-event.md` a `15-cache-reused-read.md`. Zachovat fragmenty a opakované observations; cache reuse není nové zpracování.
- `audit/audit_storage.py`/`audit_queries.py` a existující storage testy nejsou cílové změny. Mapper nesmí číst store ani udělat další query.
- Relevantní learning `learnings/architecture/2026-10-19_monitoring-filereceived-audit-plan-scope.md`: nepřekračovat schválený úzký audit scope; hermetický test není deployed persistence evidence.
- Recall knowledge: backend `local`, collection `wonderfulkb-learnings` nenalezena; fallback našel uvedený learning. Dostupný skill `tdd` se použije pro RED→GREEN proof.

## Approach

- Přidat jedinou funkci v `audit_page_observations.py`, která přijímá finite `Sequence[Mapping[str, object]]`, explicitní `run_id` a kladný `attempt_no`; vrací nové allowlisted mappings bez mutace vstupu.
- Povolit pouze `StepStarted` se stage `page_transcription`, `PageCompleted`, `PageFailed` a `PageCacheReused`; neznámé typy/stages nepublikovat. Scope mismatch se odfiltruje, malformed scope/observation se bezpečně odmítne.
- Zachovat vstupní pořadí, event identity/type/sequence/time/run/attempt/page/stage a jen konkrétním typu dovolené evidence. Nepřidávat agregaci, syntetické stavy/events, timestamp-derived duration, business Page ani content fields.

## Implementation

1. Dle skill `tdd` nejprve vytvořit focused test skeleton a zachytit RED.
2. Ověřit kontraktní typy a přesný per-event field allowlist; implementovat validaci, filtr scope a kopírování do nových mappings.
3. Spustit focused testy, zachytit GREEN proof; následně registrované test/build gates.
4. Nepřipojovat HTTP/router/I/O, reader, registry ani deployment; výsledek nedeklarovat jako dokončení pages GET.

## Testing

- Focused pytest: `pytest be-document-processing/tests/test_monitor_page_observations.py`
- Pokrýt completed/failed, unknown method/model před budget-call, cache reuse completed/failed, dvě pages/runs/attempts, terminal-only fragments, různá observations téže stránky, absence duplicitního StepFinished, přesný allowlist, input immutability, malformed scope a unknown type/stage.
- Registry gates: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.

## TDD

**Workflow:** Implementace TDD cyklu dle skill:tdd; uložit skutečný RED→GREEN proof do `plans/checkpoints/task-b37c64cd-1783-45e6-8daf-f2e6a04e0954.red-green-proof.md`.

**Test file:** `be-document-processing/tests/test_monitor_page_observations.py`  
**Framework:** pytest, podle existujících Python testů.  
**Run command:** `pytest be-document-processing/tests/test_monitor_page_observations.py`  
**Edit hint:** nový focused test.

```python
import pytest

from document_processing.audit.audit_page_observations import to_page_observations


def test_maps_only_matching_page_observations_and_returns_new_items():
    event = {
        "event_id": "evt-1", "type": "PageCompleted", "sequence": 3,
        "occurred_at": "2026-10-20T12:00:00Z", "run_id": "run-1",
        "attempt_no": 1, "page_number": 2, "stage": "page_transcription",
        "duration_ms": 12, "text": "must not escape",
    }
    original = dict(event)
    result = to_page_observations([event], run_id="run-1", attempt_no=1)
    assert result == [{key: value for key, value in event.items() if key != "text"}]
    assert result[0] is not event
    assert event == original
```

| Test | RED | GREEN |
|---|---|---|
| Matching PageCompleted mapping | Import fails until domain module exists, then fails until mapper/allowlist is implemented | Returns a new mapping with only allowed fields and leaves input untouched |

## Files

| Path | Change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_page_observations.py` | Nový čistý allowlist mapper omezeného okna |
| `be-document-processing/tests/test_monitor_page_observations.py` | Focused TDD contract tests |
| `plans/checkpoints/task-b37c64cd-1783-45e6-8daf-f2e6a04e0954.red-green-proof.md` | RED→GREEN evidence při implementaci |

## Progress

- [x] Určit kanonickou cestu plánu a prozkoumat vstupní kontrakty
- [ ] Implementovat mapper a focused testy přes TDD
- [ ] Zachytit RED→GREEN proof a spustit registrované gates

---
*Created: 2026-10-20*  
*Status: DRAFT*
