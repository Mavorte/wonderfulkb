import hashlib
import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from test_monitor_file_received import intake  # noqa: F401
from document_processing.audit.audit_storage import AuditStore


def test_authorized_service_reads_document_events(intake):
    main, _, docs, _, _, _ = intake
    credential = "synthetic-only-credential-0123456789abcdef"
    source = MagicMock(return_value={
        "version": 1,
        "credentials": [{"sha256": hashlib.sha256(credential.encode()).hexdigest(),
                         "principal_id": "monitor-test"}],
        "principals": [{"id": "monitor-test", "type": "SERVICE", "enabled": True,
                        "case_ids": ["case-test"]}],
        "retained_documents": [],
    })
    main.app.state.processing_monitor_authorization_source = source
    docs.get_item.return_value = {"Item": {"case_id": "case-test", "document_id": "doc-test"}}
    table = MagicMock()
    table.query.return_value = {"Items": [{
        "schema_version": 1, "event_id": "received-test", "sequence": 0,
        "case_id": "case-test", "document_id": "doc-test", "type": "FileReceived",
        "occurred_at": "2026-10-20T10:00:00Z",
    }]}
    main.app.state.processing_monitor_audit_store = AuditStore(table)
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/cases/case-test/processing/documents/doc-test/events",
            headers={"Authorization": f"Bearer {credential}"},
        )
    assert response.status_code == 200
    assert response.json()["items"][0]["event_id"] == "received-test"
    assert response.json()["coverage"] == "partial"
    assert response.headers["cache-control"] == "private, no-store"
    source.assert_called_once()
    table.query.assert_called_once()
    table.scan.assert_not_called()


def test_run_events_continue_across_unmatched_window(monitor):
    from document_processing.audit.audit_queries import document_key
    main, _, _, _, _, table = monitor
    key = {"pk": document_key("case-test", "doc-test"), "sk": "EVENT#other"}
    table.query.side_effect = [
        {"Items": [event("received"), event("other", type="RunQueued", run_id="run-b")],
         "LastEvaluatedKey": key},
        {"Items": [event("wanted", type="RunQueued", run_id="run-a")]},
    ]
    url = URL.removesuffix("/events") + "/runs/run-a/events"
    first = get(main, url, params={"limit": 2})
    assert first.status_code == 200
    assert first.json()["items"] == []
    assert first.json()["coverage"] == "partial"
    token = first.json()["next_token"]
    assert token
    assert table.query.call_count == 1
    assert table.query.call_args.kwargs["Limit"] == 2
    second = get(main, url, params={"limit": 2, "next_token": token})
    assert second.status_code == 200
    assert [item["event_id"] for item in second.json()["items"]] == ["wanted"]
    assert second.json()["next_token"] is None
    assert table.query.call_args.kwargs["ExclusiveStartKey"] == key
    assert table.query.call_count == 2
    denied = get(main, url.replace("run-a", "run-b"), params={"next_token": token})
    assert denied.status_code == 400
    assert table.query.call_count == 2
    table.scan.assert_not_called()


TOKEN = "synthetic-only-credential-0123456789abcdef"
URL = "/v1/cases/case-test/processing/documents/doc-test/events"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
RUN_URL = URL.removesuffix("/events") + "/runs/run-a/events"


def test_run_events_filter_and_document_parity(monitor):
    main, _, _, _, _, table = monitor
    table.query.return_value = {"Items": [event(), event("a", type="RunQueued", run_id="run-a"),
                                          event("b", type="RunQueued", run_id="run-b")]}
    response = get(main, RUN_URL)
    assert response.status_code == 200
    assert [item["event_id"] for item in response.json()["items"]] == ["a"]
    assert [item["type"] for item in get(main).json()["items"]] == ["FileReceived", "RunQueued", "RunQueued"]
    table.scan.assert_not_called()


