from fastapi.testclient import TestClient

from document_processing.api import create_app
from document_processing.config import Settings


def make_client(tmp_path, **settings):
    return TestClient(create_app(Settings(data_dir=tmp_path, worker_enabled=False, **settings)))


def test_missing_api_key_fails_closed(tmp_path):
    with make_client(tmp_path) as client:
        response = client.get("/v1/clients")
        assert response.status_code == 503
        assert response.json() == {"error": "API_AUTH_NOT_CONFIGURED"}
        assert client.get("/health").status_code == 200


def test_api_key_is_required_when_configured(tmp_path):
    with make_client(tmp_path, api_key="secret-test-key") as client:
        assert client.get("/v1/clients").status_code == 403
        assert client.get("/v1/clients", headers={"x-api-key": "wrong"}).status_code == 403
        assert client.get("/v1/clients", headers={"x-api-key": "secret-test-key"}).status_code == 200


def test_explicit_opt_in_allows_no_key(tmp_path):
    with make_client(tmp_path, allow_no_auth=True) as client:
        assert client.get("/v1/clients").status_code == 200


def test_env_opt_in_requires_exact_value(monkeypatch):
    monkeypatch.delenv("DOCUMENT_API_KEY", raising=False)
    monkeypatch.setenv("DOCUMENT_API_ALLOW_NO_AUTH", "true")
    assert Settings.from_env().allow_no_auth is False
    monkeypatch.setenv("DOCUMENT_API_ALLOW_NO_AUTH", "1")
    assert Settings.from_env().allow_no_auth is True
