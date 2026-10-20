from fastapi.testclient import TestClient
from test_monitor_file_received import intake  # noqa: F401 - explicit module-local pytest fixture
from test_processing_monitor_routes import monitor, HEADERS, event
import base64
import json
from pathlib import Path
from decimal import Decimal
import pytest

URL = "/v1/cases/case-test/processing/documents/doc-test/runs/run-test/pages"


def get(main, url=URL, headers=HEADERS, **params):
    with TestClient(main.app) as client:
        response = client.get(url, params={"attempt_no": 1, **params}, headers=headers)
    assert response.headers["cache-control"] == "private, no-store"
    return response


def page(kind="PageCompleted", **extra):
    return event("pages-terminal", type=kind, sequence=7, run_id="run-test",
                 attempt_no=1, stage="page_transcription", page_number=1, **extra)


def test_pages_endpoint_returns_partial_observations(monitor):
    main, *_ = monitor
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/cases/case-test/processing/documents/doc-test/runs/run-test/pages?attempt_no=1&limit=1",
            headers=HEADERS,
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert set(response.json()) == {"items", "next_token", "observed_at", "coverage"}
    assert response.json()["coverage"] == "partial"


def test_pages_returns_real_terminal_only_observation(monitor):
    from document_processing.audit.audit_events import PageCompleted
    main, _, _, _, _, table = monitor
    terminal = PageCompleted(**page(method="native", duration_ms=12.5))
    table.query.return_value = {"Items": [terminal.to_item()]}
    response = get(main, limit=1)
    assert response.status_code == 200
    assert response.json()["items"] == [{
        "event_id": "pages-terminal", "sequence": 7, "type": "PageCompleted",
        "occurred_at": "2026-10-20T10:00:00Z", "run_id": "run-test",
        "attempt_no": 1, "stage": "page_transcription", "page_number": 1,
        "method": "native", "duration_ms": 12.5}]
    assert response.json()["observed_at"] and response.json()["next_token"] is None
    table.query.assert_called_once()
    assert table.query.call_args.kwargs["Limit"] == 1
    table.scan.assert_not_called()


def test_two_pages_distinct_observations_and_exact_contract(monitor):
    import yaml
    from jsonschema import RefResolver
    from openapi_schema_validator import OAS30Validator
    main, _, _, _, _, table = monitor
    rows = [page("StepStarted"), page(duration_ms=Decimal("12.5"), method="vision", model="observed-model"),
            {**page("PageFailed", error_code="PAGE_TRANSCRIPTION_FAILED", duration_ms=Decimal("1.5")),
              "event_id": "failed-2", "page_number": 2},
            {**page("PageCacheReused", cached_status="completed"), "event_id": "reused-1"}]
    mixed = [event(), {**page(), "run_id": "other-run"}, {**page(), "attempt_no": 2},
             event("other-stage", type="StepStarted", run_id="run-test", attempt_no=1, stage="extraction")]
    table.query.return_value = {"Items": [dict(row, text="private", markdown="private", blocks=[],
        tables=[], warnings=["private"], content_url="private") for row in rows + mixed]}
    response = get(main, limit=100)
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["type"] for item in items] == ["StepStarted", "PageCompleted", "PageFailed", "PageCacheReused"]
    assert [item["page_number"] for item in items] == [1, 1, 2, 1]
    assert items[1]["method"] == "vision" and items[1]["model"] == "observed-model"
    assert "method" not in items[2] and "model" not in items[2]
    assert "duration_ms" not in items[0]
    assert "private" not in response.text
    contract = yaml.safe_load((Path(__file__).resolve().parents[2] / "be-document-processing/contracts/openapi-processing-monitor.yaml").read_text())
    validator = OAS30Validator(contract["components"]["schemas"]["PageCollection"], resolver=RefResolver.from_schema(contract))
    validator.validate(response.json())
    table.query.assert_called_once()
    assert table.query.call_args.kwargs["Limit"] == 100
    table.scan.assert_not_called()


def test_empty_evaluated_continuation_and_scope_bound_tokens(monitor):
    from document_processing.audit.audit_queries import document_key
    main, _, docs, _, policy, table = monitor
    key = {"pk": document_key("case-test", "doc-test"), "sk": "EVENT#evaluated-not-matched"}
    table.query.side_effect = [{"Items": [event()], "LastEvaluatedKey": key}, {"Items": [page()]}]
    first = get(main, limit=1)
    assert first.status_code == 200 and first.json()["items"] == []
    assert table.query.call_count == 1
    token = first.json()["next_token"]
    assert token
    second = get(main, limit=1, next_token=token)
    assert second.status_code == 200 and len(second.json()["items"]) == 1
    assert table.query.call_args.kwargs["ExclusiveStartKey"] == key
    assert table.query.call_args.kwargs["ConsistentRead"] is True
    for field, value in [("run_id", "other-run"), ("attempt_no", 2), ("attempt_no", True),
                         ("operation", "steps"), ("operation", "document_events"),
                         ("reader", "bad"), ("version", True), ("extra", 1)]:
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
    assert get(main, URL.replace("/pages", "/steps"), next_token=token).status_code == 400
    assert get(main, URL.split("/runs/")[0] + "/events", next_token=token).status_code == 400
    assert table.query.call_count == 2
    table.scan.assert_not_called()


