import pytest
import boto3
from moto import mock_aws

from document_processing.audit.audit_events import PageCompleted, PageFailed, StepStarted
from document_processing.audit.audit_storage import AuditStore


@pytest.fixture
def audit_table():
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="eu-central-1").create_table(
            TableName="page-outcome-audit",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )


def page_event(cls, event_id, sequence, **fields):
    return cls(schema_version=1, event_id=event_id, case_id="c", document_id="d",
               sequence=sequence, type=cls.__name__, occurred_at="2026-10-20T12:00:00Z",
               run_id="run-1", attempt_no=1, stage="page_transcription", page_number=1,
               **fields)


def test_page_start_outcomes_and_terminal_only_roundtrip(audit_table):
    store = AuditStore(audit_table)
    events = [page_event(StepStarted, "1-start", 1),
              page_event(PageCompleted, "2-native", 2, method="native", duration_ms=0),
              page_event(PageCompleted, "3-vision", 3, method="vision", model="observed-model", duration_ms=1.5),
              page_event(PageFailed, "4-before-call", 4, error_code="PAGE_TRANSCRIPTION_FAILED")]
    for event in events:
        assert store.put(event) == "inserted"
    assert store.put(events[1]) == "duplicate"
    assert store.read_document("c", "d", limit=10).items == events
    assert len(audit_table.scan()["Items"]) == 4
    assert "method" not in events[-1].to_item() and "model" not in events[-1].to_item()
    assert {item.type for item in store.read_document("c", "d").items} == {"StepStarted", "PageCompleted", "PageFailed"}


@pytest.mark.parametrize("changes", [
    {"attempt_no": 0}, {"page_number": 0}, {"run_id": ""},
    {"stage": "source_validation"}, {"duration_ms": float("inf")},
    {"duration_ms": -1}, {"method": "unknown"}, {"model": "model-without-method"},
    {"method": "vision", "model": "raw provider error: private text"},
    {"error_code": "raw provider exception"}, {"text": "private"},
])
def test_invalid_page_outcome_never_reaches_store(audit_table, changes):
    fields = dict(run_id="run-1", attempt_no=1, stage="page_transcription", page_number=1,
                  error_code="PAGE_TRANSCRIPTION_FAILED")
    with pytest.raises((ValueError, TypeError)):
        PageFailed(schema_version=1, event_id="bad", case_id="c", document_id="d", sequence=1,
                   type="PageFailed", occurred_at="2026-10-20T12:00:00Z", **{**fields, **changes})
    assert audit_table.scan()["Items"] == []


def test_page_outcomes_separate_attempts_pages_and_runs_with_bounded_query(audit_table):
    store = AuditStore(audit_table)
    first = page_event(PageCompleted, "1-a", 1, method="native")
    other_page = PageCompleted(**{**first.__dict__, "event_id": "2-b", "page_number": 2})
    other_attempt = PageFailed(**{**first.__dict__, "event_id": "3-c", "type": "PageFailed",
                                  "attempt_no": 2, "method": None})
    other_run = PageCompleted(**{**first.__dict__, "event_id": "4-d", "run_id": "run-2"})
    for event in (first, other_page, other_attempt, other_run):
        assert store.put(event) == "inserted"
    page = store.read_document("c", "d", limit=2)
    assert page.items == [first, other_page]
    assert store.read_document("c", "d", limit=2, next_token=page.next_token).items == [other_attempt, other_run]
    assert all(type(item.page_number) is int and type(item.attempt_no) is int
               for item in store.read_document("c", "d", limit=10).items)


def test_page_outcome_requires_positive_attempt_and_page_and_page_stage():
    with pytest.raises(ValueError):
        PageCompleted(
            schema_version=1, event_id="evt-1", case_id="case-1", document_id="doc-1",
            sequence=1, type="PageCompleted", occurred_at="2026-10-20T12:00:00Z",
            run_id="run-1", attempt_no=1, stage="page_transcription", page_number=0,
        )
