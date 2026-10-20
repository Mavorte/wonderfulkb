"""Extraction observations are bounded persisted facts, never inferred outcomes."""
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import RefResolver
from openapi_schema_validator import OAS30Validator

from test_monitor_file_received import intake  # noqa: F401
from test_processing_monitor_routes import monitor, HEADERS, event

DOCUMENT = "/v1/cases/case-test/processing/documents/doc-test"
URL = DOCUMENT + "/runs/run-test/steps"


def get(main, url=URL, headers=HEADERS, **params):
    with TestClient(main.app) as client:
        response = client.get(url, params={"attempt_no": 1, **params}, headers=headers)
    assert response.headers["cache-control"] == "private, no-store"
    return response


def extraction(kind="StepFinished", event_id="extraction-terminal", **extra):
    return event(event_id, type=kind, sequence=7, run_id="run-test",
                 attempt_no=1, stage="extraction", **extra)


def test_extraction_terminal_only_http_observation(monitor):
    main, _, _, _, _, table = monitor
    table.query.return_value = {"Items": [extraction()]}
    response = get(main, limit=1)
    assert response.status_code == 200
    body = response.json()
    assert body["coverage"] == "partial"
    assert body["items"] == [{
        "event_id": "extraction-terminal", "type": "StepFinished", "sequence": 7,
        "occurred_at": "2026-10-20T10:00:00Z", "run_id": "run-test",
        "attempt_no": 1, "stage": "extraction",
    }]
    table.query.assert_called_once()
    assert table.query.call_args.kwargs["Limit"] == 1
    table.scan.assert_not_called()


def test_extraction_empty_window_continuation_and_isolation(monitor):
    from document_processing.audit.audit_queries import document_key
    main, _, _, _, _, table = monitor
    key = {"pk": document_key("case-test", "doc-test"), "sk": "EVENT#other-attempt"}
    table.query.side_effect = [
        {"Items": [{**extraction(), "run_id": "other-run", "attempt_no": 2}], "LastEvaluatedKey": key},
        {"Items": [extraction("StepStarted", "only-start")]},
    ]
    first = get(main, limit=1)
    assert first.status_code == 200 and first.json()["items"] == []
    assert first.json()["coverage"] == "partial" and "status" not in first.json()
    token = first.json()["next_token"]
    assert token
    assert table.query.call_count == 1
    second = get(main, limit=1, next_token=token)
    assert second.status_code == 200
    assert [item["event_id"] for item in second.json()["items"]] == ["only-start"]
    assert "duration_ms" not in second.json()["items"][0]
    assert second.json()["next_token"] is None
    assert table.query.call_args.kwargs["ExclusiveStartKey"] == key
    for url, params in ((URL, {"attempt_no": 2}), (URL.replace("run-test", "other-run"), {}),
                        (URL.replace("/steps", "/pages"), {}), (DOCUMENT + "/events", {}),
                        (DOCUMENT + "/runs/run-test/events", {})):
        assert get(main, url, next_token=token, **params).status_code == 400
    assert get(main, next_token="bad").status_code == 400
    assert table.query.call_count == 2
    table.scan.assert_not_called()


def test_extraction_deeply_nested_cursor_is_bad_request(monitor):
    import base64

    main, _, _, _, _, table = monitor
    # Valid base64 and below both size bounds, but not a valid cursor object.
    token = base64.urlsafe_b64encode(b"[" * 3000 + b"]" * 3000).decode().rstrip("=")
    with TestClient(main.app, raise_server_exceptions=False) as client:
        response = client.get(URL, params={"attempt_no": 1, "next_token": token}, headers=HEADERS)
    assert response.status_code == 400
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json() == {"error": "invalid next_token"}
    table.query.assert_not_called()
    table.scan.assert_not_called()


def test_extraction_duplicate_cursor_scope_is_bad_request(monitor):
    import base64

    from document_processing.audit.audit_queries import document_key

    main, _, _, _, _, table = monitor
    table.query.return_value = {"Items": [], "LastEvaluatedKey": {
        "pk": document_key("case-test", "doc-test"), "sk": "EVENT#last-evaluated"}}
    response = get(main, limit=1)
    assert response.status_code == 200
    token = response.json()["next_token"]
    raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    ambiguous = raw.replace(b'"attempt_no":1', b'"attempt_no":2,"attempt_no":1')
    assert ambiguous != raw
    token = base64.urlsafe_b64encode(ambiguous).decode().rstrip("=")
    response = get(main, limit=1, next_token=token)
    assert response.status_code == 400
    assert response.json() == {"error": "invalid next_token"}
    table.query.assert_called_once()
    table.scan.assert_not_called()


