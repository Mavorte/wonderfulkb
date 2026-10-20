import boto3
import pytest
from moto import mock_aws

from document_processing.audit.audit_events import StepStarted, StepFinished, StepFailed
from document_processing.audit.audit_storage import AuditStore


@pytest.fixture
def audit_table():
    with mock_aws():
        table = boto3.resource("dynamodb", region_name="eu-central-1").create_table(
            TableName="extraction-audit",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table


def event(cls, event_id, type_, sequence, **extra):
    return cls(schema_version=1, event_id=event_id, case_id="c", document_id="d",
               sequence=sequence, type=type_, occurred_at=f"2026-10-20T12:00:0{sequence}Z", **extra)


def test_extraction_start_finish_and_failure_roundtrip(audit_table):
    store = AuditStore(audit_table)
    start = event(StepStarted, "start", "StepStarted", 1, run_id="run-1", attempt_no=1, stage="extraction")
    finish = event(StepFinished, "finish", "StepFinished", 2, run_id="run-1", attempt_no=1,
                   stage="extraction", duration_ms=12.5)
    failed = event(StepFailed, "failed", "StepFailed", 3, run_id="run-2", attempt_no=2,
                   stage="extraction", error_code="EXTRACTION_FAILED", duration_ms=0)
    assert store.put(start) == "inserted"
    assert store.put(finish) == "inserted"
    assert store.put(finish) == "duplicate"
    assert store.put(failed) == "inserted"
    assert store.read_document("c", "d", limit=10).items == [failed, finish, start]


@pytest.mark.parametrize("cls,type_,extra", [
    (StepFinished, "StepFinished", {"duration_ms": 1.0}),
    (StepFailed, "StepFailed", {"error_code": "EXTRACTION_FAILED", "duration_ms": 1.0}),
])
def test_terminal_only_and_safe_allowlist(audit_table, cls, type_, extra):
    store = AuditStore(audit_table)
    terminal = event(cls, "terminal", type_, 1, run_id="run-1", attempt_no=1, stage="extraction", **extra)
    assert store.put(terminal) == "inserted"
    raw = audit_table.scan()["Items"][0]
    assert "run_id" in raw and raw["stage"] == "extraction"
    assert "details" not in raw and "fields" not in raw and "occurred_at" in raw


@pytest.mark.parametrize("cls,type_,extra", [
    (StepStarted, "StepStarted", {"attempt_no": 1}),
    (StepStarted, "StepStarted", {"run_id": "r", "attempt_no": 0}),
    (StepStarted, "StepStarted", {"run_id": "r", "attempt_no": 1, "page_number": 1}),
    (StepFinished, "StepFinished", {"run_id": "r", "attempt_no": 1, "duration_ms": float("inf")}),
    (StepFinished, "StepFinished", {"run_id": "r", "attempt_no": 1, "duration_ms": -1}),
    (StepFailed, "StepFailed", {"run_id": "r", "attempt_no": 1, "error_code": "raw business text"}),
])
def test_invalid_extraction_contract_is_rejected(cls, type_, extra):
    expected = TypeError if "run_id" not in extra else ValueError
    with pytest.raises(expected):
        event(cls, "invalid", type_, 1, stage="extraction", **extra)
