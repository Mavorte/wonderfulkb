import pytest
from moto import mock_aws
import boto3

from document_processing.audit.audit_events import StepStarted, StepFinished, StepFailed
from document_processing.audit.audit_storage import AuditStore


@pytest.fixture
def audit_table():
    with mock_aws():
        table = boto3.resource("dynamodb", region_name="eu-central-1").create_table(
            TableName="audit-signature-test",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table


def _event(cls, event_id, sequence, **extra):
    values = dict(schema_version=1, event_id=event_id, case_id="case-1", document_id="doc-1",
                  sequence=sequence, type=cls.__name__, occurred_at="2026-10-20T12:00:00Z",
                  run_id="run-1", attempt_no=1, stage="signature_detection")
    values.update(extra)
    return cls(**values)


def test_signature_detection_completed_roundtrip(audit_table):
    store = AuditStore(audit_table)
    started = _event(StepStarted, "sig-start-1", 1)
    finished = _event(StepFinished, "sig-finish-1", 2, duration_ms=12.5)
    assert store.put(started) == "inserted"
    assert store.put(finished) == "inserted"
    items = store.read_document("case-1", "doc-1", limit=10).items
    by_type = {item.type: item for item in items}
    assert StepStarted.from_item(by_type["StepStarted"].to_item()) == started
    assert StepFinished.from_item(by_type["StepFinished"].to_item()) == finished
    assert isinstance(_event(StepFailed, "sig-failed", 3, error_code="SIGNATURE_DETECTION_FAILED"), StepFailed)


def test_signature_terminal_only_and_duplicate(audit_table):
    store = AuditStore(audit_table)
    finished = _event(StepFinished, "terminal", 7, duration_ms=0)
    assert store.put(finished) == "inserted"
    assert store.put(finished) == "duplicate"
    assert store.read_document("case-1", "doc-1", limit=10).items == [finished]


@pytest.mark.parametrize("changes", [
    {"stage": "other"}, {"run_id": ""}, {"attempt_no": 0},
    {"duration_ms": -1}, {"duration_ms": float("inf")},
])
def test_invalid_signature_events_rejected_without_mutation(audit_table, changes):
    store = AuditStore(audit_table)
    values = dict(event_id="invalid", sequence=1, duration_ms=1)
    values.update(changes)
    with pytest.raises(ValueError):
        _event(StepFinished, values.pop("event_id"), values.pop("sequence"), **values)
    assert store.read_document("case-1", "doc-1", limit=10).items == []
