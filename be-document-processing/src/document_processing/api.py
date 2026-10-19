import base64
from contextlib import asynccontextmanager
import hmac
import json
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import TypeAdapter, ValidationError

from .bootstrap import CLIENTS, create_service
from .config import Settings
from .extraction import fold
from .models import AcceptedJob, CaseId, Correction, CreateCaseRequest, DocumentList, DocumentResult, DocumentType, UploadRequest, UploadResponse
from .pipeline import DocumentWorker, start_local_worker
from .repository import Conflict
from .service import ServiceError, now


def create_app(settings=None, service=None):
    settings = settings or Settings.from_env()
    service = service or create_service(settings)

    @asynccontextmanager
    async def lifespan(app):
        stop, thread = None, None
        if settings.backend == "local" and settings.worker_enabled:
            stop, thread = start_local_worker(DocumentWorker(service))
        yield
        if stop:
            stop.set()
            thread.join(timeout=2)

    app = FastAPI(title="wonderfulkb Document API", version="1.0.0", lifespan=lifespan)
    app.state.service = service
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origin.split(","),
                       allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type", "x-api-key"])

    @app.middleware("http")
    async def authenticate(request, call_next):
        # Local PUT uses an expiring, document-scoped upload token. In AWS the
        # gateway enforces its API key; the presigned S3 request bypasses this app.
        if (settings.api_key and request.url.path.startswith("/v1/") and not request.url.path.startswith("/v1/uploads/")
                and not hmac.compare_digest(request.headers.get("x-api-key", ""), settings.api_key)):
            return JSONResponse({"error": "API_KEY_REQUIRED"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(ServiceError)
    async def service_error(request, error):
        return JSONResponse({"error": error.code}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse({"error": "INVALID_REQUEST"}, status_code=422)

    @app.get("/health")
    def health():
        return {"status": "ok", "provider": settings.provider, "storage": settings.backend}

    @app.post("/v1/cases/{case_id}/documents", status_code=201, response_model=UploadResponse)
    def create_upload(case_id: CaseId, body: UploadRequest):
        return service.create_upload(case_id, body)

    @app.put("/v1/uploads/{case_id}/{document_id}", include_in_schema=settings.backend == "local")
    async def upload(case_id: CaseId, document_id: UUID, request: Request, token: str):
        if settings.backend != "local":
            raise ServiceError("NOT_FOUND", 404)
        document = service.verify_upload_token(case_id, str(document_id), token)
        if request.headers.get("content-type", "").split(";")[0] != document["content_type"]:
            raise ServiceError("CONTENT_TYPE_MISMATCH", 422)
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > min(settings.max_bytes, document["size_bytes"]):
                raise ServiceError("UPLOAD_TOO_LARGE", 413)
            chunks.append(chunk)
        if size != document["size_bytes"]:
            raise ServiceError("UPLOAD_SIZE_MISMATCH", 422)
        try:
            service.blobs.put(document["source_key"], b"".join(chunks), document["content_type"])
        except FileExistsError:
            raise ServiceError("UPLOAD_ALREADY_EXISTS", 409)
        return Response(status_code=204)

    @app.post("/v1/cases/{case_id}/documents/{document_id}/complete", status_code=202, response_model=AcceptedJob)
    def complete(case_id: CaseId, document_id: UUID):
        return service.complete_upload(case_id, str(document_id))

    @app.get("/v1/cases/{case_id}/documents", response_model=DocumentList)
    def documents(case_id: CaseId):
        return service.list_documents(case_id)

    @app.get("/v1/cases/{case_id}/documents/{document_id}/result", response_model=DocumentResult)
    def result(case_id: CaseId, document_id: UUID):
        return service.get_result(case_id, str(document_id))

    @app.get("/v1/cases/{case_id}/documents/{document_id}/pages/{page_number}")
    def preview(case_id: CaseId, document_id: UUID, page_number: Annotated[int, Path(ge=1)]):
        document = service.get_document(case_id, str(document_id))
        if page_number > document.get("page_count", 0):
            raise ServiceError("PAGE_NOT_FOUND", 404)
        key = f"previews/{case_id}/{document_id}/{page_number}.png"
        if settings.backend == "aws":
            url = service.blobs.client.generate_presigned_url("get_object", Params={"Bucket": settings.bucket, "Key": key}, ExpiresIn=300)
        else:
            try:
                body = service.blobs.read(key)
            except FileNotFoundError:
                raise ServiceError("PREVIEW_NOT_READY", 409)
            url = "data:image/png;base64," + base64.b64encode(body).decode()
        return {"image_url": url, "page_number": page_number}

    @app.post("/v1/cases/{case_id}/documents/{document_id}/corrections", status_code=201)
    def correct(case_id: CaseId, document_id: UUID, body: Correction):
        return service.correct_field(case_id, str(document_id), body)

    @app.get("/v1/cases/{case_id}/validation")
    def validate(case_id: CaseId):
        return service.validation(case_id)

    # Only the local development server supplies the missing Case & Client API.
    # The cloud document service reads the existing tables and owns no clients.
    if settings.backend == "local":
        @app.get("/v1/clients")
        def clients(ico: str | None = None, name: str | None = None, status: str | None = None,
                    limit: Annotated[int, Query(ge=1, le=100)] = 50, next_token: str | None = None):
            filters = [ico, name, status]
            offset = 0
            if next_token:
                try:
                    cursor = json.loads(base64.urlsafe_b64decode(next_token.encode()))
                    if cursor["filters"] != filters or not isinstance(cursor["offset"], int) or cursor["offset"] < 0:
                        raise ValueError()
                    offset = cursor["offset"]
                except Exception:
                    raise ServiceError("INVALID_PAGE_TOKEN")
            items = [service.repo.get_client(c["client_id"]) for c in CLIENTS]
            items = [c for c in items if (not ico or c["ico"] == ico) and
                     (not name or fold(name) in fold(c["name"])) and (not status or c["status"] == status)]
            following = offset + limit
            token = base64.urlsafe_b64encode(json.dumps({"filters": filters, "offset": following}).encode()).decode() if following < len(items) else None
            return {"clients": items[offset:following], "next_token": token}

        @app.post("/v1/cases")
        def create_case(body: CreateCaseRequest):
            try:
                UUID(body.client_id)
                required = (body.metadata or {}).get("required_document_types")
                if required is not None:
                    TypeAdapter(list[DocumentType]).validate_python(required)
            except (ValueError, ValidationError):
                raise ServiceError("INVALID_REQUEST")
            existing = service.repo.get_case(body.case_id)
            if existing:
                if existing["client_id"] != body.client_id:
                    raise ServiceError("CASE_CLIENT_CONFLICT", 409)
                return JSONResponse(existing, status_code=200)
            client = service.repo.get_client(body.client_id)
            if not client:
                raise ServiceError("CLIENT_NOT_FOUND", 404)
            if client["status"] != "active":
                raise ServiceError("CLIENT_NOT_ACTIVE", 409)
            item = {"case_id": body.case_id, "client_id": body.client_id, "status": "open", "created_at": now(), "metadata": body.metadata or {}}
            try:
                service.repo.create("CASE#" + body.case_id, "META", item)
                service.repo.create("CLIENT_CASES#" + body.client_id, item["created_at"] + "#" + body.case_id, item)
            except Conflict:
                existing = service.repo.get_case(body.case_id)
                if existing["client_id"] != body.client_id:
                    raise ServiceError("CASE_CLIENT_CONFLICT", 409)
                return JSONResponse(existing, status_code=200)
            return JSONResponse(item, status_code=201)

        @app.get("/v1/cases/{case_id}")
        def get_case(case_id: CaseId):
            return service.get_case(case_id)

        @app.get("/v1/clients/{client_id}/cases")
        def client_cases(client_id: UUID):
            if not service.repo.get_client(str(client_id)):
                raise ServiceError("CLIENT_NOT_FOUND", 404)
            return {"client_id": str(client_id), "cases": list(reversed(service.repo.list("CLIENT_CASES#" + str(client_id)))), "next_token": None}
    return app