@pytest.mark.parametrize("change", ["case_id", "document_id", "operation", "run_id", "version", "reader", "extra", "duplicate", "bad", "oversize", "inner-oversize", "inner-scope"])
def test_run_events_cursor_scope(monitor, change):
    import base64
    from document_processing.audit.audit_queries import document_key
    main, _, _, _, _, table = monitor
    key = {"pk": document_key("case-test", "doc-test"), "sk": "EVENT#one"}
    table.query.return_value = {"Items": [], "LastEvaluatedKey": key}
    token = get(main, RUN_URL).json()["next_token"]
    data = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
    if change in {"case_id", "document_id", "operation", "run_id"}: data[change] = "foreign"
    if change == "version": data[change] = True
    if change == "reader": data[change] = 1
    if change == "extra": data[change] = "extra"
    if change == "inner-oversize": data["reader"] = "a" * 4097
    if change == "inner-scope":
        inner = json.loads(base64.urlsafe_b64decode(data["reader"] + "=" * (-len(data["reader"]) % 4)))
        inner["document_id"] = "foreign"
        data["reader"] = base64.urlsafe_b64encode(json.dumps(inner).encode()).decode().rstrip("=")
    raw = json.dumps(data)
    if change == "duplicate": raw = raw[:-1] + ', "version": 1}'
    token = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    if change == "bad": token = "bad"
    if change == "oversize": token = "a" * 8193
    table.reset_mock()
    assert get(main, RUN_URL, params={"next_token": token}).status_code == 400
    table.query.assert_not_called()


@pytest.mark.parametrize("failure,status", [("missing-auth", 403), ("forged", 403), ("revoked", 403),
    ("missing", 404), ("foreign", 404), ("auth", 503), ("membership", 503),
    ("read", 503), ("decode", 503), ("dto", 503)])
def test_run_events_auth_scope_and_read_failure(monitor, monkeypatch, failure, status):
    main, _, docs, source, policy, table = monitor
    headers = HEADERS
    if failure == "missing-auth": headers = {}
    if failure == "forged": headers = {"Authorization": "Bearer forged"}
    if failure == "revoked": policy["principals"][0]["case_ids"] = []
    if failure == "missing": docs.get_item.return_value = {}
    if failure == "foreign": docs.get_item.return_value = {"Item": {"case_id": "foreign", "document_id": "doc-test"}}
    if failure == "auth": source.side_effect = RuntimeError("private")
    if failure == "membership": docs.get_item.side_effect = RuntimeError("private")
    if failure == "read": table.query.side_effect = RuntimeError("private")
    if failure == "decode": table.query.return_value = {"Items": [event(type="Unknown")]}
    if failure == "dto":
        import processing_monitor_routes
        table.query.return_value = {"Items": [event(type="RunQueued", run_id="run-a")]}
        monkeypatch.setattr(processing_monitor_routes, "event_dto", lambda _: 1 / 0)
    response = get(main, RUN_URL, headers=headers)
    assert response.status_code == status
    assert "private" not in response.text
    if failure not in {"read", "decode", "dto"}: table.query.assert_not_called()
    if failure in {"missing-auth", "forged", "revoked", "auth"}: docs.get_item.assert_not_called()


@pytest.mark.parametrize("limit", [1, 100, 0, 101, "bad"])
def test_run_events_limits_unknown_and_contract(monitor, limit):
    import yaml
    from datetime import datetime
    from jsonschema import Draft7Validator
    from referencing import Registry, Resource
    main, _, _, _, _, table = monitor
    response = get(main, RUN_URL, params={"limit": limit})
    if limit not in (1, 100):
        assert response.status_code == 400
        table.query.assert_not_called()
        return
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == [] and body["next_token"] is None and body["coverage"] == "partial"
    assert datetime.fromisoformat(body["observed_at"].replace("Z", "+00:00")).utcoffset().total_seconds() == 0
    assert table.query.call_args.kwargs["Limit"] == limit
    path = Path(__file__).resolve().parents[2] / "be-document-processing/contracts/openapi-processing-monitor.yaml"
    contract = yaml.safe_load(path.read_text())
    # OpenAPI 3.0 nullable needs conversion for a JSON Schema validator.
    def convert(value):
        if isinstance(value, dict):
            result = {key: convert(item) for key, item in value.items() if key != "nullable"}
            if value.get("nullable") and "type" in result: result["type"] = [result["type"], "null"]
            return result
        if isinstance(value, list): return [convert(item) for item in value]
        return value
    contract = convert(contract)
    resource = Resource.from_contents({"$schema": "http://json-schema.org/draft-07/schema#", **contract})
    validator = Draft7Validator({"$ref": "urn:monitor#/components/schemas/RunEventCollection"},
                                registry=Registry().with_resource("urn:monitor", resource))
    validator.validate(body)
    table.query.return_value = {"Items": [event(type="RunQueued", run_id="run-a")]}
    validator.validate(get(main, RUN_URL).json())


