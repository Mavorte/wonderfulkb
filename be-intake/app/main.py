"""wonderfulkb-ingest: multipart upload of case documents to S3 + DynamoDB (part 2 of the ingest API)."""
import base64
import hashlib
import hmac
import logging
import os
import posixpath
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import quote

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import APIRouter, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

import content_hashes
from processing_monitor_lifecycle_routes import router as lifecycle_router
from processing_monitor_authorization import ServiceDocumentAuthorizer
from processing_monitor_authorization import AuthorizationSecretSource, authorize_case
from processing_monitor_routes import router as monitor_router
from processing_monitor_page_routes import router as page_router
from processing_monitor_step_routes import router as step_router
from document_processing.audit.audit_storage import AuditStore
from document_processing.audit.audit_listener import AuditListener, from_env as audit_from_env

API_KEY = os.environ["API_KEY"]
BUCKET = os.environ["RAW_BUCKET"]
REGION = os.environ.get("AWS_REGION", "eu-central-1")

MAX_FILES = 20
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
URL_TTL_SECONDS = 300
CASE_ID_RE = re.compile(r"^(?!\.{1,2}$)[A-Za-z0-9._-]{1,128}$")  # "." and ".." would be path segments
CASE_DOCS_PATH_RE = re.compile(r"^/v1/cases/([^/]+)/documents/?$")
DOC_NAMESPACE = uuid.UUID("5d3f0a52-7c1e-4a8b-9b36-6f1c2e0d7a11")

log = logging.getLogger("wonderfulkb-ingest")
logging.basicConfig(level=logging.INFO)

ddb = boto3.resource("dynamodb", region_name=REGION)
cases = ddb.Table(os.environ.get("CASES_TABLE", "wonderfulkb-uw-cases"))
docs = ddb.Table(os.environ.get("DOCS_TABLE", "wonderfulkb-uw-documents"))
# regional endpoint: the global one answers 307 for buckets outside us-east-1, which breaks presigned URLs
s3 = boto3.client("s3", region_name=REGION, endpoint_url=f"https://s3.{REGION}.amazonaws.com",
                  config=Config(signature_version="s3v4"))

app = FastAPI(title="wonderfulkb-ingest", docs_url=None, redoc_url=None, openapi_url=None)
app.state.audit_listener = audit_from_env()
monitor_config = Config(connect_timeout=1, read_timeout=2, retries={"total_max_attempts": 1})
monitor_secret_arn = os.environ.get("MONITOR_AUTH_SECRET_ARN", "").strip()
monitor_secrets = None
try:
    if monitor_secret_arn:
        monitor_secrets = boto3.client("secretsmanager", region_name=REGION, config=monitor_config)
except Exception:
    pass  # Configured but unavailable remains fail-closed without payload logging.
monitor_documents = docs
app.state.lifecycle_audit_table = None
try:
    monitor_ddb = boto3.resource("dynamodb", region_name=REGION, config=monitor_config)
    monitor_documents = monitor_ddb.Table(os.environ.get("DOCS_TABLE", "wonderfulkb-uw-documents"))
    audit_table_name = os.environ.get("AUDIT_TABLE_NAME", "").strip()
    if audit_table_name:
        app.state.lifecycle_audit_table = monitor_ddb.Table(audit_table_name)
except Exception:
    monitor_documents = None
app.state.lifecycle_authorize_read = ServiceDocumentAuthorizer(monitor_secrets, monitor_secret_arn, monitor_documents)
app.state.processing_monitor_authorization_source = AuthorizationSecretSource.from_env()
if not app.state.processing_monitor_authorization_source.arn and monitor_secret_arn:
    app.state.processing_monitor_authorization_source = AuthorizationSecretSource(monitor_secret_arn, monitor_secrets)
app.state.processing_monitor_audit_store = AuditStore.from_env()
app.state.processing_monitor_documents = monitor_documents
router = APIRouter(prefix="/v1")


def err(code, message):
    return JSONResponse({"error": message}, status_code=code)


@app.exception_handler(HTTPException)
async def http_error(_, exc):
    return err(exc.status_code, str(exc.detail))


class BodyTooLarge(Exception):
    pass


@app.exception_handler(BodyTooLarge)
async def body_too_large(_, exc):
    return err(413, f"request too large (limit {MAX_TOTAL_BYTES} bytes of files)")


@app.exception_handler(Exception)
async def unhandled(_, exc):
    print(f"unhandled error: {type(exc).__name__}: {exc}", flush=True)
    return err(500, "internal error")