@pytest.mark.parametrize("params", [{"attempt_no": None}, {"attempt_no": 0}, {"attempt_no": -1},
    {"attempt_no": "bad"}, {"attempt_no": "1.5"}, {"limit": 0}, {"limit": 101}, {"limit": "bad"},
    {"next_token": ""}, {"next_token": "bad"}, {"next_token": "a" * 4097}])
def test_bad_input_without_query(monitor, params):
    main, _, _, _, _, table = monitor
    assert get(main, **params).status_code == 400
    table.query.assert_not_called()


def test_invalid_run(monitor):
    main, _, _, _, _, table = monitor
    assert get(main, URL.replace("run-test", "invalid$id")).status_code == 400
    table.query.assert_not_called()


@pytest.mark.parametrize("failure", ["missing", "forged", "revoked", "disabled", "foreign", "auth-source",
    "malformed-policy", "membership", "missing-doc", "foreign-doc", "query", "decode", "unconfigured", "projection"])
def test_fail_closed_and_safe_errors(monitor, failure, monkeypatch):
    main, _, docs, source, policy, table = monitor
    headers = HEADERS
    expected = 403
    if failure == "missing": headers = {"x-api-key": "test-key"}
    if failure == "forged": headers = {"Authorization": "Bearer forged", "x-case-id": "case-test"}
    if failure == "revoked": policy["principals"][0]["case_ids"] = []
    if failure == "disabled": policy["principals"][0]["enabled"] = False
    if failure == "foreign": policy["principals"][0]["case_ids"] = ["foreign"]
    if failure == "auth-source": source.side_effect = RuntimeError("private"); expected = 503
    if failure == "malformed-policy": policy["version"] = True; expected = 503
    if failure == "membership": docs.get_item.side_effect = RuntimeError("private"); expected = 503
    if failure == "missing-doc": docs.get_item.return_value = {}; expected = 404
    if failure == "foreign-doc": docs.get_item.return_value = {"Item": {"case_id": "foreign", "document_id": "doc-test"}}; expected = 404
    if failure == "query": table.query.side_effect = RuntimeError("private"); expected = 503
    if failure == "decode": table.query.return_value = {"Items": [event(type="Unknown")]}; expected = 503
    if failure == "unconfigured":
        from document_processing.audit.audit_storage import AuditStore
        main.app.state.processing_monitor_audit_store = AuditStore()
        expected = 503
    if failure == "projection":
        from unittest.mock import MagicMock
        from document_processing.audit.audit_queries import AuditPage
        broken = MagicMock(case_id="case-test", document_id="doc-test", run_id="run-test",
                           attempt_no=1, type="PageCompleted", stage="page_transcription")
        broken.to_item.side_effect = ValueError("private")
        monkeypatch.setattr(main.app.state.processing_monitor_audit_store, "read_document",
                            lambda *a: AuditPage([broken], None))
        expected = 503
    response = get(main, headers=headers)
    assert response.status_code == expected
    assert "private" not in response.text
    if failure not in {"query", "decode", "projection"}: table.query.assert_not_called()
    if failure in {"missing", "forged", "revoked", "disabled", "foreign", "auth-source", "malformed-policy"}: docs.get_item.assert_not_called()


def test_retained_tuple_requires_current_grant(monitor):
    main, _, docs, _, policy, table = monitor
    docs.get_item.return_value = {}
    policy["retained_documents"] = [{"case_id": "case-test", "document_id": "doc-test",
        "source_revision": "committed-metadata-v1", "verified_at": "2026-10-20T10:00:00Z"}]
    table.query.return_value = {"Items": [page("StepStarted")]}
    assert get(main).json()["items"][0]["type"] == "StepStarted"
    table.reset_mock()
    docs.get_item.side_effect = RuntimeError("private")
    assert get(main).status_code == 503
    docs.get_item.side_effect = None
    policy["principals"][0]["case_ids"] = []
    assert get(main).status_code == 403
    table.query.assert_not_called()


def test_page_terminals_are_once_in_real_steps_http(monitor):
    main, _, _, _, _, table = monitor
    table.query.return_value = {"Items": [page("StepStarted"), {**page(), "event_id": "completed"},
        {**page("PageFailed", error_code="PAGE_TRANSCRIPTION_FAILED"), "event_id": "failed", "page_number": 2}]}
    pages = get(main)
    steps = get(main, URL.replace("/pages", "/steps"))
    assert pages.status_code == steps.status_code == 200
    assert steps.json()["items"] == pages.json()["items"]
    assert [item["event_id"] for item in steps.json()["items"]] == ["pages-terminal", "completed", "failed"]
    assert table.query.call_count == 2