@pytest.fixture
def monitor(intake):
    main, resource, docs, _, _, _ = intake
    policy = {"version": 1,
              "credentials": [{"sha256": hashlib.sha256(TOKEN.encode()).hexdigest(),
                               "principal_id": "monitor-test"}],
              "principals": [{"id": "monitor-test", "type": "SERVICE", "enabled": True,
                              "case_ids": ["case-test"]}], "retained_documents": []}
    source = MagicMock(side_effect=lambda: copy.deepcopy(policy))
    table = MagicMock()
    table.query.return_value = {"Items": []}
    docs.get_item.return_value = {"Item": {"case_id": "case-test", "document_id": "doc-test"}}
    main.app.state.processing_monitor_authorization_source = source
    main.app.state.processing_monitor_audit_store = AuditStore(table)
    return main, resource, docs, source, policy, table


def get(main, url=URL, headers=HEADERS, **kwargs):
    with TestClient(main.app) as client:
        response = client.get(url, headers=headers, **kwargs)
    assert response.headers["cache-control"] == "private, no-store"
    return response


@pytest.mark.parametrize("headers", [{}, {"x-api-key": "test-key"},
    {"Authorization": "Bearer forged", "x-principal-id": "monitor-test", "x-case-id": "case-test"},
    {"Authorization": "Basic test"}])
def test_identity_denied_before_membership_and_audit(monitor, headers):
    main, _, docs, _, _, table = monitor
    assert get(main, headers=headers).status_code == 403
    docs.get_item.assert_not_called()
    table.query.assert_not_called()


@pytest.mark.parametrize("change", ["revoked", "disabled", "foreign"])
def test_grant_denied_before_any_document_read(monitor, change):
    main, _, docs, _, policy, table = monitor
    if change == "disabled":
        policy["principals"][0]["enabled"] = False
    else:
        policy["principals"][0]["case_ids"] = [] if change == "revoked" else ["foreign-case"]
    assert get(main).status_code == 403
    docs.get_item.assert_not_called()
    table.query.assert_not_called()


@pytest.mark.parametrize("malformation", ["version", "wildcard", "duplicate", "type", "retained", "enabled"])
def test_malformed_authorization_source_is_unavailable(monitor, malformation):
    main, _, docs, _, policy, table = monitor
    if malformation == "version": policy["version"] = True
    if malformation == "wildcard": policy["principals"][0]["case_ids"] = ["*"]
    if malformation == "duplicate": policy["credentials"] *= 2
    if malformation == "type": policy["principals"][0]["type"] = "BROWSER"
    if malformation == "retained": policy["retained_documents"] = [{"case_id": "case-test", "document_id": "doc-test"}]
    if malformation == "enabled": policy["principals"][0]["enabled"] = "true"
    assert get(main).status_code == 503
    docs.get_item.assert_not_called()
    table.query.assert_not_called()


def test_authorization_failure_and_revocation_never_use_stale_policy(monitor):
    main, _, docs, source, policy, table = monitor
    assert get(main).status_code == 200
    table.reset_mock(); docs.reset_mock()
    source.side_effect = RuntimeError("secret details must not escape")
    response = get(main)
    assert response.status_code == 503
    assert "secret details" not in response.text
    docs.get_item.assert_not_called(); table.query.assert_not_called()
    source.side_effect = lambda: copy.deepcopy(policy)
    policy["principals"][0]["case_ids"] = []
    assert get(main).status_code == 403
    table.query.assert_not_called()


