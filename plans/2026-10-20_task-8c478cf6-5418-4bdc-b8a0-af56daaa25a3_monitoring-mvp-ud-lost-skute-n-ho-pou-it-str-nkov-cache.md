# Plan 2026-10-20: Monitoring MVP — PageCacheReused

Přidat úzce vymezený interní event/store kontrakt pro skutečné opětovné použití načteného a validovaného výsledku stránky.

## Analysis

- `audit_events.py` definuje immutable typované obálky a explicitní `to_item`/`from_item` allowlisty; `AuditStore.put` používá document partition a conditional put dle `event_id`.
- `audit_listener.py` ukazuje fail-open hranici přes konstrukci, validaci i persistenci. Eventové testy používají pytest a Moto; `test_monitor_page_outcome_events.py` je dosavadní stránkový kontrakt.
- Návrh vyžaduje aktuální předaný `run_id`, kladné `attempt_no` a `page_number`, `stage=page_transcription`, `cached_status` completed/failed, cached-only volitelná metadata a pouze známý opaque `artifact_ids`.
- `plans/monitoring/mvp-reference-20261019.md` (sekce 6), proposal `slice-cache-reused` a task `plans/tasks/2026-10-20_monitor-mvp-14-cache-reused-event.md` jsou závazné hranice. `pipeline.py:85–87` je sémantická reference, ne důkaz deployed produceru.
- Learnings: zachovat conditional `event_id` idempotenci a document Query (`learnings/architecture/2026-10-19_monitoring-filereceived-audit-store-scope.md`); převádět integrální DynamoDB `Decimal` při strict round-trip (`2026-10-20_audit-envelope-decimal-round-trip.md`); při dataclass dědičnosti zabránit nepovinnému poli před povinným a duplicitním definicím (`2026-10-20_audit-event-dataclass-inheritance.md`); smluvní test není live producer evidence (`2026-10-20_attemptstarted-audit-contract-preserves-producer-identity.md`). Recall běžel přes local fallback; kolekce QMD chyběla.
- Žádný relevantní PlantUML diagram nalezen. Další použitelné dovednosti: `tdd` pro implementační RED/GREEN cyklus; `validate-implementation` po implementaci.

## Approach

- Přidat samostatný `PageCacheReused` typ se společnou obálkou; explicitně validovat typ, stage, scope, status, cached method/model a bezpečný tvar referencí. Původní run/attempt ani novou execution identitu nepřidávat.
- Serializovat jen schválené pole; zachovat jedno `occurred_at`, document partition, stabilní producer-supplied `event_id` a podmíněný zápis. Duplikát nesmí změnit původní událost.
- Rozšířit fail-open hranici pouze pokud existující integrační cesta konstrukci/validaci nezachytává; nevytvářet žádné OCR, cache/model I/O ani souběžné page/step eventy.
- Zachovat limit na audit kontrakt/store; bez producer hooku, cache změn, HTTP/read úprav, deploymentu či replay.

## Implementation

1. `skill:tdd`: nejprve založit focused test, zachytit RED a důkaz dle skill workflow.
2. Implementovat event validaci a allowlist round-trip v `audit_events.py`; ošetřit integer `Decimal` podle existujícího patternu.
3. Přidat typ do `AuditStore.put` type contract; ověřit idempotentní Moto zápis i čtení přes existující document reader.
4. Pokud je třeba, napojit pouze existující best-effort/fail-open auditní hranici a testovat, že chyba nezmění výsledek volajícího.
5. Spustit focused a package testy, pak registrované projektové gate.

## Testing

- Moto round-trip completed i failed se zachovaným `cached_status`, volitelným neznámým modelem/reference a bez obsahu v uloženém itemu.
- Opakovat stejné `event_id` s konfliktním payloadem: výsledek `duplicate`, původní item beze změny. Ověřit izolaci mezi run/attempt/page a event identity.
- Odmítnout chybějící run, neplatný attempt/page/stage/status/cached payload před jakýmkoli zápisem.
- Ověřit NoOp/failing audit hranici bez změny caller výsledku a žádné vyrobené PageCompleted/PageFailed/Step terminály ani cache/model I/O.
- Příkaz focused: `cd be-document-processing && pytest tests/test_monitor_cache_reused_events.py`; package suite: `cd be-document-processing && pytest`; registrovaná gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- Lokální fake/Moto výsledky dokazují jen kontrakt/store, nikoli skutečnou cache větev ani deployed worker.

## TDD

**Implementační workflow:** vytvořit testovací soubor jako první, spustit jej a zaznamenat RED, implementovat event/store, znovu spustit focused testy pro GREEN a následně regresní gates. Použít `skill:tdd`; uložit RED/GREEN proof do `plans/checkpoints/task-8c478cf6-5418-4bdc-b8a0-af56daaa25a3.red-green-proof.md`.

**Test file:** `be-document-processing/tests/test_monitor_cache_reused_events.py`  
**Framework:** pytest + Moto, podle stávajících audit storage testů.  
**Run command:** `cd be-document-processing && pytest tests/test_monitor_cache_reused_events.py`  
**Edit hint:** nový soubor; skeleton začíná tímto skutečným importem a jedním round-trip assertion:

```python
import boto3
from moto import mock_aws

from document_processing.audit.audit_events import PageCacheReused
from document_processing.audit.audit_storage import AuditStore


def test_cache_reused_roundtrip_preserves_cached_status():
    with mock_aws():
        table = boto3.resource("dynamodb", region_name="eu-central-1").create_table(
            TableName="cache-reused-audit",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"},
                       {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"},
                                  {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        event = PageCacheReused(
            schema_version=1, event_id="cache-use-1", case_id="case-1",
            document_id="doc-1", sequence=1, type="PageCacheReused",
            occurred_at="2026-10-20T12:00:00Z", run_id="run-1", attempt_no=1,
            stage="page_transcription", page_number=1, cached_status="failed",
        )
        store = AuditStore(table)
        assert store.put(event) == "inserted"
        assert store.put(event) == "duplicate"
        assert store.read_document("case-1", "doc-1").items == [event]  # RED: PageCacheReused is not implemented
```

| Test | RED | GREEN |
|---|---|---|
| `test_cache_reused_roundtrip_preserves_cached_status` | Import/type or serialization/reader assertion fails before implementation. | Moto write then read returns the same event, including `cached_status="failed"`; duplicate is idempotent. |

## Files

| File | Change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_events.py` | Add validated PageCacheReused contract and explicit allowlisted round-trip. |
| `be-document-processing/src/document_processing/audit/audit_storage.py` | Accept the new event type in the existing conditional-put store. |
| `be-document-processing/tests/test_monitor_cache_reused_events.py` | Add focused pytest/Moto contract, persistence, validation, and fail-open tests. |

## Progress

- [x] Determine canonical plan path and research event/store patterns and constraints.
- [x] Incorporate relevant architecture rules and registered test gates.
- [x] Specify focused executable RED/GREEN skeleton and implementation boundaries.
- [ ] Implement the task in a separate implementation step.
