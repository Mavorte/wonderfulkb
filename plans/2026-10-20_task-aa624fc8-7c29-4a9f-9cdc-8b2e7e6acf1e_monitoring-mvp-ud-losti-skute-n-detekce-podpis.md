# Plan 2026-10-20: Monitoring MVP: události skutečné detekce podpisů

Rozšířit stávající audit Step kontrakt a úložiště pro pozorované `signature_detection` události, bez integrace produceru nebo změny OCR.

## Analysis

- `audit_events.py` již definuje `StepStarted`, `StepFinished`, `StepFailed`, `_step_values`, stage allowlist a bezpečné error-code allowlisty. Zachovat sdílenou obálku, validaci attemptu a explicitní serializaci.
- `audit_storage.py` dispatchuje známé eventy typovou unií; conditional zápis podle `event_id`, document partition, čas a fail-open výsledek už existují.
- Task `plans/tasks/2026-10-20_monitor-mvp-10-source-validation-events.md` stanovuje odpovídající Step slice hranice; signature návrh přidává pouze stage/status sémantiku.
- Sémantické reference jsou pouze `pipeline.py:114–115` a `signatures.py:153–163`; nepředstavují důkaz workeru v produkci.
- Relevantní learnings: Moto roundtrip musí ověřit `put == inserted`, konkrétní dekódovanou třídu/rovnost a Decimal duration; auditní fail-open může maskovat serializační chybu; Step identity musí zůstat explicitní a producer-owned.

## Approach

- Přidat `signature_detection` do podporovaných Step stages a pouze nezbytné bezpečné error code pro signature failure; nepřidávat event typ ani automatické odvozování statusu.
- Rozšířit `AuditStore.put` event type hint pro stávající Step event varianty jen pokud aktuální typová unie vyžaduje explicitní zápis; zachovat stávající idempotenci a best-effort chování.
- Ponechat identitu `event_id`, `run_id`, kladný `attempt_no` a `occurred_at` jako předané hodnoty. Step event nemá `page_number`.
- Dovolit pouze naměřenou finite nezápornou `duration_ms` na konci a safe `error_code` na failure. Serializovat číslo přes `Decimal(str(value))`; allowlist odmítá podpisy, citace, geometrii, nálezy, počty, provider chyby, S3 klíče, konfiguraci a business objekty.
- Zachovat neznámý/chybějící výsledek jako absenci eventu; auditní kontrakt nevolá detector a nemění OCR status.

## Implementation

1. Vytvořit nejprve focused testy dle TDD skeletonu a zaznamenat skutečné RED.
2. Přidat stage/error code do existujících allowlistů; upravit validaci, dekodér nebo store dispatch pouze pokud testy prokáží potřebu.
3. Ověřit roundtrip a fail-open chování pro completed, returned-failed, raised-failed, completed-empty, disabled a unknown scénáře jako syntetické vstupy bez automatických observations.
4. Spustit focused test, celý `be-document-processing` relevantní test suite a registrovaný gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
5. Zachovat všechny předchozí event kontrakty a gates; neprovádět AWS/inference/deploy.

## Testing

- Fake/Moto: start→completed/failed roundtrip, terminal-only event, event_id duplicate bez druhé mutace, rozdílné run/attempt izolované identity.
- Validace odmítne špatný stage, chybějící/invalid identity, negative/nonfinite duration a nepovolený business payload bez store mutation.
- Syntetické boundary testy ověří výsledková pravidla: pouze skutečně returned `completed` vytváří StepFinished; returned `failed` i zachycená výjimka jsou StepFailed; disabled nevytváří nic; žádný konec nevytváří success.
- NoOp a failing audit boundary nesmí změnit caller výsledek. Ověřit `put == inserted`, načtenou třídu, rovnost a typ/roundtrip duration.

## TDD

**Test file:** `be-document-processing/tests/test_monitor_signature_events.py`  
**Framework:** pytest; použiť existující audit test fixtures/fake či Moto podle okolních testů.  
**Run command:** `pytest be-document-processing/tests/test_monitor_signature_events.py -q`  
**Edit hint:** NEW FILE; importovat `StepStarted`, `StepFinished`, `StepFailed`, `AuditStore` a existující document reader/test fixtures.

```python
from document_processing.audit.audit_events import StepStarted, StepFinished, StepFailed


def test_signature_detection_completed_roundtrip(audit_store, audit_reader):
    started = StepStarted(
        schema_version=1, event_id="sig-start-1", case_id="case-1", document_id="doc-1",
        sequence=1, type="StepStarted", occurred_at="2026-10-20T12:00:00Z",
        run_id="run-1", attempt_no=1, stage="signature_detection",
    )
    finished = StepFinished(
        schema_version=1, event_id="sig-finish-1", case_id="case-1", document_id="doc-1",
        sequence=2, type="StepFinished", occurred_at="2026-10-20T12:00:01Z",
        run_id="run-1", attempt_no=1, stage="signature_detection", duration_ms=12.5,
    )
    assert audit_store.put(started) == "inserted"
    assert audit_store.put(finished) == "inserted"
    items = audit_reader("case-1", "doc-1")
    assert StepFinished.from_item(items[1]) == finished  # RED: signature stage not yet accepted
    assert isinstance(StepFailed, type)
```

| Test | RED | GREEN |
|---|---|---|
| `test_signature_detection_completed_roundtrip` | Constructing the event rejects unsupported `signature_detection` stage | Both events persist and decoded terminal equals original with numeric duration roundtrip |
| terminal-only / idempotence / invalid payload cases | Missing behavioral support, duplicate or invalid item accepted/mutated | Terminal fragment reads independently, duplicate is idempotent, invalid scope/payload never writes |

Implement the TDD cycle using skill:tdd; capture focused RED/GREEN evidence before broader regression tests.

## Files

| File | Change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_events.py` | Allow `signature_detection` stage and safe failure code while retaining strict Step allowlists/validation. |
| `be-document-processing/src/document_processing/audit/audit_storage.py` | Include any newly supported Step event types in the store contract typing; preserve conditional writes and fail-open. |
| `be-document-processing/tests/test_monitor_signature_events.py` | Add focused TDD, Moto/fake roundtrip, idempotence, isolation, invalid-input and synthetic outcome boundary coverage. |

## Progress

- [x] Canonical path and repository contract located
- [x] Relevant audit patterns and constraints recorded
- [x] Implementation and verification steps specified

*Created: 2026-10-20*
