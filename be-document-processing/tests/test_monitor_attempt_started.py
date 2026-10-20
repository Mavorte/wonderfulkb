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
    attempt = make_attempt(event_id="evt-z")
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
