from decimal import Decimal
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from document_processing.audit.audit_queries import read_document
from document_processing.audit.audit_storage import AuditStore


def row(status="partial"):
    return dict(schema_version=1, case_id="case-test", document_id="doc-test",
                event_id="publication-1", sequence=1, type="ResultPublished",
                occurred_at="2026-10-20T10:00:00Z", run_id="run-1",
                attempt_no=1, result_status=status, artifact_ids=["artifact-1"])


def test_bounded_reader_decodes_partial_publication():
    table = Mock()
    table.query.return_value = {"Items": [row()]}
    page = read_document(table, "case-test", "doc-test", limit=1)
    assert page.items[0].to_item() == row()
    assert table.query.call_count == 1


@pytest.mark.parametrize("status", ["completed", "partial", "failed"])
def test_publication_store_round_trip_and_duplicate(status):
    from document_processing.audit.audit_events import ResultPublished
    event = ResultPublished(**row(status))
    table = Mock()
    assert AuditStore(table).put(event) == "inserted"
    stored = table.put_item.call_args.kwargs
    assert stored["ConditionExpression"] == "attribute_not_exists(pk) AND attribute_not_exists(sk)"
    item = dict(stored["Item"], attempt_no=Decimal(1), sequence=Decimal(1), schema_version=Decimal(1))
    table.query.return_value = {"Items": [item]}
    assert AuditStore(table).read_document("case-test", "doc-test").items[0] == event
    table.put_item.side_effect = ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
    assert AuditStore(table).put(event) == "duplicate"


@pytest.mark.parametrize("changes", [{"result_status": "success"}, {"attempt_no": 0},
    {"run_id": ""}, {"artifact_ids": ["https://secret"]}, {"result": "private content"}, {"page_number": 1}])
def test_publication_rejects_invalid_scope_or_content(changes):
    from document_processing.audit.audit_events import ResultPublished
    with pytest.raises((ValueError, TypeError)):
        ResultPublished(**{**row(), **changes})


def test_publish_steps_are_distinct_facts_and_do_not_imply_terminal():
    from document_processing.audit.audit_events import ResultPublished, StepStarted, StepFinished, StepFailed
    from document_processing.audit.audit_lifecycle_observations import reduce_observations
    base = {key: value for key, value in row().items() if key not in {"result_status", "artifact_ids"}}
    events = [StepStarted(**{**base, "type": "StepStarted", "event_id": "start"}, stage="result_publishing"),
              StepFinished(**{**base, "type": "StepFinished", "event_id": "finish"}, stage="result_publishing", duration_ms=0),
              ResultPublished(**row())]
    summary = reduce_observations([event.to_item() for event in events], next_token=None)
    assert summary.runs[0].state == "unknown"
    assert summary.published_results[0].publication_id == "publication-1"
    assert [e.event_id for e in summary.published_results[0].evidence] == ["publication-1"]
    failure = StepFailed(**{**base, "type": "StepFailed", "event_id": "failed"},
                         stage="result_publishing", error_code="RESULT_PUBLISHING_FAILED")
    assert not reduce_observations([failure.to_item()], next_token=None).published_results
