import hashlib
import hmac
import json
import time
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from . import PIPELINE_VERSION, PROMPT_VERSION
from .blobs import get_sha256
from .models import Correction, UploadRequest
from .rendering import InvalidDocument, open_document
from .repository import Conflict
from .validation import validate_case


def now():
    return datetime.now(timezone.utc).isoformat()


class ServiceError(Exception):
    def __init__(self, code, status=400):
        self.code, self.status = code, status
        super().__init__(code)


class DocumentService:
    def __init__(self, settings, repository, blobs, enqueue=None):
        self.settings, self.repo, self.blobs = settings, repository, blobs
        self.enqueue = enqueue or (lambda job: None)

    def get_case(self, case_id):
        case = self.repo.get_case(case_id)
        if not case:
            raise ServiceError("CASE_NOT_FOUND", 404)
        return case

    def get_document(self, case_id, document_id):
        self.get_case(case_id)
        document = self.repo.get("CASE#" + case_id, "DOC#" + document_id)
        if not document:
            raise ServiceError("DOCUMENT_NOT_FOUND", 404)
        return document

    def public_document(self, document):
        return {k: v for k, v in document.items() if k not in ("upload_token", "upload_expires_at", "source_key", "source_version", "result_key")}

    def list_documents(self, case_id):
        self.get_case(case_id)
        return {"documents": [self.public_document(d) for d in self.repo.list("CASE#" + case_id, "DOC#")]}

    def create_upload(self, case_id, request: UploadRequest):
        case = self.get_case(case_id)
        client = self.repo.get_client(case["client_id"])
        if not client:
            raise ServiceError("CLIENT_NOT_FOUND", 404)
        document_id, token = str(uuid4()), uuid4().hex + uuid4().hex
        document = {"schema_version": "1.0", "case_id": case_id, "client_id": case["client_id"],
                    "document_id": document_id, **request.model_dump(), "processing_status": "awaiting_upload",
                    "source_key": f"originals/{case_id}/{document_id}", "source_sha256": None,
                    "upload_token": hashlib.sha256(token.encode()).hexdigest(), "upload_expires_at": time.time() + 900,
                    "created_at": now(), "updated_at": now(), "job_id": None, "run_id": None}
        self.repo.create("CASE#" + case_id, "DOC#" + document_id, document)
        if self.settings.backend == "aws":
            url = self.blobs.upload_url(document["source_key"], request.content_type)
        else:
            url = f"{self.settings.public_url}/v1/uploads/{case_id}/{document_id}?token={token}"
        return {"document": self.public_document(document), "upload": {
            "method": "PUT", "url": url, "headers": {"Content-Type": request.content_type}, "expires_in": 900}}

    def verify_upload_token(self, case_id, document_id, token):
        document = self.get_document(case_id, document_id)
        if (document["upload_expires_at"] < time.time() or not hmac.compare_digest(
                document["upload_token"], hashlib.sha256(token.encode()).hexdigest())):
            raise ServiceError("UPLOAD_TOKEN_INVALID", 403)
        if document["processing_status"] != "awaiting_upload":
            raise ServiceError("UPLOAD_ALREADY_COMPLETED", 409)
        return document

    def complete_upload(self, case_id, document_id):
        document = self.get_document(case_id, document_id)
        if document.get("job_id"):
            job = self.repo.get("JOBS", document["job_id"])
            if job["status"] == "queued":
                self.enqueue(job)
            return {"job_id": job["job_id"], "document_id": document_id, "processing_status": document["processing_status"]}
        try:
            head = self.blobs.head(document["source_key"])
        except FileNotFoundError as error:
            raise ServiceError("UPLOAD_NOT_FOUND", 409) from error
        if head["size_bytes"] != document["size_bytes"] or head["size_bytes"] > self.settings.max_bytes:
            raise ServiceError("UPLOAD_SIZE_MISMATCH", 422)
        body = self.blobs.read(document["source_key"], head["version_id"])
        try:
            with open_document(body, document["content_type"], self.settings.max_pages) as pdf:
                page_count = len(pdf)
        except InvalidDocument as error:
            raise ServiceError(str(error), 422) from error
        source_hash = get_sha256(body)
        job_id = "job-" + document_id
        config = {"provider": self.settings.provider, "ocr_model": self.settings.ocr_model,
                  "extraction_model": self.settings.extraction_model, "mode": document["mode"],
                  "pipeline_version": PIPELINE_VERSION, "prompt_version": PROMPT_VERSION}
        config.update(bedrock_api=self.settings.bedrock_api, bedrock_region=self.settings.bedrock_region)
        job = {"job_id": job_id, "run_id": str(uuid4()), "case_id": case_id, "document_id": document_id,
               "status": "queued", "attempts": 0, "lease_until": 0, "created_at": now(),
               "source_sha256": source_hash, "source_version": head["version_id"], "page_count": page_count, "config": config,
               "config_hash": get_sha256(json.dumps(config, sort_keys=True).encode())}
        try:
            self.repo.create("JOBS", job_id, job)
        except Conflict:
            job = self.repo.get("JOBS", job_id)

        def finish(current):
            if current.get("job_id"):
                return current
            current.update({"job_id": job_id, "run_id": job["run_id"], "source_sha256": job["source_sha256"],
                            "source_version": job["source_version"], "page_count": job["page_count"],
                            "processing_status": "queued", "updated_at": now()})
            return current
        document = self.repo.update("CASE#" + case_id, "DOC#" + document_id, finish)
        self.enqueue(job)
        return {"job_id": job_id, "document_id": document_id, "processing_status": document["processing_status"]}

    def get_result(self, case_id, document_id):
        document = self.get_document(case_id, document_id)
        if not document.get("result_key"):
            raise ServiceError("RESULT_NOT_READY", 409)
        result = self.blobs.read_json(document["result_key"])
        corrections = self.repo.list("CORRECTIONS#" + document_id, result["run_id"] + "#")
        result["corrections"] = corrections
        for correction in corrections:
            for field in result["extraction"]["fields"]:
                if field["field_id"] == correction["field_id"]:
                    field.setdefault("original_normalized_value", field["normalized_value"])
                    field["normalized_value"] = correction["normalized_value"]
                    field["status"] = "human_corrected"
                    field["correction_id"] = correction["correction_id"]
        return result

    def correct_field(self, case_id, document_id, correction: Correction):
        from .extraction import normalize_value
        result = self.get_result(case_id, document_id)
        if result["run_id"] != correction.run_id:
            raise ServiceError("RUN_CHANGED", 409)
        field = next((f for f in result["extraction"]["fields"] if f["field_id"] == correction.field_id), None)
        if not field:
            raise ServiceError("FIELD_NOT_FOUND", 404)
        if correction.normalized_value is not None and normalize_value(field["key"], correction.normalized_value) != correction.normalized_value:
            raise ServiceError("CORRECTION_FORMAT_INVALID", 422)
        item = {**correction.model_dump(), "correction_id": str(uuid4()), "created_at": now(),
                "previous_value": field["normalized_value"], "actor": "local-reviewer" if self.settings.backend == "local" else "api-key-client"}
        self.repo.create("CORRECTIONS#" + document_id, item["run_id"] + "#" + item["created_at"] + "#" + item["correction_id"], item)
        return item

    def validation(self, case_id):
        case = self.get_case(case_id)
        documents = self.repo.list("CASE#" + case_id, "DOC#")
        results = [self.get_result(case_id, d["document_id"]) for d in documents if d.get("result_key")]
        client = self.repo.get_client(case["client_id"])
        if not client:
            raise ServiceError("CLIENT_NOT_FOUND", 404)
        return validate_case(case, client, results, documents)
