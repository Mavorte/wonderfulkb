"""Composition proof: replace AWS clients only, never the reader or authorizer."""
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from test_monitor_file_received import intake

CONFIG = {"MONITOR_AUTH_SECRET_ARN": "arn:aws:secretsmanager:eu-central-1:123456789012:secret:monitor-test",
          "AUDIT_TABLE_NAME": "test-audit"}
HEADERS = {"x-api-key": "test-key", "Authorization": "Bearer monitor-test-credential"}
PREFIX = "/v1/cases/case-test/processing/documents/doc-test"


def policy():
    return {"schema_version": 1, "credentials": [{
        "credential_id": "version-1", "sha256": hashlib.sha256(b"monitor-test-credential").hexdigest(),
        "state": "active", "principal_type": "SERVICE", "principal_id": "monitor-test",
        "grants": [{"case_id": "case-test", "documents": [{"document_id": "doc-test", "membership": "current"}]}]}]}


def configure(intake):
    main, resource, docs, *_ = intake
    resource.monitor_secrets.get_secret_value.return_value = {"SecretString": json.dumps(policy())}
    docs.get_item.return_value = {"Item": {"case_id": "case-test", "document_id": "doc-test"}}
    from document_processing.audit.audit_events import ResultPublished
    from document_processing.audit.audit_storage import AuditStore
    event = ResultPublished(**dict(
        schema_version=1, case_id="case-test", document_id="doc-test", event_id="publication-1",
        sequence=1, type="ResultPublished", occurred_at="2026-10-20T10:00:00Z",
        run_id="run-1", attempt_no=1, result_status="partial", artifact_ids=["artifact-1"]))
    assert AuditStore(resource.monitor_audit).put(event) == "inserted"
    resource.monitor_audit.query.return_value = {"Items": [resource.monitor_audit.put_item.call_args.kwargs["Item"]]}
    return main, resource, docs


def test_composition_installs_real_lifecycle_authorizer(intake):
    assert callable(getattr(intake[0].app.state, "lifecycle_authorize_read", None))


@pytest.mark.parametrize("intake", [CONFIG], indirect=True)
def test_real_boundary_publication_routes_and_revocation(intake):
    main, resource, docs = configure(intake)
    with TestClient(main.app) as client:
        for suffix in ("/runs", "/runs/run-1", "/audit"):
            response = client.get(PREFIX + suffix, headers=HEADERS)
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "private, no-store"
            assert response.json()["items"][0].get("state", "unknown") == "unknown"
            if suffix != "/runs":
                publication = response.json()["items"][0]["published_results"][0]
                assert publication["publication_id"] == "publication-1"
                assert publication["evidence"][0]["event_id"] == "publication-1"
        assert resource.monitor_audit.query.call_count == 3
        assert docs.get_item.call_args.kwargs == {"Key": {"case_id": "case-test", "document_id": "doc-test"}, "ConsistentRead": True}
        changed = policy()
        changed["credentials"][0]["state"] = "revoked"
        resource.monitor_secrets.get_secret_value.return_value = {"SecretString": json.dumps(changed)}
        assert client.get(PREFIX + "/runs", headers=HEADERS).status_code == 403
        assert resource.monitor_audit.query.call_count == 3


@pytest.mark.parametrize("intake", [CONFIG], indirect=True)
@pytest.mark.parametrize("failure,code", [("missing", 403), ("forged", 403), ("ungranted", 404),
    ("ungranted_case", 404), ("membership", 404), ("outage", 403), ("malformed", 403)])
def test_real_boundary_denial_before_audit(intake, failure, code):
    main, resource, docs = configure(intake)
    headers, path = dict(HEADERS), PREFIX
    if failure == "missing": headers.pop("Authorization")
    if failure == "forged": headers["Authorization"] = "Bearer forged"
    if failure == "ungranted": path = path.replace("doc-test", "doc-other")
    if failure == "ungranted_case": path = path.replace("case-test", "case-other")
    if failure == "membership": docs.get_item.return_value["Item"]["case_id"] = "forged"
    if failure == "outage": resource.monitor_secrets.get_secret_value.side_effect = RuntimeError("offline")
    if failure == "malformed": resource.monitor_secrets.get_secret_value.return_value = {"SecretString": "{}"}
    with TestClient(main.app) as client:
        response = client.get(path + "/runs", headers=headers)
    assert response.status_code == code
    assert response.headers["cache-control"] == "private, no-store"
    resource.monitor_audit.query.assert_not_called()
    if failure != "membership": docs.get_item.assert_not_called()


