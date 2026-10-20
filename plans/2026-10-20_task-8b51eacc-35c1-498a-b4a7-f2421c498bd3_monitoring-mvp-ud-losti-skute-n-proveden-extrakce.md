# Plan 2026-10-20: Monitoring MVP: události skutečně provedené extrakce

Rozšířit interní auditní event/store kontrakt pro explicitně pozorované extraction kroky bez připojení produceru.

## Analysis

- `audit_events.py` definuje neměnné event dataclasses, validaci a explicitní `to_item`/`from_item` allowlisty.
- `audit_storage.py` zapisuje podmíněně podle event identity a čte dokumentovým Query; zápis je best-effort.
- `test_monitor_run_queued.py` a `test_monitor_audit_storage.py` ukazují Moto roundtrip, duplicate a kompatibilní kontrakty.
- Předchozí `source_validation` slice v `plans/tasks/2026-10-20_monitor-mvp-10-source-validation-events.md` vymezuje stejný Step event model, ale extraction nesmí přebírat jeho nepříslušné předpoklady.
- Learnings: audit nesmí vytvářet execution identity; zachovat event_id idempotenci a skutečný DynamoDB Decimal roundtrip; lokální testy nejsou živý worker/deployment důkaz.
- Nejsou nalezeny PlantUML diagramy pro tento audit kontrakt. Schválené sémantické reference jsou `pipeline.py:104–111` a `LocalExtractor.extract` (read-only).

## Approach

- Přidat jen `StepStarted`, `StepFinished`, `StepFailed` s `stage=extraction`, předanými `run_id`, kladným `attempt_no` a bez `page_number`; nepřidávat povinná pole do společného Step kontraktu.
- Vymezit scope kroku jako case/document/run/attempt/stage; vyžadovat stabilní producer-supplied event_id, bez generování identity auditem.
- Serializovat pouze bezpečnou obálku, finite nezáporné monotonic `duration_ms` na terminálu a bezpečný technický `error_code` jen při selhání. Žádné extracted data, volná details, provider payload, config, prompt či business text.
- Přijímat terminál nezávisle na start/RunQueued/AttemptStarted fragmentech; zachovat conditional duplicate chování, document Query a jediný uložený event timestamp `occurred_at`.
- Význam eventů vychází jen z explicitně předaných observations: start při skutečně započaté práci nad neprázdnými completed pages, finish při pozorovaném úspěšném návratu, failure při zachyceném selhání. Prázdný vstup nevytváří eventy; prázdné fields/not_found nejsou samy o sobě failure.
- Zachovat fail-open business-facing auditní hranici; validační či serializační chyba nesmí změnit caller výsledek ani retry/business klasifikaci.

## Implementation

1. Nejprve vytvořit focused test skeleton a zaznamenat RED podle `skill:tdd`.
2. Implementovat extraction Step event dataclasses, přesnou validaci a explicitní serializaci/deserializaci v `audit_events.py`.
3. Rozšířit store event dispatch/deserialization v `audit_storage.py`, zachovat podmíněný event_id zápis, partition a timestamp invarianty.
4. Ověřit roundtrip, invalid payload bez mutace, duplicate, terminal-only fragment, oddělené attempts/runs a fail-open caller behavior.
5. Spustit všechny Python audit kontrakty a registrovanou gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.

## Testing

- Focused fake/Moto: start/finish a start/failure, terminal-only fragment, duplicate bez změny, oddělené dva pokusy/runy, validace vstupu a audit fail-open.
- Odmítnout missing run_id, neplatný attempt_no, page-scoped extraction, nefinite/záporné duration a raw business payload; ověřit žádnou store mutation.
- Testovat pouze výslovně dodané observations; prázdný seznam completed pages negeneruje skipped/start/success. Nevolat skutečný extractor.
- Regrese zachová `FileReceived`, `RunQueued`, `source_validation`, page/cache kontrakty a registrované gates. Žádné AWS ani deployment/live-write tvrzení.

## TDD

Implementace TDD cyklu dle `skill:tdd`.

**Test file:** `be-document-processing/tests/test_monitor_extraction_events.py`  
**Framework:** pytest + Moto, navazuje na existující audit testy.  
**Run command:** `cd be-document-processing && .venv/bin/python -m pytest tests/test_monitor_extraction_events.py -q`  
**Edit hint:** nový soubor.

```python
import boto3
import pytest
from moto import mock_aws

from document_processing.audit.audit_events import StepStarted, StepFinished, StepFailed
from document_processing.audit.audit_storage import AuditStore


def test_extraction_started_and_finished_roundtrip(audit_table):
    store = AuditStore(audit_table)
    start = StepStarted(schema_version=1, event_id="evt-start", case_id="c", document_id="d",
                        sequence=1, type="StepStarted", occurred_at="2026-10-20T12:00:00Z",
                        run_id="run-1", attempt_no=1, stage="extraction")
    finish = StepFinished(schema_version=1, event_id="evt-finish", case_id="c", document_id="d",
                          sequence=2, type="StepFinished", occurred_at="2026-10-20T12:00:01Z",
                          run_id="run-1", attempt_no=1, stage="extraction", duration_ms=12.5)
    assert store.put(start) == "inserted"
    assert store.put(finish) == "inserted"
    assert store.read_document("c", "d", limit=10).items == [start, finish]
```

| Test | RED | GREEN |
|---|---|---|
| `test_extraction_started_and_finished_roundtrip` | Import/contract is missing before event support | Both typed events persist and read back in order with allowlisted fields |

## Files

| File | Change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_events.py` | Add strict Step event contracts and explicit extraction-safe allowlists |
| `be-document-processing/src/document_processing/audit/audit_storage.py` | Store/read the new event types without changing identity/query semantics |
| `be-document-processing/tests/test_monitor_extraction_events.py` | Focused TDD/Moto contract tests |

## Progress

- [x] Inspect audit contracts and applicable project learnings
- [x] Define scope, invariants, and focused verification
- [ ] Implement after plan approval using the documented TDD cycle
