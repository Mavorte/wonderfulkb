"""Stored cache observations through the existing bounded, authorized HTTP API."""

import base64
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import RefResolver
from openapi_schema_validator import OAS30Validator

from test_monitor_file_received import intake  # noqa: F401
from test_processing_monitor_routes import monitor, event, get as events_get
from test_processing_monitor_page_routes import get, URL


def reuse(event_id="reuse-observed", **extra):
    return event(event_id, type="PageCacheReused", sequence=7,
                 run_id="run-test", attempt_no=1, stage="page_transcription",
                 page_number=1, cached_status="completed", **extra)


def validate(schema, value):
    path = Path(__file__).resolve().parents[2] / "be-document-processing/contracts/openapi-processing-monitor.yaml"
    contract = yaml.safe_load(path.read_text())
    OAS30Validator(contract["components"]["schemas"][schema],
                   resolver=RefResolver.from_schema(contract)).validate(value)


@pytest.mark.parametrize("status,model", [("completed", "stored-model"), ("failed", None)])
def test_reuse_fragment_survives_pages_and_document_events(monitor, status, model):
    main, _, _, _, _, table = monitor
    row = {**reuse(cached_method="vision", artifact_ids=["opaque-result-1"]), "cached_status": status}
    if model is not None:
        row["cached_model"] = model
    table.query.return_value = {"Items": [dict(row, s3_key="private", text="private", page={"raw": "private"})]}
    response = get(main, limit=1)
    assert response.status_code == 200
    body = response.json()
    assert body["coverage"] == "partial"
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item == {k: v for k, v in row.items() if k not in {"schema_version", "case_id", "document_id"}}
    assert "method" not in item and "model" not in item
    assert "private" not in response.text
    table.query.assert_called_once()
    assert table.query.call_args.kwargs["Limit"] == 1
    table.scan.assert_not_called()
    validate("PageCollection", body)
    document_response = events_get(main)
    document = document_response.json()["items"][0]
    assert document == {**item, "case_id": "case-test", "document_id": "doc-test"}
    validate("DocumentEvent", document)
    run_response = events_get(main, URL.replace("/pages", "/events"))
    assert run_response.status_code == 200
    assert run_response.json()["items"] == [document]
    validate("RunEvent", run_response.json()["items"][0])
    assert get(main, URL.replace("/pages", "/steps")).json()["items"] == []


def test_reuse_and_new_work_keep_distinct_identity_and_scope(monitor, intake):
    main, resource, *_rest, table = monitor
    rows = [reuse(), {**reuse("reuse-2"), "page_number": 2},
            {**reuse("other-attempt"), "attempt_no": 2},
            {**reuse("other-run"), "run_id": "other-run"},
            event("new-completion", type="PageCompleted", run_id="run-test", attempt_no=1,
                  sequence=8, stage="page_transcription", page_number=1, method="native")]
    table.query.return_value = {"Items": rows}
    response = get(main)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "next_token", "observed_at", "coverage"}
    assert [item["event_id"] for item in body["items"]] == ["reuse-observed", "reuse-2", "new-completion"]
    assert [item["type"] for item in body["items"]] == ["PageCacheReused", "PageCacheReused", "PageCompleted"]
    assert all("cached_model" not in item and "artifact_ids" not in item for item in body["items"])
    validate("PageCollection", body)
    assert [item["event_id"] for item in get(main, URL.replace("/pages", "/steps")).json()["items"]] == ["new-completion"]
    assert table.query.call_count == 2
    table.scan.assert_not_called()
    assert intake[3].mock_calls == []  # S3 and any model client boundary are untouched.
    resource.meta.client.transact_write_items.assert_not_called()


@pytest.mark.parametrize("scope", [{"attempt_no": 2}, {"run_id": "other-run"}])
def test_reuse_empty_evaluated_window_keeps_position_and_bound_cursor(monitor, scope):
    from document_processing.audit.audit_queries import document_key
    main, _, docs, _, policy, table = monitor
    key = {"pk": document_key("case-test", "doc-test"), "sk": "EVENT#other-observation"}
    table.query.side_effect = [{"Items": [{**reuse(), **scope}], "LastEvaluatedKey": key},
                               {"Items": [reuse()]}]
    first = get(main, limit=1)
    assert first.status_code == 200 and first.json()["items"] == []
    token = first.json()["next_token"]
    assert token and table.query.call_count == 1
    for field, value in [("operation", "steps"), ("operation", "document_events"),
                         ("attempt_no", 2), ("run_id", "other-run"),
                         ("case_id", "other-case"), ("document_id", "other-doc")]:
        data = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
        data[field] = value
        altered = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
        assert get(main, next_token=altered).status_code == 400
    assert table.query.call_count == 1
    second = get(main, limit=1, next_token=token)
    assert second.status_code == 200
    assert second.json()["items"][0]["event_id"] == "reuse-observed"
    assert table.query.call_args.kwargs["ExclusiveStartKey"] == key
    assert table.query.call_args.kwargs["Limit"] == 1
    assert table.query.call_count == 2
    table.scan.assert_not_called()


@pytest.mark.parametrize("failure,expected", [("missing", 403), ("forged", 403), ("revoked", 403),
    ("foreign", 403), ("scope", 404), ("query", 503), ("decode", 503)])
def test_reuse_retains_authorization_scope_and_read_errors(monitor, failure, expected):
    main, _, docs, _, policy, table = monitor
    table.query.return_value = {"Items": [reuse()]}
    params = {}
    if failure == "missing": params["headers"] = {"x-api-key": "test-key"}
    if failure == "forged": params["headers"] = {"Authorization": "Bearer forged", "x-case-id": "case-test"}
    if failure == "revoked": policy["principals"][0]["case_ids"] = []
    if failure == "foreign": policy["principals"][0]["case_ids"] = ["foreign-case"]
    if failure == "scope": docs.get_item.return_value = {}
    if failure == "query": table.query.side_effect = RuntimeError("private")
    if failure == "decode": table.query.return_value = {"Items": [{**reuse(), "cached_status": "unknown"}]}
    response = get(main, **params)
    assert response.status_code == expected
    assert "private" not in response.text
    if expected != 503: table.query.assert_not_called()