def test_rotation_reloads_binding_each_request(monitor):
    main, _, _, _, policy, _ = monitor
    new = "rotated-synthetic-only-credential-0123456789abcdef"
    policy["credentials"].append({"sha256": hashlib.sha256(new.encode()).hexdigest(), "principal_id": "monitor-test"})
    assert get(main).status_code == 200
    assert get(main, headers={"Authorization": f"Bearer {new}"}).status_code == 200
    policy["credentials"].pop(0)
    assert get(main).status_code == 403
    assert get(main, headers={"Authorization": f"Bearer {new}"}).status_code == 200


def test_membership_requires_exact_consistent_source_not_case_existence(monitor):
    main, resource, docs, _, _, table = monitor
    main.cases.get_item.return_value = {}
    assert get(main).status_code == 200
    docs.get_item.assert_called_once_with(Key={"case_id": "case-test", "document_id": "doc-test"}, ConsistentRead=True)
    main.cases.get_item.assert_not_called()
    docs.get_item.return_value = {"Item": {"case_id": "foreign", "document_id": "doc-test"}}
    table.reset_mock()
    assert get(main).status_code == 404
    table.query.assert_not_called()


def test_retained_history_requires_verified_tuple_and_current_grant(monitor):
    main, _, docs, _, policy, table = monitor
    docs.get_item.return_value = {}
    assert get(main).status_code == 404
    policy["retained_documents"] = [{"case_id": "case-test", "document_id": "doc-test",
        "source_revision": "committed-metadata-v1", "verified_at": "2026-10-20T10:00:00Z"}]
    assert get(main).status_code == 200
    table.reset_mock()
    assert get(main, URL.replace("doc-test", "guessed-doc")).status_code == 404
    policy["principals"][0]["case_ids"] = []
    assert get(main).status_code == 403
    table.query.assert_not_called()


def test_membership_failure_does_not_fallback_to_retained(monitor):
    main, _, docs, _, policy, table = monitor
    policy["retained_documents"] = [{"case_id": "case-test", "document_id": "doc-test",
        "source_revision": "committed-metadata-v1", "verified_at": "2026-10-20T10:00:00Z"}]
    docs.get_item.side_effect = RuntimeError("private details")
    assert get(main).status_code == 503
    table.query.assert_not_called()


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=1.5", "limit=abc", "next_token=bad", "next_token=", "next_token=" + "a" * 4097])
def test_invalid_request_is_400_without_audit_query(monitor, query):
    main, _, _, _, _, table = monitor
    assert get(main, URL + "?" + query).status_code == 400
    table.query.assert_not_called()


def event(event_id="received-test", **extra):
    return {"schema_version": 1, "event_id": event_id, "sequence": 0,
            "case_id": "case-test", "document_id": "doc-test", "type": "FileReceived",
            "occurred_at": "2026-10-20T10:00:00Z", **extra}


def test_two_bounded_pages_and_cross_document_cursor(monitor):
    from document_processing.audit.audit_queries import document_key
    main, _, docs, _, policy, table = monitor
    key = {"pk": document_key("case-test", "doc-test"), "sk": "EVENT#received-test"}
    table.query.side_effect = [{"Items": [event()], "LastEvaluatedKey": key}, {"Items": [event("second")]}]
    first = get(main, URL + "?limit=1")
    token = first.json()["next_token"]
    assert token and len(first.json()["items"]) == 1
    second = get(main, params={"limit": 1, "next_token": token})
    assert second.status_code == 200 and second.json()["next_token"] is None
    assert second.json()["items"][0]["event_id"] == "second"
    assert table.query.call_count == 2
    assert table.query.call_args.kwargs["ExclusiveStartKey"] == key
    assert table.query.call_args.kwargs["Limit"] == 1
    assert table.query.call_args.kwargs["ConsistentRead"] is True
    docs.get_item.return_value = {"Item": {"case_id": "case-test", "document_id": "other-doc"}}
    assert get(main, URL.replace("doc-test", "other-doc"), params={"next_token": token}).status_code == 400
    policy["principals"][0]["case_ids"].append("other-case")
    docs.get_item.return_value = {"Item": {"case_id": "other-case", "document_id": "doc-test"}}
    assert get(main, URL.replace("case-test", "other-case"), params={"next_token": token}).status_code == 400
    assert table.query.call_count == 2
    table.scan.assert_not_called()


