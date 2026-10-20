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
                  sequence=3, type="RunQueued", occurred_at="2026-10-20T12:01:00Z", run_id="")
    assert [event.event_id for event in store.read_document("c", "d", limit=10).items] == ["evt-q"]


def test_run_context_persists_only_nonempty_whitelisted_values(audit_table):
    queued = RunQueued(schema_version=1, event_id="evt-q", case_id="c", document_id="d",
                       sequence=2, type="RunQueued", occurred_at="2026-10-20T12:00:00Z",
                       run_id="opaque-run-1",
                       run_context={"source": "approved", "unknown": "discard", "empty": ""})
    assert queued.to_item()["run_context"] == {"source": "approved"}
