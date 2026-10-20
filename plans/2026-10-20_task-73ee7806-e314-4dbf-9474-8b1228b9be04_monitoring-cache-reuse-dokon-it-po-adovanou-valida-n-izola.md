# Plan 2026-10-20: Monitoring cache reuse — validační, izolační a fail-open matice

Rozšířit kontraktové testy PageCacheReused; opravit pouze jeho dotčené model/store/read větve, pokud testy odhalí chybu.

## Analysis

- `be-document-processing/tests/test_monitor_cache_reused_events.py` nyní pokrývá jeden failed-status Moto roundtrip a opakovaný zápis.
- `audit_events.py` definuje PageCacheReused; `audit_storage.py` persistuje explicitní event; `audit_queries.py` dispatchuje podle persisted `type`.
- `audit_listener.py` zpřístupňuje pouze `file_received`; nesvědčí o cache producer fail-open volání.
- Relevantní kontext: `plans/monitoring/mvp-reference-20261019.md`, `plans/tasks/2026-10-20_monitor-mvp-12-page-outcome-events.md`, proposal `20261019-150954-c8891f` (slice-cache-reused/signals/instrumentation).
- Learning: integrální DynamoDB `Decimal` převádět přes `from_item` a ověřit skutečným Moto roundtripem (`learnings/architecture/2026-10-20_audit-envelope-decimal-round-trip.md`). Type dispatch, allowlist serializace a starší Python pytest collection gotcha (`learnings/architecture/2026-10-20_audit-event-dispatch-and-pytest-runtime.md`).
- Learning: audit store testy dokazují pouze adapter; netvrdit deployed/producer evidence (`learnings/architecture/2026-10-19_monitoring-filereceived-audit-plan-scope.md`). Producer identity musí být explicitní, nikoli odvozena (`learnings/architecture/2026-10-20_attemptstarted-audit-contract-preserves-producer-identity.md`).

## Approach

- Doplň testovací matici bez předpokladu, že aktuální validace je vadná; odděl existující characterization od nových chybějících asercí.
- Ověř payload allowlist, neúnik obsahu/URL/error, žádné vedlejší Page/Step eventy ani cache/model/S3/environment přístupy při konstrukci.
- Prověř skutečný existující fail-open seam; pojmenuj jeho hranici jako intake `file_received` a odkaž předchozí konkrétní characterization, pokud dostupná. Neodvozuj obecnou cacheproducer garanci.
- Zachovej public API, opaque artifact semantics, `occurred_at` jako jediný persisted time a absenci požadavku na parent eventy.

## Implementation

1. Rozšiř focused testy pro completed/failed, native/vision, absent/unknown model/reference bez environment inference a opaque artifact allowlist.
2. Přidej izolaci run/attempt/page/document; stable event idempotence ověř druhým payloadem odlišným od prvního a zachovej první persisted item.
3. Ověř direct validator odmítnutí missing run, bool/zero/negative/float attempt/page, neplatného stage/status/method/model/payload před zápisem; zachovej rozlišení TypeError/ValueError pro chybějící argumenty.
4. Ověř decimal roundtrip přes Moto i čistý mapping; explicitní store/read dispatch pouze na PageCacheReused.
5. Použij hermetické fake/sentinel spy k ověření absence konstrukčního I/O a vedlejších terminálních eventů. Charakterizuj existující NoOp/failing boundary jen v rozsahu jeho skutečné odpovědnosti.
6. Implementuj TDD dle `skill:tdd`. Při skutečném selhání oprav jen příslušnou PageCacheReused větev v `audit_events.py`, `audit_storage.py` nebo `audit_queries.py`; jinak pouze doplň chybějící characterization.

## Testing

- Python: `cd be-document-processing && .venv/bin/python -m pytest tests/test_monitor_cache_reused_events.py`
- Python regression: `cd be-document-processing && .venv/bin/python -m pytest tests`
- Registrované gates: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`
- Zachovat historii/proof; zaznamenat genuine RED/GREEN nebo poctivé zdůvodnění nepoužitelnosti RED pro již fungující assertion do `plans/checkpoints/task-73ee7806-e314-4dbf-9474-8b1228b9be04.red-green-proof.md` a checkpointu bez executable checkpoint souborů.
- Žádné live/provider/model/deployment/replay testy; hermetické výsledky nejsou důkazem cacheproducer volání.

## TDD

**Workflow:** skill `tdd`; pracovat nejprve v existujícím focused test souboru. Nevyvolávat umělý production/environment RED; u již funkčního chování označit novou assertion jako chybějící coverage a doložit applicability.

**Test file:** `be-document-processing/tests/test_monitor_cache_reused_events.py`  
**Run command:** `cd be-document-processing && .venv/bin/python -m pytest tests/test_monitor_cache_reused_events.py`  
**Edit hint:** rozšířit existující focused testy.

```python
from document_processing.audit.audit_events import PageCacheReused
from document_processing.audit.audit_storage import AuditStore


def test_cache_reused_duplicate_with_changed_payload_keeps_first_item():
    # Reuse the existing Moto table/event fixture; second event shares event_id
    # but differs in cached_status and occurred_at.
    first = PageCacheReused(...)
    changed = PageCacheReused(...)
    assert store.put(first) == "inserted"
    assert store.put(changed) == "duplicate"
    assert store.read_document("case-1", "doc-1").items == [first]
```

| Test | RED / characterization | GREEN |
|---|---|---|
| duplicate with changed payload | RED only if current store overwrites; otherwise record existing behavior and missing coverage without manufacturing failure | original payload remains the sole read result |
| new matrix assertions | Identify only genuine contract mismatch; direct-validator failures are not business fail-open evidence | validation, isolation, serialization, read dispatch and bounded seam characterization pass |

Implementace TDD cyklu dle `skill:tdd`.

## Files

| Path | Planned change |
|---|---|
| `be-document-processing/tests/test_monitor_cache_reused_events.py` | Complete PageCacheReused validation, serialization, isolation, dispatch and boundary characterization matrix |
| `be-document-processing/src/document_processing/audit/audit_events.py` | Conditional PageCacheReused-only fix if assertions expose a model/validator contract defect |
| `be-document-processing/src/document_processing/audit/audit_storage.py` | Conditional PageCacheReused-only persistence fix |
| `be-document-processing/src/document_processing/audit/audit_queries.py` | Conditional PageCacheReused-only read-dispatch fix |
| `plans/checkpoints/task-73ee7806-e314-4dbf-9474-8b1228b9be04.red-green-proof.md` | Genuine TDD applicability and execution evidence |

## Progress

- [x] Resolve canonical plan path and inspect current focused test/seams.
- [ ] Complete the missing validation, isolation, payload, dispatch and boundary matrix.
- [ ] Run focused/full Python and registered backoffice gates; record accurate evidence.