@pytest.mark.parametrize("failure,status", [
    ("missing-auth", 403), ("shared-key", 403), ("revoked", 403), ("missing-doc", 404),
    ("foreign-doc", 404), ("auth-source", 503), ("query", 503), ("decode", 503),
    ("missing-attempt", 400), ("invalid-attempt", 400),
])
def test_extraction_authorization_scope_and_read_errors(monitor, failure, status):
    main, _, docs, source, policy, table = monitor
    table.query.return_value = {"Items": [extraction()]}
    headers, params = HEADERS, {}
    if failure == "missing-auth": headers = {}
    if failure == "shared-key": headers = {"x-api-key": "test-key"}
    if failure == "revoked": policy["principals"][0]["case_ids"] = []
    if failure == "missing-doc": docs.get_item.return_value = {}
    if failure == "foreign-doc": docs.get_item.return_value = {"Item": {"case_id": "other", "document_id": "doc-test"}}
    if failure == "auth-source": source.side_effect = RuntimeError("private-value")
    if failure == "query": table.query.side_effect = RuntimeError("private-value")
    if failure == "decode": table.query.return_value = {"Items": [extraction(duration_ms=Decimal("-1"))]}
    if failure == "missing-attempt": params = {"attempt_no": None}
    if failure == "invalid-attempt": params = {"attempt_no": 0}
    response = get(main, headers=headers, **params)
    assert response.status_code == status
    assert "private-value" not in response.text
    if failure not in {"query", "decode"}: table.query.assert_not_called()
    table.scan.assert_not_called()


@pytest.mark.parametrize("terminal", ["StepFinished", "StepFailed", None])
def test_extraction_facts_parity_privacy_and_schema(monitor, terminal):
    main, _, _, _, _, table = monitor
    rows = [extraction("StepStarted", "start")]
    if terminal:
        extra = {"duration_ms": Decimal("2.5")}
        if terminal == "StepFailed":
            extra["error_code"] = "EXTRACTION_FAILED"
        rows.append(extraction(terminal, "terminal", **extra))
    private = {key: "private-value" for key in (
        "fields", "quotes", "evidence", "labels", "prompt", "result", "raw_error", "counts")}
    table.query.return_value = {"Items": [dict(row, **private) for row in rows] + [
        {**extraction(), "attempt_no": 2}, {**extraction(), "run_id": "other-run"},
        {**extraction(), "stage": "source_validation", "event_id": "source"}]}
    response = get(main)
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["event_id"] for item in items] == [row["event_id"] for row in rows] + ["source"]
    assert "duration_ms" not in items[0]
    if terminal:
        assert items[1]["duration_ms"] == 2.5
        if terminal == "StepFailed":
            assert items[1]["error_code"] == "EXTRACTION_FAILED"
    assert all(not (set(item) & (set(private) | {"page_number", "status", "model_call"})) for item in items)
    assert "private-value" not in response.text
    contract = yaml.safe_load((Path(__file__).resolve().parents[2] /
        "be-document-processing/contracts/openapi-processing-monitor.yaml").read_text())
    validator = OAS30Validator(contract["components"]["schemas"]["StepCollection"],
                               resolver=RefResolver.from_schema(contract))
    validator.validate(response.json())
    observation = OAS30Validator(contract["components"]["schemas"]["StepObservation"],
                                 resolver=RefResolver.from_schema(contract))
    for forbidden in ("page_number", "fields", "status", "model_call"):
        assert not observation.is_valid({**items[0], forbidden: 1})
    for url in (DOCUMENT + "/events", DOCUMENT + "/runs/run-test/events"):
        result = get(main, url)
        assert result.status_code == 200
        selected = [item for item in result.json()["items"] if item["stage"] == "extraction"
                    and item["run_id"] == "run-test" and item["attempt_no"] == 1]
        assert [item["event_id"] for item in selected] == [row["event_id"] for row in rows]
        if terminal:
            assert selected[1]["duration_ms"] == 2.5
            if terminal == "StepFailed":
                assert selected[1]["error_code"] == "EXTRACTION_FAILED"
    assert get(main, URL.replace("/steps", "/pages")).json()["items"] == []
    assert table.query.call_count == 4
    table.scan.assert_not_called()