@pytest.mark.parametrize("failure", ["query", "decode", "disabled", "foreign-row"])
def test_audit_failures_are_safe_503_not_empty_success(monitor, failure):
    main, _, _, _, _, table = monitor
    if failure == "query": table.query.side_effect = RuntimeError("secret payload")
    if failure == "decode": table.query.return_value = {"Items": [event(type="Unknown")]}
    if failure == "disabled": main.app.state.processing_monitor_audit_store = AuditStore()
    if failure == "foreign-row": table.query.return_value = {"Items": [event(case_id="foreign")]}
    response = get(main)
    assert response.status_code == 503
    assert response.json() == {"error": "audit read unavailable"}


def test_safe_dto_and_unknown_monitor_route(monitor):
    main, _, _, _, _, table = monitor
    table.query.return_value = {"Items": [event(filename="private.pdf", sha256="private", prompt="private")]}
    response = get(main)
    assert response.status_code == 200
    assert set(response.json()) == {"items", "next_token", "observed_at", "coverage"}
    assert set(response.json()["items"][0]) == {"event_id", "case_id", "document_id", "sequence", "type", "occurred_at"}
    assert get(main, URL + "/unknown").status_code == 404


def test_monitor_token_does_not_replace_upload_auth(monitor):
    main, _, _, _, _, _ = monitor
    with TestClient(main.app) as client:
        for method in (client.get, client.post):
            assert method("/v1/cases/case-test/documents", headers=HEADERS).status_code == 401
        assert client.get("/v1/cases/case-test/documents", headers={"x-api-key": "wrong"}).status_code == 403


def test_real_upload_producer_to_reader_and_http(monitor):
    from test_monitor_file_received import post
    from document_processing.audit.audit_listener import FileReceivedAudit
    main, _, docs, _, _, table = monitor
    main.app.state.audit_listener = FileReceivedAudit(AuditStore(table))
    docs.get_item.return_value = {}
    uploaded = post(main)
    assert uploaded.status_code == 201
    document_id = uploaded.json()["documents"][0]["document_id"]
    written = table.put_item.call_args.kwargs["Item"]
    assert written["document_id"] == document_id and written["type"] == "FileReceived"
    docs.get_item.return_value = {"Item": {"case_id": "case-test", "document_id": document_id}}
    table.query.return_value = {"Items": [written]}
    response = get(main, URL.replace("doc-test", document_id))
    assert response.status_code == 200
    assert response.json()["items"][0]["event_id"] == written["event_id"]
    assert response.json()["items"][0]["occurred_at"] == "2026-10-20T10:00:00Z"


@pytest.mark.parametrize("intake", [{
    "PROCESSING_MONITOR_AUTHORIZATION_SECRET_ARN": "arn:aws:secretsmanager:eu-central-1:123456789012:secret:monitor-test",
    "AUDIT_TABLE_NAME": "test-audit",
}], indirect=True)
def test_installed_source_wiring_refresh_and_fail_closed(intake):
    main, resource, docs, *_ = intake
    policy = {"version": 1, "credentials": [{
        "sha256": hashlib.sha256(TOKEN.encode()).hexdigest(), "principal_id": "monitor-test"}],
        "principals": [{"id": "monitor-test", "type": "SERVICE", "enabled": True, "case_ids": ["case-test"]}],
        "retained_documents": []}
    secrets = resource.monitor_secrets
    secrets.get_secret_value.return_value = {"SecretString": json.dumps(policy)}
    docs.get_item.return_value = {"Item": {"case_id": "case-test", "document_id": "doc-test"}}
    resource.monitor_audit.query.return_value = {"Items": [event()]}
    assert get(main).status_code == 200
    secrets.get_secret_value.assert_called_once_with(
        SecretId="arn:aws:secretsmanager:eu-central-1:123456789012:secret:monitor-test", VersionStage="AWSCURRENT")
    resource.monitor_audit.reset_mock(); docs.reset_mock()
    policy["principals"][0]["case_ids"] = []
    secrets.get_secret_value.return_value = {"SecretString": json.dumps(policy)}
    assert get(main).status_code == 403
    secrets.get_secret_value.return_value = {"SecretString": '{"version": 1, "version": 1}'}
    assert get(main).status_code == 503
    secrets.get_secret_value.side_effect = RuntimeError("unavailable")
    assert get(main).status_code == 503
    assert secrets.get_secret_value.call_count == 4
    docs.get_item.assert_not_called(); resource.monitor_audit.query.assert_not_called()