@pytest.mark.parametrize("intake", [CONFIG], indirect=True)
def test_retained_membership_rotation_and_read_failure(intake):
    main, resource, docs = configure(intake)
    changed = policy()
    scope = changed["credentials"][0]["grants"][0]["documents"][0]
    scope.update(membership="retained", provenance={"record_id": "verified-record-1",
        "verified_by": "fixture-owner", "verified_at": "2026-10-20T10:00:00Z"})
    resource.monitor_secrets.get_secret_value.return_value = {"SecretString": json.dumps(changed)}
    docs.get_item.return_value = {}
    with TestClient(main.app) as client:
        assert client.get(PREFIX + "/runs", headers=HEADERS).status_code == 200
        assert docs.get_item.call_args.kwargs["ConsistentRead"] is True
        changed["credentials"][0]["sha256"] = hashlib.sha256(b"rotated-credential").hexdigest()
        resource.monitor_secrets.get_secret_value.return_value = {"SecretString": json.dumps(changed)}
        assert client.get(PREFIX + "/runs", headers=HEADERS).status_code == 403
        rotated = {**HEADERS, "Authorization": "Bearer rotated-credential"}
        assert client.get(PREFIX + "/runs", headers=rotated).status_code == 200
        resource.monitor_audit.query.return_value = {"Items": [{"type": "MalformedSynthetic"}]}
        response = client.get(PREFIX + "/audit", headers=rotated)
        assert response.status_code == 503
        assert response.json() == {"error": "audit read unavailable"}
        assert response.headers["cache-control"] == "private, no-store"
        scope.pop("provenance")
        resource.monitor_secrets.get_secret_value.return_value = {"SecretString": json.dumps(changed)}
        before = resource.monitor_audit.query.call_count
        assert client.get(PREFIX + "/runs", headers=rotated).status_code == 403
        assert resource.monitor_audit.query.call_count == before


@pytest.mark.parametrize("intake", [CONFIG], indirect=True)
def test_real_boundary_cursor_scope_and_bounded_query(intake):
    from document_processing.audit.audit_queries import document_key
    main, resource, _ = configure(intake)
    resource.monitor_audit.query.return_value["LastEvaluatedKey"] = {
        "pk": document_key("case-test", "doc-test"), "sk": "EVENT#publication-1"}
    with TestClient(main.app) as client:
        first = client.get(PREFIX + "/runs?limit=1", headers=HEADERS)
        assert first.status_code == 200
        token = first.json()["next_token"]
        assert token
        assert resource.monitor_audit.query.call_args.kwargs["Limit"] == 1
        assert resource.monitor_audit.query.call_args.kwargs["ConsistentRead"] is True
        assert client.get(PREFIX + "/runs", params={"next_token": token}, headers=HEADERS).status_code == 200
        assert "ExclusiveStartKey" in resource.monitor_audit.query.call_args.kwargs
        before = resource.monitor_audit.query.call_count
        for suffix in ("/audit", "/runs/run-1"):
            assert client.get(PREFIX + suffix, params={"next_token": token}, headers=HEADERS).status_code == 400
        assert resource.monitor_audit.query.call_count == before


@pytest.mark.parametrize("intake", [CONFIG], indirect=True)
def test_retained_provenance_does_not_leak_between_credentials(intake):
    import copy
    main, resource, docs = configure(intake)
    changed = policy()
    other = copy.deepcopy(changed["credentials"][0])
    other.update(credential_id="version-other", sha256=hashlib.sha256(b"other-credential").hexdigest())
    other["grants"][0]["documents"][0].update(membership="retained", provenance={
        "record_id": "other-record", "verified_by": "fixture-owner", "verified_at": "2026-10-20T10:00:00Z"})
    changed["credentials"].append(other)
    docs.get_item.return_value = {}
    resource.monitor_secrets.get_secret_value.return_value = {"SecretString": json.dumps(changed)}
    with TestClient(main.app) as client:
        assert client.get(PREFIX + "/runs", headers=HEADERS).status_code == 404
        resource.monitor_audit.query.assert_not_called()
        assert client.get(PREFIX + "/runs", headers={**HEADERS, "Authorization": "Bearer other-credential"}).status_code == 200
