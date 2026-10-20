from fastapi.testclient import TestClient
from test_monitor_file_received import intake
from unittest.mock import patch


def test_lifecycle_routes_require_trusted_case_scope_and_private_denial(intake):
    main, _, _, _, _, _ = intake
    route_paths = [
        "/v1/cases/{case_id}/processing/documents/{document_id}/runs",
        "/v1/cases/{case_id}/processing/documents/{document_id}/runs/{run_id}",
        "/v1/cases/{case_id}/processing/documents/{document_id}/audit",
    ]
    assert {route.path for route in main.lifecycle_router.routes} == set(route_paths)
    paths = [path.replace("{case_id}", "case-test").replace("{document_id}", "doc-test")
             .replace("{run_id}", "run-test") for path in route_paths]
    with TestClient(main.app) as client:
        for path in paths:
            response = client.get(path, headers={"x-api-key": "test-key"})
            assert response.status_code == 403
            assert response.headers["cache-control"] == "private, no-store"
            assert "runs" not in response.json()
            unauthenticated = client.get(path)
            assert unauthenticated.status_code == 401
            assert unauthenticated.headers["cache-control"] == "private, no-store"


def test_authorized_lifecycle_window_uses_bounded_reader(intake, monkeypatch):
    import processing_monitor_lifecycle_routes as lifecycle
    from document_processing.audit.audit_queries import AuditPage
    from document_processing.audit.audit_events import RunQueued

    main, *_ = intake
    # Hermetic stand-in for the service owner's trusted entitlement provider.
    monkeypatch.setattr(main.app.state, "lifecycle_authorize_read",
                        lambda request, case_id, document_id: lifecycle.AuthorizedDocumentScope(case_id, document_id),
                        raising=False)
    main.app.state.lifecycle_audit_table = object()
    event = RunQueued(schema_version=1, case_id="case-test", document_id="doc-test",
                      event_id="evt-1", sequence=1, type="RunQueued",
                      occurred_at="2026-10-20T10:00:00Z", run_id="run-1")
    with patch.object(lifecycle, "read_document", create=True,
                      return_value=AuditPage([event], None)) as reader:
        with TestClient(main.app) as client:
            response = client.get("/v1/cases/case-test/processing/documents/doc-test/runs",
                                  headers={"x-api-key": "test-key"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["coverage"] == "partial"
    assert response.json()["items"][0]["run_id"] == "run-1"
    assert reader.call_count == 1


def test_lifecycle_detail_audit_cursor_and_errors(intake):
    import processing_monitor_lifecycle_routes as lifecycle
    from document_processing.audit.audit_queries import AuditPage
    from document_processing.audit.audit_events import RunQueued, AttemptStarted, RunFinished

    main, *_ = intake
    main.app.state.lifecycle_authorize_read = lambda request, case_id, document_id: lifecycle.AuthorizedDocumentScope(case_id, document_id)
    main.app.state.lifecycle_audit_table = object()
    base = dict(schema_version=1, case_id="case-test", document_id="doc-test",
                occurred_at="2026-10-20T10:00:00Z", run_id="run-1")
    events = [RunQueued(**base, event_id="e1", sequence=1, type="RunQueued"),
              AttemptStarted(**base, event_id="e2", sequence=2, type="AttemptStarted", attempt_no=1),
              RunFinished(**base, event_id="e3", sequence=3, type="RunFinished", run_status="completed")]
    prefix = "/v1/cases/case-test/processing/documents/doc-test"
    with patch.object(lifecycle, "read_document", return_value=AuditPage(events, "reader-cursor")) as reader:
        with TestClient(main.app) as client:
            runs = client.get(prefix + "/runs", headers={"x-api-key": "test-key"})
            detail = client.get(prefix + "/runs/run-1", headers={"x-api-key": "test-key"})
            audit = client.get(prefix + "/audit", headers={"x-api-key": "test-key"})
            for result in (runs, detail, audit):
                assert result.status_code == 200
                assert result.headers["cache-control"] == "private, no-store"
                assert result.json()["coverage"] == "partial"
                assert result.json()["next_token"]
            assert runs.json()["items"][0]["state"] == "completed"
            assert detail.json()["items"][0]["attempts"][0]["terminal_state"] == "unknown"
            assert [e["event_id"] for e in detail.json()["items"][0]["evidence"]] == ["e1", "e2", "e3"]
            assert audit.json()["items"][0]["runs"][0] == runs.json()["items"][0]
            assert reader.call_count == 3
            wrong = client.get(prefix + "/audit", params={"next_token": runs.json()["next_token"]},
                               headers={"x-api-key": "test-key"})
            assert wrong.status_code == 400
            assert wrong.headers["cache-control"] == "private, no-store"
            assert reader.call_count == 3
            empty = client.get(prefix + "/runs/run-2", params={"next_token": detail.json()["next_token"]},
                               headers={"x-api-key": "test-key"})
            assert empty.status_code == 400
            assert reader.call_count == 3
    with patch.object(lifecycle, "read_document", return_value=AuditPage([], "reader-cursor")):
        with TestClient(main.app) as client:
            response = client.get(prefix + "/runs/run-1", headers={"x-api-key": "test-key"})
            assert response.status_code == 200
            assert response.json()["items"][0]["state"] == "unknown"
            assert response.json()["next_token"]
    with patch.object(lifecycle, "read_document", side_effect=RuntimeError("synthetic outage")):
        with TestClient(main.app) as client:
            response = client.get(prefix + "/audit", headers={"x-api-key": "test-key"})
            assert response.status_code == 503
            assert response.headers["cache-control"] == "private, no-store"
            assert "synthetic outage" not in response.text


def test_lifecycle_rejects_untrusted_or_mismatched_scope_without_audit_read(intake):
    import processing_monitor_lifecycle_routes as lifecycle

    main, *_ = intake
    main.app.state.lifecycle_audit_table = object()
    base = "/v1/cases/case-test/processing/documents/doc-test"
    with patch.object(lifecycle, "read_document") as reader:
        with TestClient(main.app) as client:
            for value in (("case-test", "doc-test"),
                          lifecycle.AuthorizedDocumentScope("other-case", "doc-test"), None):
                main.app.state.lifecycle_authorize_read = lambda *_args, value=value: value
                for suffix in ("/runs", "/runs/run-1", "/audit"):
                    denied = client.get(base + suffix, headers={"x-api-key": "test-key"})
                    assert denied.status_code == 403
                    assert denied.headers["cache-control"] == "private, no-store"
            reader.assert_not_called()
