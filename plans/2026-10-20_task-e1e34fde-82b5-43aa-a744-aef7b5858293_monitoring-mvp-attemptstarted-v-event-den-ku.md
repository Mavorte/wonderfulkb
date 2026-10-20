# Plan 2026-10-20: Monitoring MVP — AttemptStarted v event deníku

Rozšířit interní audit event/store kontrakt o AttemptStarted při zachování producerem dodané identity a stávající idempotence/Query.

## Analysis

- `audit_events.py` má společnou neměnnou obálku `FileReceived`; `RunQueued` ji rozšiřuje explicitním `run_id` a filtrováním polí při serializaci.
- `audit_storage.py` zapisuje přes `event.to_item()` a conditional put podle dokumentového pk/event_id sk. `audit_queries` dnes vrací dekódované eventy přes dokumentový Query.
- `test_monitor_run_queued.py` je vzor pro Moto round-trip a kompatibilitu FileReceived.
- `live-trigger-evidence-20261019.md`: žádný doložený claim attempt counter ani run_id v živé cestě. Změna přijímá výhradně hodnoty od volajícího; nesmí zavádět producer hook, claim ani inference.
- `mvp-reference-20261019.md`: AttemptStarted event/store kontrakt je samostatný slice, nikoliv důkaz producer/live integrace.
- Relevantní learningy: `trigger-audit-execution-identity-contract.md` zakazuje auditní generování identity; `monitoring-audit-runqueued-contract.md` vyžaduje typově dispatchované dekódování a kompatibilitu; `2026-10-20_audit-envelope-decimal-round-trip.md` vyžaduje podporu integrálních DynamoDB Decimal hodnot.
- Recall: local fallback; WonderfulKB learnings kolekce nenalezena.

## Approach

- Přidat `AttemptStarted` jako `FileReceived`-kompatibilní dataclass s povinnými neprázdnými `run_id` a kladným striktním integer `attempt_no` (bool odmítnout); opětovně použít common envelope validaci.
- Uložit pouze explicitní obálku plus run/attempt fields. Rozšířit dekódování existujícího document Query podle uloženého `type`; ponechat event key, conditional idempotenci a pořadí/rozsah Query.
- Zachovat producerem předaný `event_id`; žádná generace run/attempt identity, approximate receive count, audit-count ani mutable timestamp inference.

## Implementation

1. Nejdřív vytvořit cílený test `be-document-processing/tests/test_monitor_attempt_started.py` s reálnými package importy; dle `skill:tdd` zaznamenat RED.
2. Implementovat event validaci, explicitní round-trip serialization/deserialization v `audit_events.py` a type dispatch pro současnou document read cestu; upravit store jen pokud jeho typové rozhraní vyžaduje změnu, bez změny conditional put.
3. Ověřit Moto round-trip společně s FileReceived/RunQueued, duplicate bez navýšení počtu, neplatné identity bez mutation a oddělené runy/pokusy.
4. Spustit registrovanou bránu `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.

## Testing

- Focused: `be-document-processing/.venv/bin/python -m pytest be-document-processing/tests/test_monitor_attempt_started.py` (spouštět z rootu, package venv kvůli Python/dependency požadavkům; ověřit dostupnost příkazu před TDD cyklem).
- Regression: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- Fake/Moto důkaz je pouze lokální kontraktový test; neoznačovat jej za producer nebo live-worker důkaz.

## TDD

Test file: `be-document-processing/tests/test_monitor_attempt_started.py`  
Framework: pytest + boto3/moto, podle `test_monitor_run_queued.py`.  
Run command: `be-document-processing/.venv/bin/python -m pytest be-document-processing/tests/test_monitor_attempt_started.py`

Spustitelný RED skeleton (testy spadnou při importu, dokud typ není implementován):

```python
import boto3
import pytest
from moto import mock_aws

from document_processing.audit.audit_events import AttemptStarted, FileReceived, RunQueued
from document_processing.audit.audit_storage import AuditStore


@pytest.fixture
def audit_table():
    with mock_aws():
        table = boto3.resource("dynamodb", region_name="eu-central-1").create_table(
            TableName="wonderfulkb-attemptstarted-audit",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"},
                       {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"},
                                  {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table


def make_attempt(event_id="evt-a", run_id="run-1", attempt_no=1, sequence=3):
    return AttemptStarted(schema_version=1, event_id=event_id, case_id="c", document_id="d",
                          sequence=sequence, type="AttemptStarted",
                          occurred_at="2026-10-20T12:02:00Z", run_id=run_id,
                          attempt_no=attempt_no)


def test_document_roundtrip_keeps_existing_event_types_and_deduplicates(audit_table):
    store = AuditStore(audit_table)
    received = FileReceived(1, "evt-f", "c", "d", 1, "FileReceived", "2026-10-20T12:00:00Z")
    queued = RunQueued(1, "evt-q", "c", "d", 2, "RunQueued", "2026-10-20T12:01:00Z", "run-1")
    attempt = make_attempt()
    assert store.put(received) == "inserted"
    assert store.put(queued) == "inserted"
    assert store.put(attempt) == "inserted"
    assert store.put(attempt) == "duplicate"
    assert store.read_document("c", "d", limit=10).items == [received, queued, attempt]


@pytest.mark.parametrize("changes", [{"run_id": ""}, {"attempt_no": 0},
                                     {"attempt_no": -1}, {"attempt_no": True},
                                     {"attempt_no": 1.5}])
def test_invalid_attempt_identity_is_rejected_without_mutation(audit_table, changes):
    store = AuditStore(audit_table)
    with pytest.raises((TypeError, ValueError)):
        make_attempt(**changes)
    assert store.read_document("c", "d", limit=10).items == []


def test_attempts_are_distinct_by_producer_event_identity_run_and_number(audit_table):
    store = AuditStore(audit_table)
    first = make_attempt(event_id="evt-a", run_id="run-1", attempt_no=1)
    second = make_attempt(event_id="evt-b", run_id="run-1", attempt_no=2, sequence=4)
    other_run = make_attempt(event_id="evt-c", run_id="run-2", attempt_no=1, sequence=5)
    assert [store.put(item) for item in (first, second, other_run)] == ["inserted"] * 3
    assert store.read_document("c", "d", limit=10).items == [first, second, other_run]
```

| Test | RED | GREEN |
|---|---|---|
| Existing event types, AttemptStarted round-trip and duplicate | ImportError: `AttemptStarted` not defined | All three event types read back in sequence; repeat is `duplicate` |
| Missing/invalid run or attempt values | ImportError until type exists; then invalid constructor must fail | ValueError/TypeError before any store mutation |
| Separate attempts and runs | ImportError until type exists | Three producer-identified events are independently stored |

Implementace TDD cyklu dle skill:tdd; pro AttemptStarted nepřidávat nové identity ani live producer tvrzení.

## Files

| Path | Planned change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_events.py` | AttemptStarted model, validation, allowlisted serialization and type-aware decoding. |
| `be-document-processing/src/document_processing/audit/audit_storage.py` | Preserve conditional idempotency; adjust accepted event typing only if necessary. |
| `be-document-processing/tests/test_monitor_attempt_started.py` | Moto contract tests from the TDD skeleton. |

## Progress

- [x] Canonical plan path resolved; references and local contract patterns reviewed.
- [x] Scope and producer-identity boundary incorporated.
- [x] TDD skeleton and registered verification gates specified.
