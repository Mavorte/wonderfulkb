from fastapi.testclient import TestClient
from test_monitor_file_received import intake  # Explicit local fixture; no shared conftest.
from test_processing_monitor_routes import monitor, HEADERS, event
import base64
import json
from pathlib import Path
from decimal import Decimal
import pytest

URL = "/v1/cases/case-test/processing/documents/doc-test/runs/run-test/steps"


def get(main, url=URL, headers=HEADERS, **params):
    with TestClient(main.app) as client:
        response = client.get(url, params={"attempt_no": 1, **params}, headers=headers)
    assert response.headers["cache-control"] == "private, no-store"
    return response


def step(kind="StepFinished", **extra):
    return event("steps-terminal", type=kind, sequence=7, run_id="run-test",
                 attempt_no=1, stage="source_validation", **extra)


def test_steps_returns_partial_window(monitor):
    main, *_ = monitor
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/cases/case-test/processing/documents/doc-test/runs/run-test/steps",
            params={"attempt_no": 1, "limit": 1},
            headers=HEADERS,
        )
    assert response.status_code == 200
    assert response.json()["coverage"] == "partial"
    assert response.headers["cache-control"] == "private, no-store"


def test_steps_returns_real_terminal_only_observation(monitor):
    main, _, _, _, _, table = monitor
    table.query.return_value = {"Items": [step(duration_ms=Decimal("12.5"))]}
    response = get(main, limit=1)
    assert response.status_code == 200
    assert response.json()["items"] == [{
        "event_id": "steps-terminal", "sequence": 7, "occurred_at": "2026-10-20T10:00:00Z",
        "type": "StepFinished", "stage": "source_validation", "run_id": "run-test",
        "attempt_no": 1, "duration_ms": 12.5}]
    assert set(response.json()) == {"items", "next_token", "observed_at", "coverage"}
    assert response.json()["coverage"] == "partial" and response.json()["observed_at"]
    assert response.json()["next_token"] is None
    table.query.assert_called_once()
    assert table.query.call_args.kwargs["Limit"] == 1
    table.scan.assert_not_called()


def test_allowlist_fragments_and_attempt_scope(monitor):
    main, _, _, _, _, table = monitor
    rows = [step("StepStarted"), step(), step("StepFailed", duration_ms=Decimal("3.5"),
            error_code="SOURCE_VALIDATION_FAILED"),
            {**step(), "run_id": "other-run"}, {**step(), "attempt_no": 2},
            {**step(), "stage": "extraction"},
            {**step("StepStarted"), "stage": "page_transcription", "page_number": 1},
            {**step(), "type": "PageCompleted", "stage": "page_transcription", "page_number": 1}]
    table.query.return_value = {"Items": [dict(row, filename="private", raw_error="private") for row in rows]}
    response = get(main)
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["type"] for item in items] == ["StepStarted", "StepFinished", "StepFailed", "StepFinished", "StepStarted", "PageCompleted"]
    assert "duration_ms" not in items[1]
    assert items[2]["error_code"] == "SOURCE_VALIDATION_FAILED"
    assert items[2]["duration_ms"] == 3.5
    assert items[3]["stage"] == "extraction"
    assert all("page_number" not in item for item in items[:4])
    assert [item["page_number"] for item in items[4:]] == [1, 1]
    assert all(not (set(item) & {"case_id", "document_id", "filename", "raw_error", "status"}) for item in items)
    table.query.assert_called_once()
    import yaml
    from jsonschema import Draft7Validator, RefResolver
    contract = yaml.safe_load((Path(__file__).resolve().parents[2] / "be-document-processing/contracts/openapi-processing-monitor.yaml").read_text())
    validator = Draft7Validator(contract["components"]["schemas"]["StepObservation"], resolver=RefResolver.from_schema(contract))
    for item in items:
        validator.validate(item)


def test_empty_evaluated_continuation_and_scope_bound_tokens(monitor):
    from document_processing.audit.audit_queries import document_key
    main, _, docs, _, policy, table = monitor
    key = {"pk": document_key("case-test", "doc-test"), "sk": "EVENT#evaluated-not-matched"}
    table.query.side_effect = [{"Items": [{**step(), "attempt_no": 2}], "LastEvaluatedKey": key}, {"Items": [step()]}]
    first = get(main, limit=1)
    assert first.status_code == 200 and first.json()["items"] == []
    token = first.json()["next_token"]
    assert token
    second = get(main, limit=1, next_token=token)
    assert second.status_code == 200 and len(second.json()["items"]) == 1
    assert table.query.call_count == 2
    assert table.query.call_args.kwargs["ExclusiveStartKey"] == key
    for field, value in [("run_id", "other-run"), ("attempt_no", 2), ("operation", "pages"),
                         ("reader", "bad"), ("v", True)]:
        data = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
        data[field] = value
        altered = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
        assert get(main, next_token=altered).status_code == 400
    assert get(main, URL.replace("run-test", "other-run"), next_token=token).status_code == 400
    assert get(main, attempt_no=2, next_token=token).status_code == 400
    policy["principals"][0]["case_ids"].append("other-case")
    for field, value in [("document_id", "other-doc"), ("case_id", "other-case")]:
        docs.get_item.return_value = {"Item": {"case_id": "case-test", "document_id": "doc-test", field: value}}
        assert get(main, URL.replace("doc-test" if field == "document_id" else "case-test", value), next_token=token).status_code == 400
    docs.get_item.return_value = {"Item": {"case_id": "case-test", "document_id": "doc-test"}}
    assert get(main, URL.split("/runs/")[0] + "/events", next_token=token).status_code == 400
    assert table.query.call_count == 2
    table.scan.assert_not_called()


