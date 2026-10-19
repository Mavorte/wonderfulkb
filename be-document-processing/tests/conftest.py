from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from document_processing.api import create_app
from document_processing.bootstrap import CLIENTS
from document_processing.config import Settings


@pytest.fixture
def application(tmp_path):
    return create_app(Settings(data_dir=tmp_path, worker_enabled=False, allow_no_auth=True))


@pytest.fixture
def client(application):
    with TestClient(application) as client:
        yield client


@pytest.fixture
def case(client):
    item = {"case_id": "case-test", "client_id": CLIENTS[0]["client_id"],
            "metadata": {"required_document_types": ["loan_agreement", "invoice"]}}
    assert client.post("/v1/cases", json=item).status_code == 201
    return item


def make_pdf(*pages):
    with pymupdf.open() as document:
        for text in pages:
            page = document.new_page()
            page.insert_text((45, 60), text, fontsize=11)
        return document.tobytes()


def upload_document(client, body, case_id="case-test", mode="auto"):
    response = client.post(f"/v1/cases/{case_id}/documents", json={
        "filename": "document.pdf", "content_type": "application/pdf", "size_bytes": len(body), "mode": mode})
    assert response.status_code == 201, response.text
    result = response.json()
    uploaded = client.put(result["upload"]["url"], content=body, headers=result["upload"]["headers"])
    assert uploaded.status_code == 204, uploaded.text
    return result
