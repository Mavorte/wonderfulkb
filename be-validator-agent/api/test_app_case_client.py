"""Směrování v app.handler: /cases a /clients obsluhuje case_client_handler za stejnou kontrolou klíče."""
import json

import pytest

import app
import core


class _Keys:
    def check(self, key):
        return key == "k"


class _Api:
    keys = _Keys()


@pytest.fixture(autouse=True)
def mock_backend(monkeypatch):
    monkeypatch.setenv("DATA_BACKEND", "mock")
    monkeypatch.setenv("ALLOW_EPHEMERAL_MOCK", "true")
    monkeypatch.setattr(core, "_default", _Api())


def ev(method, path, key="k", body=None, query=None):
    return {"version": "2.0", "rawPath": path, "requestContext": {"http": {"method": method}},
            "headers": {"x-api-key": key} if key else {}, "body": body, "queryStringParameters": query}


@pytest.mark.parametrize("path", ["/v1/cases", "/v1/clients", "/v1/cases/abc", "/v1/clients/x/cases"])
def test_case_client_routes_need_key(path):
    assert app.handler(ev("GET", path, key=None))["statusCode"] == 401
    assert app.handler(ev("GET", path, key="bad"))["statusCode"] == 403


def test_list_cases_and_clients():
    r = app.handler(ev("GET", "/v1/cases", query={"limit": "5"}))
    assert r["statusCode"] == 200 and "cases" in json.loads(r["body"])
    r = app.handler(ev("GET", "/v1/clients"))
    clients = json.loads(r["body"])["clients"]
    assert r["statusCode"] == 200 and clients
    active = next(c for c in clients if c["status"] == "active")
    r = app.handler(ev("POST", "/v1/cases", body=json.dumps({"client_id": active["client_id"]})))
    assert r["statusCode"] == 201
    case_id = json.loads(r["body"])["case_id"]
    r = app.handler(ev("GET", f"/v1/cases/{case_id}"))
    assert r["statusCode"] == 200 and json.loads(r["body"])["client_id"] == active["client_id"]
    r = app.handler(ev("GET", f"/v1/clients/{active['client_id']}/cases"))
    assert case_id in [c["case_id"] for c in json.loads(r["body"])["cases"]]


def test_documents_routes_stay_in_core(monkeypatch):
    seen = []
    monkeypatch.setattr(core, "handle", lambda *a, **k: seen.append(a[1]) or (200, {}))
    app.handler(ev("GET", "/v1/cases/abc/documents"))
    assert seen == ["/v1/cases/abc/documents"]


def test_set_case_status_goes_to_case_client():
    assert app.handler(ev("PUT", "/v1/cases/abc/status", key=None))["statusCode"] == 401
    r = app.handler(ev("GET", "/v1/clients"))
    active = next(c for c in json.loads(r["body"])["clients"] if c["status"] == "active")
    case_id = json.loads(app.handler(ev("POST", "/v1/cases", body=json.dumps({"client_id": active["client_id"]})))["body"])["case_id"]
    r = app.handler(ev("PUT", f"/v1/cases/{case_id}/status", body=json.dumps({"status": "awaiting_decision"})))
    assert r["statusCode"] == 200 and json.loads(r["body"])["status"] == "awaiting_decision"
