# Plan 2026-10-20: Monitoring MVP — source validation events

Přidat úzký interní event/store kontrakt pro předané začátky a výsledky `source_validation`, bez zásahu do workeru či runtime.

## Analysis

### Codebase context
- `audit_events.py` definuje immutable typed eventy s explicitním envelope allowlistem a validací; stávající FileReceived/RunQueued je nutné zachovat.
- `audit_storage.py` zapisuje pod document partition s conditional idempotencí podle `event_id`; čtení používá stávající bounded Query.
- `audit_listener.py` ukazuje fail-open business boundary, zatímco `tests/test_monitor_audit_storage.py` poskytuje pytest/Moto pattern.
- Checked-in validator pipeline je pouze sémantická reference, nikoli doklad živého produceru.

### Relevant documentation
- `plans/monitoring/mvp-reference-20261019.md`, sekce „Rozšíření sekcí 4 a 5“: source-validation event/store je partial observation; samotný event/store není producer slice.
- `plans/monitoring/next-slices-source-seams-20261019.md`: žádné domyšlené identity, globální runtime kontext ani neautorizovaný outbox/runtime design.

### Knowledge base
- `learnings/architecture/2026-10-19_monitoring-filereceived-audit-store-scope.md`: audit store nezakládá oprávnění k producer hooku, API ani deploymentu.
- `learnings/architecture/2026-10-20_audit-envelope-decimal-round-trip.md`: DynamoDB integrální `Decimal` převádět explicitně, neintegální hodnoty odmítnout; zachovat allowlist a round-trip test.

## Approach

- Přidat `StepStarted`, `StepFinished`, `StepFailed` pouze pro `stage=source_validation`; vyžadovat producerem předané `run_id`, kladný `attempt_no` a stabilní `event_id`.
- Zaznamenávat jediný krok config/version/hash/open; validovat `duration_ms` pouze na terminálu jako finite nezápornou naměřenou hodnotu a `error_code` pouze u `StepFailed` z bezpečného technického allowlistu; žádný page number ani volná metadata.
- Persistovat pouze skutečně předané eventy. Přijímat terminal-only fragmenty bez předpokladů o předchozích událostech; zachovat document partition, event_id conditional idempotenci a `occurred_at` jako jediný uložený timestamp.
- Obalit konstrukci/validaci/zápis přes business-facing audit hranici fail-open; přímý validator odmítá malformed událost bez mutace.

## Implementation

1. Nejprve vytvořit `test_monitor_source_validation_events.py` se skutečnými event/store importy a cílenými RED assertions.
2. Doplnit typed event modely a explicitní `to_item`/`from_item` allowlist v `audit_events.py`; normalizovat pouze integrální DynamoDB `Decimal` pro integer pole.
3. Rozšířit `audit_storage.py` jen pokud modelové serialization/readback vyžadují dispatch nových typů; zachovat conditional put, document partition a bounded read beze změny.
4. Přidat či rozšířit fail-open business boundary tak, aby chyby tvorby, validace i zápisu nepropagovaly do calleru; přímý kontraktový validator zůstane striktní.
5. Spustit cílené Python testy a poté všechny registrované gates; neinstalovat hook, měnit business schema ani nasazovat runtime.

## Testing

- Fake/Moto roundtrip `StepStarted → StepFinished` a `StepStarted → StepFailed`, včetně skutečně předané monotónní duration.
- Duplicate `event_id` zachová první persisted item beze změny; terminal-only událost se uloží a přečte bez syntetizovaných začátků.
- Chybějící `run_id`, neplatný attempt, chybný stage a malformed duration jsou odmítnuty před zápisem.
- Raw exception/business obsah a nepovolená pole se neserializují; nezmapovaná chyba používá bezpečný obecný kód.
- No-op i failing audit boundary ponechají výsledek calleru nezměněn; existující FileReceived/RunQueued/AttemptStarted kontrakty zůstávají kompatibilní.
- Hermetické testy dokazují pouze kontrakt/adaptér, nikoli živého produceru ani AWS runtime.
- Projektové gate dle registrovaného kontextu: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.

## TDD

**Test file:** `be-document-processing/tests/test_monitor_source_validation_events.py`  
**Framework:** pytest + Moto, podle existujících audit storage testů.  
**Run command:** `cd be-document-processing && python -m pytest tests/test_monitor_source_validation_events.py -q`

```python
from document_processing.audit.audit_events import StepStarted, StepFinished, StepFailed
from document_processing.audit.audit_storage import AuditStore


def test_source_validation_terminal_only_persists_without_synthetic_start(audit_table):
    store = AuditStore(audit_table)
    terminal = StepFailed(
        schema_version=1, event_id="evt-failed", case_id="case-1", document_id="doc-1",
        sequence=2, type="StepFailed", occurred_at="2026-10-20T12:00:02Z",
        run_id="run-1", attempt_no=1, stage="source_validation", error_code="SOURCE_HASH_MISMATCH",
    )
    assert store.put(terminal) == "inserted"  # RED: StepFailed contract not present yet
    page = store.read_document("case-1", "doc-1", limit=10)
    assert [event.event_id for event in page.items] == ["evt-failed"]  # no fabricated StepStarted
```

| Skeleton assertion | RED before implementation | GREEN after implementation |
|---|---|---|
| Terminal-only `StepFailed` insert | Import/contract unavailable or rejected | One terminal event persists and reads without synthetic history |
| Focused suite contracts | New Step types/validation absent | Roundtrips, duplicate immutability, invalid-input no-write and fail-open tests pass |

Implementace TDD cyklu dle skill:tdd: zaznamenat RED, implementovat nejmenší změnu a ověřit GREEN.

## Files

| Path | Planned change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_events.py` | Přidat typed source-validation events, validaci a explicitní serialization allowlist. |
| `be-document-processing/src/document_processing/audit/audit_storage.py` | Persistovat/načítat nové typy přes stávající idempotentní document partition; pouze nutné dispatch změny. |
| `be-document-processing/src/document_processing/audit/audit_listener.py` | Případně doplnit malou fail-open business-facing událostní hranici. |
| `be-document-processing/tests/test_monitor_source_validation_events.py` | Přidat focused kontraktové a fake/Moto testy. |

## Progress

- [x] Vyřešit kanonickou cestu plánu a načíst relevantní scope, codebase a learnings.
- [x] Zapsat implementační a TDD kroky s explicitními hranicemi scope.
