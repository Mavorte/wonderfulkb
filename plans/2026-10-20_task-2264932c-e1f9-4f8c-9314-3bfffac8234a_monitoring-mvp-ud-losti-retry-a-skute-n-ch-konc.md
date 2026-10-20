# Plan 2026-10-20: Monitoring MVP — události retry a skutečných konců

Naplánovat rozšíření audit event kontraktu a storage o runtime fakta RetryEnqueued, AttemptFinished a RunFinished; bez runtime producer integrace.

## Progress
- [x] Určit kanonickou cestu plánu.
- [x] Prozkoumat existující audit kontrakty, úložiště a testovací vzory.
- [x] Zapsat TDD implementační kroky a ověřovací brány.

## Analysis
- `audit_events.py` obsahuje explicitní immutable dataclass kontrakty a allowlist serializaci; `RunQueued` je dosud jediný run-scoped typ.
- `audit_storage.py` provádí conditional put podle `event_id` a fail-open převádí validační, serializační i sink chyby na `unavailable`.
- `audit_queries.py` mapuje současné typy při čtení v jedné document-scoped Query; rozšířit dekódování typů bez cross-event kontrol a zachovat FileReceived/RunQueued zpětnou kompatibilitu.
- `audit_listener.py` má NoOp a fail-open hranici pro FileReceived. Úkol nepřidává producenty ani runtime lifecycle hooky.
- Testovací vzor je `be-document-processing/tests/test_monitor_audit_storage.py` (pytest + Moto), doplněný RunQueued kontraktem v `test_monitor_run_queued.py`.
- Relevantní learnings: `2026-10-20_runqueued-store-contract-separate-from-producer.md` (opaque identity, type-aware decoding, `event_id` idempotence, `occurred_at` jediný čas); `2026-10-20_runtime-audit-needs-authoritative-execution-identity.md` (neodvozovat identitu z queue/auditu); `2026-10-20_audit-envelope-decimal-round-trip.md` (převod pouze integrálních DynamoDB Decimal); `2026-10-20_bounded-audit-lifecycle-summaries-preserve-uncertainty.md` (udržet nejistotu a hranici producenta).
- Recall použil local fallback, protože kolekce QMD chybí; našel 10 auditně relevantních learnings. Skill discovery: pro implementaci použít `tdd` pro zachycený RED/GREEN cyklus; `run-and-debug-app-tests` pouze pokud bude potřeba diagnostikovat testovací běh.

## Approach
- Přidat tři explicitní typy událostí se společnou dokumentovou obálkou, striktními povinnými poli a type-specific allowlisty; `attempt_no` musí být skutečný kladný ordinal, `duration_ms` pouze finite a nezáporné.
- RetryEnqueued vyžaduje doložený attempt, ale store žádný retry ani claim nevyrábí; AttemptFinished není terminální pro run; RunFinished dovoluje absenci attempt scope, pokud neexistuje skutečný claim.
- Bezpečné volitelné `reason_code`/`error_code` akceptovat pouze jako omezené kódy; žádné raw payloady, exception/config dumpy, page scope ani kopie jobu.
- Zachovat best-effort `put`, conditional idempotenci, document partition a `occurred_at`; serializace validuje před zápisem, bez sekvenční identity, SQS receive count nebo cross-event existence/state-machine checků.
- Přijímat reorder i terminal-only fragmenty a zachovat dekódování starších typů při stejné bounded document query.

## Implementation
- První krok implementace: vytvořit `test_monitor_retry_terminal_events.py`, zachytit skutečný RED přes `skill:tdd` a teprve potom doplnit minimum implementace.
- Testy s Moto ověří zápis/čtení retry, dokončený attempt následovaný pozdějším jiným AttemptStarted, všechny run outcome statusy, terminal bez pokusu, terminal-only/reordered data, duplicate `event_id` a izolaci dokumentů.
- Negativní testy odmítnou neznámé typy/statusy/scope, nekladný či bool `attempt_no`, nefinite/záporné duration a nepovolený payload; ověří, že chyba validace/serializace v audit hranici neovlivní caller.
- Ověřit, že store nevyrábí RetryEnqueued, claim/AttemptStarted ani RunFinished z jiných událostí; zachovat stávající NoOp/failing audit boundary a všechny předešlé kontrakty/gates.
- Nepřidávat producer hooky, enqueue/claim/retry/lease/fencing změny, outbox/recovery/replay, cloud/model/deploy, projekce ani index.

## Testing
- Focused TDD command: `be-document-processing/.venv/bin/python -m pytest be-document-processing/tests/test_monitor_retry_terminal_events.py -q` spuštěný z kořene projektu (ověřit existenci použitelného package venv před během).
- Po GREEN spustit registrovanou bránu z injected project context: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; Python package testy zůstávají focused na nový audit slice a případně příslušné starší audit testy.
- Žádný live retry ani AWS experiment; Moto/fake dokazuje pouze lokální store kontrakt, nikoli deployed worker/producers.

## TDD
**Workflow:** použít `skill:tdd`; najprve zapsat test, jednou zachytit RED, implementovat, stejný argv zachytit GREEN. Zachovat proof helperem pod `plans/checkpoints/task-2264932c-e1f9-4f8c-9314-3bfffac8234a.red-green-proof.md`.

**Test file:** `be-document-processing/tests/test_monitor_retry_terminal_events.py`  
**Framework:** pytest + Moto, shodně s existující audit storage sadou.  
**Run command:** `be-document-processing/.venv/bin/python -m pytest be-document-processing/tests/test_monitor_retry_terminal_events.py -q`  
**Edit hint:** NEW FILE; nejprve přidat kontraktové skeleton testy, před změnou produkčního kódu.

```python
import pytest
from document_processing.audit.audit_events import RetryEnqueued


def test_retry_enqueued_requires_real_positive_attempt_number():
    event = RetryEnqueued(
        schema_version=1, event_id="evt-retry", case_id="case-1", document_id="doc-1",
        sequence=1, type="RetryEnqueued", occurred_at="2026-10-20T12:00:00Z",
        run_id="run-1", attempt_no=2,
    )
    assert event.to_item()["attempt_no"] == 2  # RED: RetryEnqueued contract does not exist yet
```

| Test | RED | GREEN |
|---|---|---|
| `test_retry_enqueued_requires_real_positive_attempt_number` | import/contract missing | emits approved `attempt_no=2` in serialized event |
| lifecycle and persistence parametrizations | new event constructors/decoder unavailable | retry, attempt and run outcomes round-trip with conditional duplicate idempotence |
| invalid contract and scope cases | no validators for new types | invalid type/status/scope/duration/raw payload rejected |
| fail-open/storage invariants | new behavior not present | no caller impact; store creates no lifecycle facts or state |

## Files
| Path | Planned change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_events.py` | Add RetryEnqueued, AttemptFinished, RunFinished contracts; strict validation and explicit serialization/deserialization allowlists. |
| `be-document-processing/src/document_processing/audit/audit_storage.py` | Accept the expanded audit-event union while preserving fail-open validation/serialization/write and conditional event_id idempotency. |
| `be-document-processing/src/document_processing/audit/audit_queries.py` | Decode new event types from the existing bounded document query; preserve older event decoding and allow fragments/reordering. |
| `be-document-processing/src/document_processing/audit/audit_listener.py` | Only adjust if needed to preserve/test the existing fail-open boundary; add no lifecycle producers or worker integration. |
| `be-document-processing/tests/test_monitor_retry_terminal_events.py` | Add focused pytest/Moto contract, serialization, lifecycle-fragment, idempotence, scope and fail-open tests. |

## Files
