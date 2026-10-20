import pytest
import boto3
from moto import mock_aws

from document_processing.audit.audit_events import (
    AttemptFinished, AttemptStarted, RetryEnqueued, RunFinished,
)
from document_processing.audit.audit_storage import AuditStore


@pytest.fixture
def audit_table():
    with mock_aws():
        table = boto3.resource("dynamodb", region_name="eu-central-1").create_table(
            TableName="retry-terminal-audit",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table


def test_retry_enqueued_requires_real_positive_attempt_number():
    event = RetryEnqueued(
        schema_version=1, event_id="evt-retry", case_id="case-1", document_id="doc-1",
        sequence=1, type="RetryEnqueued", occurred_at="2026-10-20T12:00:00Z",
        run_id="run-1", attempt_no=2,
    )
    assert event.to_item()["attempt_no"] == 2


def make_event(cls, event_id, **fields):
    common = dict(schema_version=1, event_id=event_id, case_id="c", document_id="d",
                  sequence=1, type=cls.__name__, occurred_at="2026-10-20T12:00:00Z")
    return cls(**common, **fields)


def test_retry_attempt_and_terminal_fragments_roundtrip_and_deduplicate(audit_table):
    store = AuditStore(audit_table)
    retry = make_event(RetryEnqueued, "e1", run_id="r", attempt_no=2, reason_code="RETRYABLE_FAILURE")
    finished = make_event(AttemptFinished, "e2", run_id="r", attempt_no=1,
                          attempt_status="failed", duration_ms=1.5, error_code="PROCESSING_FAILED")
    later = make_event(AttemptStarted, "e3", run_id="r", attempt_no=2)
    terminal = make_event(RunFinished, "e4", run_id="r", run_status="completed", attempt_no=2)
    for event in (retry, finished, later, terminal):
        assert store.put(event) == "inserted"
    assert store.put(retry) == "duplicate"
    assert store.read_document("c", "d", limit=10).items == [retry, finished, later, terminal]


@pytest.mark.parametrize("status", ["completed", "partial", "failed"])
def test_run_finished_all_outcomes_and_terminal_without_claim(audit_table, status):
    store = AuditStore(audit_table)
    event = make_event(RunFinished, f"e-{status}", run_id="r", run_status=status)
    assert store.put(event) == "inserted"
    assert store.read_document("c", "d").items == [event]
    assert "attempt_no" not in event.to_item()


@pytest.mark.parametrize("kwargs", [
    {"attempt_no": 0}, {"attempt_no": True},
])
def test_retry_rejects_invalid_attempt(kwargs):
    with pytest.raises(ValueError):
        make_event(RetryEnqueued, "e", run_id="r", **kwargs)


@pytest.mark.parametrize("status", ["queued", "unknown"])
def test_terminal_and_attempt_statuses_are_allowlisted(status):
    with pytest.raises(ValueError):
        make_event(AttemptFinished, "e", run_id="r", attempt_no=1, attempt_status=status)
    with pytest.raises(ValueError):
        make_event(RunFinished, "r", run_id="r", run_status=status)


@pytest.mark.parametrize("duration", [-1, float("inf"), float("nan"), True])
def test_attempt_duration_must_be_finite_nonnegative_measurement(duration):
    with pytest.raises(ValueError):
        make_event(AttemptFinished, "e", run_id="r", attempt_no=1,
                   attempt_status="failed", duration_ms=duration)


def test_unknown_sensitive_codes_and_scope_are_rejected():
    with pytest.raises(ValueError):
        make_event(RetryEnqueued, "e", run_id="r", attempt_no=1, reason_code="raw exception")
    with pytest.raises(TypeError):
        make_event(RetryEnqueued, "e", run_id="r", attempt_no=1, page_id="page")


def test_terminal_only_reordered_scopes_and_no_inferred_events(audit_table):
    store = AuditStore(audit_table)
    events = [make_event(RunFinished, "1-terminal", run_id="r1", run_status="failed",
                         error_code="RETRY_EXHAUSTED"),
              make_event(AttemptFinished, "2-attempt", run_id="r2", attempt_no=3,
                         attempt_status="partial", duration_ms=0),
              make_event(RetryEnqueued, "3-retry", run_id="r2", attempt_no=3)]
    for event in events:
        assert store.put(event) == "inserted"
    assert store.put(events[0]) == "duplicate"
    assert store.read_document("c", "d", limit=10).items == events
    assert {item["type"] for item in audit_table.scan()["Items"]} == {item.type for item in events}
    assert "attempt_no" not in events[0].to_item()


@pytest.mark.parametrize("cls,fields", [
    (RetryEnqueued, {"run_id": "", "attempt_no": 1}),
    (RetryEnqueued, {"run_id": "r", "attempt_no": 1, "reason_code": "raw error"}),
    (AttemptFinished, {"run_id": "r", "attempt_no": 0, "attempt_status": "failed"}),
    (AttemptFinished, {"run_id": "r", "attempt_no": 1, "attempt_status": "unknown"}),
    (RunFinished, {"run_id": "r", "run_status": "queued"}),
    (RunFinished, {"run_id": "r", "run_status": "failed", "attempt_no": 0}),
    (RunFinished, {"run_id": "r", "run_status": "failed", "error_code": "provider text"}),
])
def test_invalid_runtime_facts_do_not_mutate_store(audit_table, cls, fields):
    with pytest.raises(ValueError):
        make_event(cls, "bad", **fields)
    assert audit_table.scan()["Items"] == []