class BodyLimit:
    """Counts request body bytes, so the limit also holds for chunked uploads without Content-Length.
    The multipart parser turns the exception from receive() into a 400, so once the limit is hit the app's own
    response is dropped and a 413 is sent instead."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        total, exceeded, started = 0, False, False

        async def counted():
            nonlocal total, exceeded
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > MAX_TOTAL_BYTES + 1024 * 1024:
                    exceeded = True
                    raise BodyTooLarge()
            return message

        async def guarded_send(message):
            nonlocal started
            if exceeded and not started:
                return
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, counted, guarded_send)
        except BodyTooLarge:
            pass
        if exceeded and not started:
            await err(413, f"request too large (limit {MAX_TOTAL_BYTES} bytes of files)")(scope, receive, send)


@app.exception_handler(RequestValidationError)
async def validation_error(_, exc):
    return err(400, "invalid request: " + "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()))


@app.middleware("http")
async def guard(request: Request, call_next):
    """Auth and size limit run before the body is parsed, so unauthenticated uploads are never read."""
    monitor = re.match(r"^/v1/cases/([^/]+)/processing/documents(?:/|$)", request.url.path)
    async def respond(response):
        if monitor:
            response.headers["Cache-Control"] = "private, no-store"
        return response
    if request.url.path == "/healthz":
        return await call_next(request)
    lifecycle = re.match(r"^/v1/cases/[^/]+/processing/documents/[^/]+/(?:runs(?:/[^/]+)?|audit)/?$", request.url.path)
    if monitor and not lifecycle:
        try:
            request.state.processing_monitor_access = await run_in_threadpool(
                authorize_case, request.app.state.processing_monitor_authorization_source,
                request.headers.get("authorization"), monitor.group(1),
            )
            return await respond(await call_next(request))
        except HTTPException as exc:
            return await respond(err(exc.status_code, str(exc.detail)))
        except Exception:
            return await respond(err(500, "internal error"))
    key = request.headers.get("x-api-key")
    if not key:
        return await respond(err(401, "missing x-api-key"))
    if not hmac.compare_digest(key.encode(), API_KEY.encode()):
        return await respond(err(403, "invalid API key"))
    match = CASE_DOCS_PATH_RE.match(request.url.path)
    if match:  # unknown case_id is rejected before the (possibly 100 MB) body is read
        try:
            await run_in_threadpool(require_case, match.group(1))
        except HTTPException as e:
            return err(e.status_code, str(e.detail))
    length = request.headers.get("content-length")
    if request.method == "POST" and length and length.isdigit() and int(length) > MAX_TOTAL_BYTES + 1024 * 1024:
        return err(413, f"request too large (limit {MAX_TOTAL_BYTES} bytes of files)")
    return await respond(await call_next(request))


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def require_case(case_id):
    if not CASE_ID_RE.fullmatch(case_id):
        raise HTTPException(400, "case_id must be 1-128 chars of A-Z a-z 0-9 . _ -")
    if "Item" not in cases.get_item(Key={"case_id": case_id}, ConsistentRead=True):
        raise HTTPException(404, "case not found")


def clean_filename(name):
    name = posixpath.basename((name or "").replace("\\", "/"))
    name = "".join(c for c in name if c.isprintable())[:255].strip()
    return name or "document.pdf"


def inspect(upload):
    """Returns (size, sha256) and verifies the PDF header; leaves the file rewound."""
    f = upload.file
    head = f.read(5)
    if not head:  # the contract: an empty file is not a PDF either
        raise HTTPException(415, f"{clean_filename(upload.filename)} is empty, not a PDF")
    if head != b"%PDF-":
        raise HTTPException(415, f"{clean_filename(upload.filename)} is not a PDF")
    f.seek(0)
    sha, size = hashlib.sha256(), 0
    while chunk := f.read(1024 * 1024):
        sha.update(chunk)
        size += len(chunk)
    f.seek(0)
    if size > MAX_FILE_BYTES:
        raise HTTPException(413, f"{clean_filename(upload.filename)} exceeds {MAX_FILE_BYTES} bytes")
    return size, sha.hexdigest()


def public(item, duplicate=None, also_in=None):
    out = {"document_id": item["document_id"], "filename": item["filename"], "received_at": item["received_at"],
           "content_type": item["content_type"], "size_bytes": int(item["size_bytes"])}
    if duplicate is not None:
        out["duplicate"] = duplicate
    if also_in is not None:  # None = index hashů nedostupný, pole se vynechá (prázdný seznam = nikde jinde není)
        out["also_in"] = also_in
    return out


def find_in_other_cases(case_id, hashes):
    """{sha256: [{case_id, document_id}]} pro stejný obsah v jiných případech. Chyba indexu = {} (pole se vynechá);
    do logu jde jen typ chyby, nikdy hash, id ani obsah."""
    if not content_hashes.enabled():
        return {}
    found = {}
    for sha in hashes:
        try:
            found[sha] = content_hashes.lookup_other_cases(sha, case_id)
        except Exception as e:  # noqa: BLE001 - výpadek indexu nesmí shodit nahrání
            log.warning("content hash lookup failed: %s", type(e).__name__)
            return {}
    return found


def register_hashes(case_id, entries):
    """Zaregistruje [(sha256, document_id)] v indexu; chyba se jen zaloguje (typ chyby)."""
    if not content_hashes.enabled():
        return
    for sha, document_id in entries:
        try:
            content_hashes.register(sha, case_id, document_id)
        except Exception as e:  # noqa: BLE001
            log.warning("content hash register failed: %s", type(e).__name__)


def store_and_commit(case_id, uploaded_by, pending, items, ours, existing, received_at):
    """S3 then metadata; fill items/ours/existing and return only rows committed by this request."""
    for document_id, (upload_file, size, sha) in pending.items():
        key = f"cases/{case_id}/original/{document_id}.pdf"
        filename = clean_filename(upload_file.filename)
        # S3 metadata must be ASCII and max 2 KB in total: URL-encoded and cut; DynamoDB holds the full values
        meta = {"case_id": case_id, "document_id": document_id, "sha256": sha, "filename": quote(filename[:100])}
        if uploaded_by:
            meta["uploaded_by"] = quote(uploaded_by[:100])
        # conditional put: a concurrent upload of the same content never overwrites the first object and its
        # metadata (412 = the object is there already; its content is the same, the key is derived from sha256)
        try:
            ours[document_id] = s3.put_object(Bucket=BUCKET, Key=key, Body=upload_file.file, IfNoneMatch="*",
                                              ContentType="application/pdf", Metadata=meta).get("VersionId")
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") not in ("PreconditionFailed", "ConditionalRequestConflict"):
                raise
        item = {"case_id": case_id, "document_id": document_id, "filename": filename,
                "content_type": "application/pdf", "size_bytes": size, "sha256": sha, "received_at": received_at,
                "s3_key": key}
        if uploaded_by:
            item["uploaded_by"] = uploaded_by
        items[document_id] = item

    # 3) commit point: all new rows in ONE DynamoDB transaction, so the case lists all new documents or none.
    #    If a concurrent identical upload wins some row, the transaction is cancelled as a whole; we then
    #    treat the winners as duplicates and retry with the rest.
    committed = []
    for _ in range(3):
        todo = [item for document_id, item in items.items() if document_id not in existing]
        if not todo:
            break
        try:
            ddb.meta.client.transact_write_items(TransactItems=[
                {"Put": {"TableName": docs.name, "Item": item,  # the resource client serializes native values itself
                         "ConditionExpression": "attribute_not_exists(document_id)"}} for item in todo])
            committed = todo
            break
        except ClientError as e:
            reasons = e.response.get("CancellationReasons", [])
            if e.response["Error"]["Code"] != "TransactionCanceledException" or any(
                    r.get("Code") not in ("ConditionalCheckFailed", "None") for r in reasons):
                raise  # only a lost race (condition failed) is retried; anything else is a real error
            for item in todo:
                row = docs.get_item(Key={"case_id": case_id, "document_id": item["document_id"]},
                                    ConsistentRead=True).get("Item")
                if row:
                    existing[item["document_id"]] = row
    else:
        raise HTTPException(409, "concurrent upload, please retry")
    return committed


def remove_uncommitted(case_id, ours):
    """The request failed: delete the S3 versions it created, but only where no DynamoDB row references the key
    (a row of a concurrent winner may point to our object). Errors are logged, the original error is kept."""
    for document_id, version_id in ours.items():
        try:
            if docs.get_item(Key={"case_id": case_id, "document_id": document_id}, ConsistentRead=True).get("Item"):
                continue
            key = f"cases/{case_id}/original/{document_id}.pdf"
            s3.delete_object(Bucket=BUCKET, Key=key, **({"VersionId": version_id} if version_id else {}))
        except Exception as e:  # noqa: BLE001
            log.warning("cleanup of uploaded object failed: %s", type(e).__name__)


@router.post("/cases/{case_id}/documents", status_code=201)
def upload(case_id: str, request: Request, files: List[UploadFile] = File(...), uploaded_by: Optional[str] = Form(None),
           include_also_in: bool = Query(False)):
    if uploaded_by is not None and len(uploaded_by) > 255:
        raise HTTPException(400, "uploaded_by is longer than 255 characters")
    if not 0 < len(files) <= MAX_FILES:
        raise HTTPException(400, f"send 1-{MAX_FILES} files in the 'files' field")

    # validate everything first; nothing is written when any file is invalid
    prepared, total = [], 0
    for upload_file in files:
        size, sha = inspect(upload_file)
        total += size
        prepared.append((upload_file, size, sha))
    if total > MAX_TOTAL_BYTES:
        raise HTTPException(413, f"request too large ({total} bytes, limit {MAX_TOTAL_BYTES})")

    # 1) plan: one entry per distinct content; what already exists in this case is a duplicate
    plan = []  # (document_id, upload_file, size, sha)
    for upload_file, size, sha in prepared:
        plan.append((str(uuid.uuid5(DOC_NAMESPACE, f"{case_id}:{sha}")), upload_file, size, sha))
    existing = {}
    for document_id in {p[0] for p in plan}:
        item = docs.get_item(Key={"case_id": case_id, "document_id": document_id}, ConsistentRead=True).get("Item")
        if item:
            existing[document_id] = item
    pending = {}  # document_id -> (upload_file, size, sha), first occurrence wins
    for document_id, upload_file, size, sha in plan:
        if document_id not in existing and document_id not in pending:
            pending[document_id] = (upload_file, size, sha)

    # 2) objects to S3 first; they are invisible until their DynamoDB rows exist
    items, ours = {}, {}  # ours: document_id -> S3 version this request created (deleted again if the request fails)
    received_at = now_iso()
    try:
        committed = store_and_commit(case_id, uploaded_by, pending, items, ours, existing, received_at)
    except BaseException:
        remove_uncommitted(case_id, ours)
        raise

    audit: AuditListener = request.app.state.audit_listener
    for row in committed:
        audit.file_received(case_id=row["case_id"], document_id=row["document_id"], occurred_at=row["received_at"])

    # 4) stejný obsah v jiných případech (jen informace; index nikdy nesmí způsobit selhání) a registrace v indexu
    shas = {document_id: sha for document_id, _, _, sha in plan}
    # `also_in` prozrazuje ID cizích případů, proto jen na výslovné vyžádání (?include_also_in=true) důvěryhodným volajícím
    elsewhere = find_in_other_cases(case_id, sorted(set(shas.values()))) if include_also_in else {}
    register_hashes(case_id, sorted((sha, document_id) for document_id, sha in shas.items()))

    out, seen = [], set()
    for document_id, *_ in plan:
        also_in = elsewhere.get(shas[document_id])
        if document_id in existing:
            out.append(public(existing[document_id], duplicate=True, also_in=also_in))
        else:
            out.append(public(items[document_id], duplicate=document_id in seen, also_in=also_in))
        seen.add(document_id)
    return JSONResponse({"case_id": case_id, "documents": out}, status_code=201)


@router.get("/cases/{case_id}/documents")
def list_documents(case_id: str, limit: int = Query(50, ge=1, le=100), next_token: Optional[str] = None,
                   with_urls: bool = False):
    try:
        offset = int(base64.urlsafe_b64decode(next_token.encode()).decode()) if next_token else 0
        if offset < 0:
            raise ValueError
    except ValueError:
        raise HTTPException(400, "invalid next_token")

    items, kwargs = [], {"KeyConditionExpression": Key("case_id").eq(case_id)}
    while True:
        page = docs.query(**kwargs)
        items += page["Items"]
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    items.sort(key=lambda i: (i["received_at"], i["document_id"]))

    chunk = items[offset:offset + limit]
    result = []
    for item in chunk:
        doc = public(item)
        if item.get("uploaded_by"):
            doc["uploaded_by"] = item["uploaded_by"]
        if with_urls:
            doc["download_url"] = s3.generate_presigned_url(
                "get_object", ExpiresIn=URL_TTL_SECONDS,
                Params={"Bucket": BUCKET, "Key": item["s3_key"], "ResponseContentType": "application/pdf",
                        "ResponseContentDisposition": f"inline; filename*=UTF-8''{quote(item['filename'])}"})
        result.append(doc)
    more = offset + limit < len(items)
    token = base64.urlsafe_b64encode(str(offset + limit).encode()).decode() if more else None
    return {"case_id": case_id, "documents": result, "next_token": token}


app.include_router(router)
app.include_router(lifecycle_router)
app.include_router(monitor_router)
app.include_router(page_router)
app.include_router(step_router)
app.add_middleware(BodyLimit)
