# Plan 2026-10-20: Monitoring MVP — RunQueued v existujícím event deníku

Přidat interní event/store kontrakt RunQueued a zachovat stávající document-scope čtení a FileReceived kompatibilitu.

## Analysis

- `audit_events.py` serializuje eventy explicitním allowlistem; FileReceived validuje společnou obálku a při čtení převádí integrální DynamoDB `Decimal`.
- `audit_storage.py` používá podmíněný put přes document pk + event_id sk a převádí conditional duplicate na `duplicate`.
- `audit_queries.py` čte jediným bounded document Query; eventy se aktuálně dekódují jako FileReceived, proto typově rozšířit dekódování bez změny query/token contractu.
- `test_monitor_audit_storage.py` ukazuje Moto fixture a stávající storage pattern; nový soustředěný test přidat dle zadání.
- Rozšíření 2 a 3 v `plans/monitoring/mvp-reference-20261019.md` odděluje event/store kontrakt od producenta; vyžaduje reálný run_id a žádný domyšlený hook.
- Relevantní pravidla: auditní envelope má zůstat allowlist; sequence/occurred_at nesmí tvořit idempotence identity; auditní produceru nelze přisuzovat autoritativní execution identity.

## Approach

- Zavést RunQueued jako jediný nový typ se stejnými společnými poli a povinným neprázdným opaque `run_id`; nepřidávat generování či odvozování identity.
- Přidat volitelný kontext pouze přes whitelist schválených neprázdných hodnot; nečíst worker environment a neukládat config/job payload.
- Uložit `run_id` (a povolené kontextové atributy) v explicitním event serializer/deserializer allowlistu; udržet `occurred_at` jako jediný timestamp.
- Rozšířit AuditStore put/read dispatch pro FileReceived i RunQueued; zachovat conditional event_id idempotenci, bounded Query, dokumentové scope a výchozí čtení existujících FileReceived eventů.
- Žádné producer, queue/payload/business schema, run index/projekce, runtime, cloud write ani AWS deployment v tomto slice.

## Implementation

1. Nejprve vytvořit `be-document-processing/tests/test_monitor_run_queued.py` s RED testy níže a zachytit skutečný RED přes `skill:tdd` proof-capture.
2. Implementovat RunQueued konstruktor/validaci, explicitní allowlist serializaci a robustní from-item převod DynamoDB numeric polí.
3. Rozšířit AuditStore write/read type handling; ověřit RunQueued roundtrip při zachování FileReceived čtení.
4. Přidat testy duplicate event_id bez další události, run_id chybějící/neplatný odmítnut před mutation a kontext whitelistu včetně vynechání neznámých hodnot.
5. Zachytit GREEN stejným focused příkazem; pak spustit package test suite a registrované gates beze změny.

## Testing

- Focused: `pytest -q tests/test_monitor_run_queued.py` (cwd `be-document-processing`). Moto/fake only; žádný AWS/cloud.
- Pokrýt FileReceived i RunQueued put/read roundtrip, duplicate idempotenci, chybějící run_id bez mutation a context whitelist.
- Regrese: `pytest` z package root.
- Registrované gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.

## TDD

**Test file:** `be-document-processing/tests/test_monitor_run_queued.py`  
**Framework:** pytest + Moto (stávající audit storage fixture pattern).  
**Run command:** `pytest -q tests/test_monitor_run_queued.py` (cwd `be-document-processing`).

Skeleton — reálné importy/API po prvním RED přizpůsobit stávajícím stylem:

```python
import boto3
import pytest
from moto import mock_aws

from document_processing.audit.audit_events import FileReceived, RunQueued
from document_processing.audit.audit_storage import AuditStore


@pytest.fixture
def audit_table():
    with mock_aws():
        table = boto3.resource("dynamodb", region_name="eu-central-1").create_table(
            TableName="wonderfulkb-runqueued-audit",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"},
                       {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"},
                                  {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table


def test_run_queued_roundtrip_and_file_received_compatibility(audit_table):
    store = AuditStore(audit_table)
    # RED: RunQueued symbol/contract is not implemented yet.
    queued = RunQueued(schema_version=1, event_id="evt-q", case_id="c", document_id="d",
                       sequence=2, type="RunQueued", occurred_at="2026-10-20T12:00:00Z",
                       run_id="opaque-run-1", run_context={"source": "approved"})
    received = FileReceived(schema_version=1, event_id="evt-f", case_id="c", document_id="d",
                            sequence=1, type="FileReceived", occurred_at="2026-10-20T11:00:00Z")
    assert store.put(received) == "inserted"
    assert store.put(queued) == "inserted"
    assert store.read_document("c", "d", limit=10).items == [received, queued]


def test_run_queued_duplicate_and_required_identity(audit_table):
    store = AuditStore(audit_table)
    queued = RunQueued(schema_version=1, event_id="evt-q", case_id="c", document_id="d",
                       sequence=2, type="RunQueued", occurred_at="2026-10-20T12:00:00Z",
                       run_id="opaque-run-1")
    assert store.put(queued) == "inserted"
    assert store.put(queued) == "duplicate"
    with pytest.raises((TypeError, ValueError)):
        RunQueued(schema_version=1, event_id="evt-bad", case_id="c", document_id="d",
                  sequence=3, type="RunQueued", occurred_at="2026-10-20T12:01:00Z",
                  run_id="")
    assert [event.event_id for event in store.read_document("c", "d", limit=10).items] == ["evt-q"]


def test_run_context_persists_only_nonempty_whitelisted_values(audit_table):
    # RED: context validation/serialization contract is not implemented yet.
    queued = RunQueued(schema_version=1, event_id="evt-q", case_id="c", document_id="d",
                       sequence=2, type="RunQueued", occurred_at="2026-10-20T12:00:00Z",
                       run_id="opaque-run-1",
                       run_context={"source": "approved", "unknown": "discard", "empty": ""})
    item = queued.to_item()
    assert item["run_context"] == {"source": "approved"}
```

| Test | RED | GREEN |
|---|---|---|
| `test_run_queued_roundtrip_and_file_received_compatibility` | Missing RunQueued contract/type-aware read assertion | Both event types roundtrip, FileReceived remains readable |
| `test_run_queued_duplicate_and_required_identity` | RunQueued absent or identity validation missing | Duplicate returns duplicate; invalid identity rejected without extra stored item |
| `test_run_context_persists_only_nonempty_whitelisted_values` | Context whitelist not implemented | Only approved nonempty context fields persist |

Implement the TDD cycle using skill:tdd; store captured proof at `plans/checkpoints/task-db71cc4e-dc83-4457-8119-8bf72e2fa1a7.red-green-proof.md`.

## Files

| Path | Change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_events.py` | RunQueued contract, validation and explicit safe serialization/deserialization |
| `be-document-processing/src/document_processing/audit/audit_storage.py` | Accept and preserve RunQueued through existing put/read store path |
| `be-document-processing/src/document_processing/audit/audit_queries.py` | Decode supported event types from the same bounded document Query |
| `be-document-processing/tests/test_monitor_run_queued.py` | Focused Moto roundtrip, idempotency, identity and whitelist tests |

## Progress

- [x] Resolve canonical plan path and load compound-plan workflow
- [x] Inspect reference, audit implementation and related learnings
- [x] Define focused TDD skeleton and scope boundaries
- [ ] Implement the planned source and test changes (separate implementation task)
