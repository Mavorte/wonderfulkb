import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from document_processing.bootstrap import CLIENTS
from document_processing.models import UploadRequest
from document_processing.pipeline import DocumentWorker
from document_processing.providers import LocalOcr, ProviderError
from conftest import make_pdf, upload_document


def complete(client, upload, case_id="case-test"):
    document_id = upload["document"]["document_id"]
    response = client.post(f"/v1/cases/{case_id}/documents/{document_id}/complete")
    assert response.status_code == 202, response.text
    return response.json()


def test_firm_clients_and_persistent_case(client, case):
    firms = client.get("/v1/clients?name=Obrabeni").json()["clients"]
    assert firms[0]["ico"] == "98007009"
    assert "birthDate" not in firms[0]
    assert client.post("/v1/cases", json=case).status_code == 200
    assert client.post("/v1/cases", json={**case, "client_id": CLIENTS[1]["client_id"]}).status_code == 409
    assert client.get("/v1/cases/case-test").json()["status"] == "open"


def test_upload_cannot_override_client(client, case):
    response = client.post("/v1/cases/case-test/documents", json={
        "filename": "a.pdf", "size_bytes": 10, "content_type": "application/pdf", "client_id": CLIENTS[1]["client_id"]})
    assert response.status_code == 422


def test_complete_is_idempotent_and_upload_is_immutable(client, application, case):
    upload = upload_document(client, make_pdf("Smlouva o uveru c. 123/26"))
    first, second = complete(client, upload), complete(client, upload)
    assert first["job_id"] == second["job_id"]
    assert len(application.state.service.repo.list("JOBS")) == 1
    assert client.put(upload["upload"]["url"], content=b"different").status_code == 409
    assert upload["document"]["client_id"] == case["client_id"]
    assert "upload_token" not in client.get("/v1/cases/case-test/documents").text


def test_wrong_case_cannot_read_document(client, case):
    upload = upload_document(client, make_pdf("invoice"))
    client.post("/v1/cases", json={"case_id": "other", "client_id": CLIENTS[1]["client_id"]})
    document_id = upload["document"]["document_id"]
    assert client.get(f"/v1/cases/other/documents/{document_id}/result").status_code == 404
    assert client.post(f"/v1/cases/other/documents/{document_id}/complete").status_code == 404


def test_invalid_pdf_and_expired_token(client, application, case):
    upload = upload_document(client, b"not a PDF")
    document_id = upload["document"]["document_id"]
    response = client.post(f"/v1/cases/case-test/documents/{document_id}/complete")
    assert response.status_code == 422
    assert response.json()["error"] == "CONTENT_TYPE_MISMATCH"
    service = application.state.service
    service.repo.update("CASE#case-test", "DOC#" + document_id, lambda d: {**d, "upload_expires_at": time.time() - 1})
    assert client.put(upload["upload"]["url"], content=b"x").status_code == 403


def test_real_native_pdf_pipeline_and_correction(client, application, case):
    upload = upload_document(client, make_pdf("SMLOUVA O UVERU C. 123/26\nPrijemce financovani / dluznik\nICO 98007009\nVyrobni cislo SN-001\nJistina 1 000,00 CZK"))
    job = complete(client, upload)
    worker = DocumentWorker(application.state.service)
    worker.process(job["job_id"])
    document_id = upload["document"]["document_id"]
    response = client.get(f"/v1/cases/case-test/documents/{document_id}/result")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["processing_status"] == "completed", result
    assert result["ocr"]["pages"][0]["method"] == "native"
    principal = next(f for f in result["extraction"]["fields"] if f["key"] == "loan.principal")
    assert principal["normalized_value"] == "1000.00"
    assert principal["currency"] == "CZK"
    correction = {"run_id": result["run_id"], "field_id": principal["field_id"], "normalized_value": "1001.00", "reason": "Opraveno po kontrole originálu"}
    assert client.post(f"/v1/cases/case-test/documents/{document_id}/corrections", json=correction).status_code == 201
    updated = client.get(f"/v1/cases/case-test/documents/{document_id}/result").json()
    corrected = next(f for f in updated["extraction"]["fields"] if f["field_id"] == principal["field_id"])
    assert corrected["raw_value"] == principal["raw_value"]
    assert corrected["normalized_value"] == "1001.00"
    assert corrected["status"] == "human_corrected"
    document = application.state.service.get_document("case-test", document_id)
    stored = application.state.service.blobs.read_json(document["result_key"])
    assert next(f for f in stored["extraction"]["fields"] if f["field_id"] == principal["field_id"])["normalized_value"] == "1000.00"
    assert client.get(f"/v1/cases/case-test/documents/{document_id}/pages/1").json()["image_url"].startswith("data:image/png;")
    assert client.get("/v1/cases/case-test/validation").json()["authenticity"] == "not_assessed"


def test_failed_page_does_not_remove_successful_pages(client, application, case):
    class Ocr:
        def transcribe(self, page, number, mode):
            if number == 2:
                raise ProviderError("ILLEGIBLE")
            return LocalOcr().transcribe(page, number, "auto")
    upload = upload_document(client, make_pdf("Smlouva o uveru", "second page"))
    job = complete(client, upload)
    DocumentWorker(application.state.service, ocr=Ocr()).process(job["job_id"])
    result = application.state.service.get_result("case-test", upload["document"]["document_id"])
    assert result["processing_status"] == "partial"
    assert len(result["ocr"]["pages"]) == 2
    assert result["ocr"]["pages"][0]["text"]
    assert result["errors"][0]["page_number"] == 2


def test_retry_reuses_successful_pages(client, application, case):
    class Ocr:
        def __init__(self):
            self.calls = []
        def transcribe(self, page, number, mode):
            self.calls.append(number)
            if number == 2 and self.calls.count(2) == 1:
                raise ProviderError("THROTTLED", True)
            return LocalOcr().transcribe(page, number, "auto")
    upload = upload_document(client, make_pdf("Smlouva o uveru", "Jistina 1000,00 CZK"))
    job = complete(client, upload)
    ocr = Ocr()
    worker = DocumentWorker(application.state.service, ocr=ocr)
    worker.process(job["job_id"])
    worker.process(job["job_id"])
    assert ocr.calls == [1, 2, 2]
    assert application.state.service.repo.get("JOBS", job["job_id"])["status"] == "completed"


def test_duplicate_delivery_does_not_run_ocr_twice(client, application, case):
    upload = upload_document(client, make_pdf("SMLOUVA O UVERU"))
    job = complete(client, upload)
    worker = DocumentWorker(application.state.service)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(worker.process, [job["job_id"], job["job_id"]]))
    assert application.state.service.repo.get("JOBS", job["job_id"])["attempts"] == 1


def test_source_hash_is_checked_after_upload(client, application, case):
    upload = upload_document(client, make_pdf("Smlouva o uveru"))
    job = complete(client, upload)
    service = application.state.service
    doc = service.get_document("case-test", upload["document"]["document_id"])
    service.blobs.path(doc["source_key"]).write_bytes(b"changed")
    DocumentWorker(service).process(job["job_id"])
    assert service.get_document("case-test", doc["document_id"])["error"] == "SOURCE_HASH_MISMATCH"