def test_missing_configuration_is_503_and_invalid_ids_are_400(intake):
    main, _, docs, *_ = intake
    assert get(main).status_code == 503
    assert get(main, URL.replace("doc-test", "invalid$id")).status_code == 503
    assert get(main, URL.replace("case-test", "invalid$id")).status_code == 400
    docs.get_item.assert_not_called()


def test_authorized_invalid_document_id_is_400(monitor):
    main, _, docs, _, _, table = monitor
    assert get(main, URL.replace("doc-test", "invalid$id")).status_code == 400
    docs.get_item.assert_not_called(); table.query.assert_not_called()


def test_unhandled_monitor_exception_is_private_and_safe(monitor):
    main, _, _, _, _, table = monitor
    @main.app.get(URL + "/crash")
    def crash():
        raise RuntimeError("private exception detail")
    response = get(main, URL + "/crash")
    assert response.status_code == 500
    assert response.json() == {"error": "internal error"}
    table.query.assert_not_called()


@pytest.mark.parametrize("payload", [
    event(),
    event(type="RunQueued", run_id="run-test", run_context={"source": "internal"}),
    event(type="AttemptStarted", run_id="run-test", attempt_no=1),
    event(type="StepStarted", run_id="run-test", attempt_no=1, stage="extraction"),
    event(type="StepFinished", run_id="run-test", attempt_no=1, stage="extraction", duration_ms=1.5),
    event(type="StepFailed", run_id="run-test", attempt_no=1, stage="source_validation",
          duration_ms=1.5, error_code="SOURCE_VALIDATION_FAILED"),
    event(type="PageCacheReused", run_id="run-test", attempt_no=1, stage="page_transcription",
          page_number=1, cached_status="completed", cached_method="native", cached_model="model-test", artifact_ids=["internal-ref"]),
    event(type="PageCompleted", run_id="run-test", attempt_no=1, stage="page_transcription",
          page_number=1, duration_ms=1.5, method="vision", model="model-test"),
    event(type="PageFailed", run_id="run-test", attempt_no=1, stage="page_transcription",
          page_number=1, duration_ms=1.5, method="vision", model="model-test", error_code="PAGE_TRANSCRIPTION_FAILED"),
    event(type="ResultPublished", run_id="run-test", attempt_no=1, result_status="partial", artifact_ids=["public-ref"]),
    event(type="RetryEnqueued", run_id="run-test", attempt_no=1, reason_code="THROTTLED"),
    event(type="RetryEnqueued", run_id="run-test", attempt_no=1, reason_code="MAX_ATTEMPTS"),
    event(type="AttemptFinished", run_id="run-test", attempt_no=1, attempt_status="failed",
          duration_ms=1.5, error_code="SOURCE_VALIDATION_FAILED"),
    event(type="RunFinished", run_id="run-test", run_status="failed", error_code="SOURCE_VALIDATION_FAILED"),
], ids=lambda payload: payload["type"] + ":" + payload.get("reason_code", ""))
def test_public_event_dto_matches_sole_openapi_contract(monitor, payload):
    import yaml
    from jsonschema import Draft7Validator
    main, _, _, _, _, table = monitor
    table.query.return_value = {"Items": [payload]}
    response = get(main)
    assert response.status_code == 200, response.text
    path = Path(__file__).resolve().parents[2] / "be-document-processing/contracts/openapi-processing-monitor.yaml"
    schema = yaml.safe_load(path.read_text())["components"]["schemas"][payload["type"]]
    result = response.json()["items"][0]
    errors = list(Draft7Validator(schema).iter_errors(result))
    assert errors == [], [error.message for error in errors]
    assert result["event_id"] == payload["event_id"]
    if payload.get("reason_code") == "MAX_ATTEMPTS":
        assert "reason_code" not in result  # no invented retry-exhausted conclusion
    table.query.assert_called_once()
