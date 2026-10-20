"""Signature boundaries are persisted observations, never inferred detector results."""
import base64
import json
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


def signature(kind="StepFinished", event_id="signature-observed", **extra):
    return event(event_id, type=kind, sequence=7, run_id="run-test",
                 attempt_no=1, stage="signature_detection", **extra)


@pytest.mark.parametrize("kind", ["StepStarted", "StepFinished", "StepFailed"])
@pytest.mark.parametrize("duration", [None, Decimal("2.5")])
def test_signature_terminal_fragment_and_event_parity(monitor, kind, duration):
    main, _, _, _, _, table = monitor
    extra = {"error_code": "SIGNATURE_DETECTION_FAILED"} if kind == "StepFailed" else {}
    if duration is not None and kind != "StepStarted":
        extra["duration_ms"] = duration
    row = signature(kind, **extra)
    private = {key: "private-value" for key in (
        "signatures", "geometry", "quotes", "findings", "counts", "results", "config",
        "raw_error", "model_call", "status")}
    table.query.return_value = {"Items": [{**row, **private}]}
    contract = yaml.safe_load((Path(__file__).resolve().parents[2] /
        "be-document-processing/contracts/openapi-processing-monitor.yaml").read_text())
    observation = OAS30Validator(contract["components"]["schemas"]["StepObservation"],
                                 resolver=RefResolver.from_schema(contract))
    expected = {key: value for key, value in row.items()
                if key not in {"schema_version", "case_id", "document_id"}}
    if "duration_ms" in expected:
        expected["duration_ms"] = float(expected["duration_ms"])
    for path in (URL, DOCUMENT + "/events", DOCUMENT + "/runs/run-test/events"):
        response = get(main, path, limit=1)
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"items", "next_token", "observed_at", "coverage"}
        assert body["coverage"] == "partial" and body["observed_at"] and body["next_token"] is None
        wanted = expected if path == URL else {**expected, "case_id": "case-test", "document_id": "doc-test"}
        assert body["items"] == [wanted]
        assert "private-value" not in response.text
        if path == URL:
            OAS30Validator(contract["components"]["schemas"]["StepCollection"],
                           resolver=RefResolver.from_schema(contract)).validate(body)
            observation.validate(body["items"][0])
            for forbidden in (*private, "page_number"):
                assert not observation.is_valid({**expected, forbidden: 1})
    assert get(main, URL.replace("/steps", "/pages")).json()["items"] == []
    assert table.query.call_count == 4
    assert table.query.call_args.kwargs["Limit"] == 50
    table.scan.assert_not_called()


@pytest.mark.parametrize("terminal", [None, "StepFinished", "StepFailed"])
def test_signature_start_and_completed_empty_or_failed_are_only_facts(monitor, terminal):
    main, _, _, _, _, table = monitor
    rows = [signature("StepStarted", "start")]
    if terminal:
        extra = {"error_code": "SIGNATURE_DETECTION_FAILED"} if terminal == "StepFailed" else {}
        rows.append(signature(terminal, "terminal", **extra))
    table.query.return_value = {"Items": rows}
    body = get(main).json()
    assert [item["type"] for item in body["items"]] == [row["type"] for row in rows]
    assert all("status" not in item and "counts" not in item for item in body["items"])
    table.query.assert_called_once()
    table.scan.assert_not_called()


def test_signature_absent_or_disabled_has_no_synthetic_observation(monitor):
    main, _, _, _, _, table = monitor
    table.query.return_value = {"Items": []}
    body = get(main).json()
    assert body["items"] == [] and body["coverage"] == "partial"
    assert "status" not in body
    table.query.assert_called_once()


def test_signature_empty_continuation_evaluated_position_and_isolation(monitor):
    from document_processing.audit.audit_queries import document_key
    main, _, _, _, _, table = monitor
    key = {"pk": document_key("case-test", "doc-test"), "sk": "EVENT#other"}
    table.query.side_effect = [
        {"Items": [{**signature(), "run_id": "other-run"}, {**signature(), "attempt_no": 2}],
         "LastEvaluatedKey": key}, {"Items": [signature()]},
    ]
    first = get(main, limit=2)
    assert first.status_code == 200 and first.json()["items"] == []
    token = first.json()["next_token"]
    assert token and table.query.call_count == 1
    assert table.query.call_args.kwargs["Limit"] == 2
    second = get(main, limit=2, next_token=token)
    assert [item["event_id"] for item in second.json()["items"]] == ["signature-observed"]
    assert second.json()["next_token"] is None
    assert table.query.call_args.kwargs["ExclusiveStartKey"] == key
    assert table.query.call_count == 2
    for field, value in (("case_id", "foreign"), ("document_id", "foreign"),
                         ("run_id", "foreign"), ("operation", "pages"), ("attempt_no", 2)):
        data = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
        data[field] = value
        bad = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
        assert get(main, next_token=bad).status_code == 400
    for path in (DOCUMENT + "/events", DOCUMENT + "/runs/run-test/events", URL.replace("/steps", "/pages")):
        assert get(main, path, next_token=token).status_code == 400
    assert get(main, next_token="bad").status_code == 400
    assert table.query.call_count == 2
    table.scan.assert_not_called()


@pytest.mark.parametrize("failure,status", [
    ("missing-auth", 403), ("shared-key", 403), ("forged", 403), ("revoked", 403),
    ("disabled", 403), ("ungranted", 403), ("missing-doc", 404), ("foreign-doc", 404),
    ("auth-source", 503), ("membership", 503), ("query", 503), ("decode", 503),
    ("nonfinite", 503), ("unsafe-code", 503), ("missing-attempt", 400), ("invalid-attempt", 400),
])
def test_signature_auth_scope_and_required_read_errors(monitor, failure, status):
    main, _, docs, source, policy, table = monitor
    table.query.return_value = {"Items": [signature()]}
    headers, params = HEADERS, {}
    if failure == "missing-auth": headers = {}
    if failure == "shared-key": headers = {"x-api-key": "test-key"}
    if failure == "forged": headers = {"Authorization": "Bearer forged"}
    if failure == "revoked": policy["credentials"] = []
    if failure == "disabled": policy["principals"][0]["enabled"] = False
    if failure == "ungranted": policy["principals"][0]["case_ids"] = []
    if failure == "missing-doc": docs.get_item.return_value = {}
    if failure == "foreign-doc": docs.get_item.return_value = {"Item": {"case_id": "other", "document_id": "doc-test"}}
    if failure == "auth-source": source.side_effect = RuntimeError("private-value")
    if failure == "membership": docs.get_item.side_effect = RuntimeError("private-value")
    if failure == "query": table.query.side_effect = RuntimeError("private-value")
    if failure in {"decode", "nonfinite"}:
        table.query.return_value = {"Items": [signature(duration_ms=Decimal("-1" if failure == "decode" else "NaN"))]}
    if failure == "unsafe-code":
        table.query.return_value = {"Items": [signature("StepFailed", error_code="private-value")]}
    if failure == "missing-attempt": params = {"attempt_no": None}
    if failure == "invalid-attempt": params = {"attempt_no": 0}
    response = get(main, headers=headers, **params)
    assert response.status_code == status
    assert "private-value" not in response.text
    if failure not in {"query", "decode", "nonfinite", "unsafe-code"}:
        table.query.assert_not_called()
    table.scan.assert_not_called()