@pytest.mark.parametrize("params", [{"attempt_no": None}, {"attempt_no": 0}, {"attempt_no": -1},
    {"attempt_no": "bad"}, {"attempt_no": "1.5"}, {"limit": 0}, {"limit": 101}, {"limit": "bad"},
    {"next_token": ""}, {"next_token": "bad"}, {"next_token": "a" * 8193}])
def test_bad_input_without_query(monitor, params):
    main, _, _, _, _, table = monitor
    assert get(main, **params).status_code == 400
    table.query.assert_not_called()


def test_invalid_run(monitor):
    main, _, _, _, _, table = monitor
    assert get(main, URL.replace("run-test", "invalid$id")).status_code == 400
    table.query.assert_not_called()


@pytest.mark.parametrize("failure", ["missing", "forged", "revoked", "disabled", "foreign", "auth-source", "membership", "missing-doc", "query", "decode"])
def test_fail_closed_and_safe_errors(monitor, failure):
    main, _, docs, source, policy, table = monitor
    headers = HEADERS
    expected = 403
    if failure == "missing": headers = {}
    if failure == "forged": headers = {"Authorization": "Bearer forged", "x-case-id": "case-test"}
    if failure == "revoked": policy["principals"][0]["case_ids"] = []
    if failure == "disabled": policy["principals"][0]["enabled"] = False
    if failure == "foreign": policy["principals"][0]["case_ids"] = ["foreign"]
    if failure == "auth-source": source.side_effect = RuntimeError("private"); expected = 503
    if failure == "membership": docs.get_item.side_effect = RuntimeError("private"); expected = 503
    if failure == "missing-doc": docs.get_item.return_value = {}; expected = 404
    if failure == "query": table.query.side_effect = RuntimeError("private"); expected = 503
    if failure == "decode": table.query.return_value = {"Items": [event(type="Unknown")]}; expected = 503
    response = get(main, headers=headers)
    assert response.status_code == expected
    assert "private" not in response.text
    if failure not in {"query", "decode"}: table.query.assert_not_called()
    if failure in {"missing", "forged", "revoked", "disabled", "foreign", "auth-source"}: docs.get_item.assert_not_called()


def test_retained_tuple_requires_current_grant(monitor):
    main, _, docs, _, policy, table = monitor
    docs.get_item.return_value = {}
    policy["retained_documents"] = [{"case_id": "case-test", "document_id": "doc-test",
        "source_revision": "committed-metadata-v1", "verified_at": "2026-10-20T10:00:00Z"}]
    table.query.return_value = {"Items": [step("StepStarted")]}
    assert get(main).json()["items"][0]["type"] == "StepStarted"
    table.reset_mock()
    policy["principals"][0]["case_ids"] = []
    assert get(main).status_code == 403
    table.query.assert_not_called()


def test_page_projection_matches_pages_once_per_terminal(monitor):
    import yaml
    from jsonschema import RefResolver
    from openapi_schema_validator import OAS30Validator
    main, _, _, _, _, table = monitor
    table.query.return_value = {"Items": [event("completed", sequence=4, type="PageCompleted",
        run_id="run-test", attempt_no=1, stage="page_transcription", page_number=1, method="native"),
        event("failed", sequence=5, type="PageFailed", run_id="run-test", attempt_no=1,
              stage="page_transcription", page_number=2, error_code="PAGE_TRANSCRIPTION_FAILED")]}
    steps = get(main)
    pages = get(main, URL.replace("/steps", "/pages"))
    assert steps.status_code == pages.status_code == 200
    assert steps.json()["items"] == pages.json()["items"]
    assert [item["event_id"] for item in steps.json()["items"]] == ["completed", "failed"]
    contract = yaml.safe_load((Path(__file__).resolve().parents[2] / "be-document-processing/contracts/openapi-processing-monitor.yaml").read_text())
    OAS30Validator(contract["components"]["schemas"]["StepCollection"], resolver=RefResolver.from_schema(contract)).validate(steps.json())
    assert table.query.call_count == 2
