import pytest
from moto import mock_aws
import boto3

from document_processing.audit.audit_events import StepStarted, StepFinished, StepFailed
from document_processing.audit.audit_storage import AuditStore


@pytest.fixture
def audit_table():
    with mock_aws():
        table = boto3.resource("dynamodb", region_name="eu-central-1").create_table(
            TableName="source-validation-audit",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table


def start(event_id="evt-start"):
    return StepStarted(schema_version=1, event_id=event_id, case_id="case-1", document_id="doc-1",
                       sequence=1, type="StepStarted", occurred_at="2026-10-20T12:00:00Z",
                       run_id="run-1", attempt_no=1, stage="source_validation")


def test_source_validation_terminal_only_persists_without_synthetic_start(audit_table):
    store = AuditStore(audit_table)
    terminal = StepFailed(schema_version=1, event_id="evt-failed", case_id="case-1", document_id="doc-1",
                          sequence=2, type="StepFailed", occurred_at="2026-10-20T12:00:02Z",
                          run_id="run-1", attempt_no=1, stage="source_validation", error_code="SOURCE_HASH_MISMATCH")
    assert store.put(terminal) == "inserted"
    page = store.read_document("case-1", "doc-1", limit=10)
    assert [event.event_id for event in page.items] == ["evt-failed"]


def test_start_finish_roundtrip_and_duplicate(audit_table):
    store = AuditStore(audit_table)
    first = start()
    terminal = StepFinished(schema_version=1, event_id="evt-finish", case_id="case-1", document_id="doc-1",
                            sequence=2, type="StepFinished", occurred_at="2026-10-20T12:00:02Z",
                            run_id="run-1", attempt_no=1, stage="source_validation", duration_ms=12.5)
    assert store.put(first) == "inserted"
    assert store.put(terminal) == "inserted"
    assert store.put(terminal) == "duplicate"
    page = store.read_document("case-1", "doc-1", limit=10)
    assert page.items == [terminal, first]  # document Query orders by event_id, not sequence


def test_source_step_readback_preserves_class_and_values(audit_table):
    store = AuditStore(audit_table)
    started = start("evt-regression-1-start")
    finished = StepFinished(
        schema_version=1, event_id="evt-regression-2-finish", case_id="case-1",
        document_id="doc-1", sequence=2, type="StepFinished",
        occurred_at="2026-10-20T12:00:02Z", run_id="run-1", attempt_no=1,
        stage="source_validation", duration_ms=12.5,
    )
    assert store.put(started) == "inserted"
    assert store.put(finished) == "inserted"
    decoded = store.read_document("case-1", "doc-1", limit=10).items
    assert [type(item) for item in decoded] == [StepStarted, StepFinished]
    assert decoded == [started, finished]
    assert all(type(item.attempt_no) is int for item in decoded)


@pytest.mark.parametrize("changes", [
    {"run_id": ""}, {"attempt_no": 0}, {"stage": "other"},
    {"duration_ms": float("nan")}, {"duration_ms": -1},
])
def test_malformed_events_rejected(changes):
    terminal = dict(schema_version=1, event_id="evt", case_id="case-1", document_id="doc-1", sequence=1,
                    type="StepFinished", occurred_at="2026-10-20T12:00:02Z", run_id="run-1",
                    attempt_no=1, stage="source_validation", duration_ms=1.0)
    with pytest.raises(ValueError):
        StepFinished(**{**terminal, **changes})
