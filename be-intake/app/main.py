"""wonderfulkb-ingest: multipart upload of case documents to S3 + DynamoDB (part 2 of the ingest API)."""
import base64
import hashlib
import hmac
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

API_KEY = os.environ["API_KEY"]
BUCKET = os.environ["RAW_BUCKET"]
REGION = os.environ.get("AWS_REGION", "eu-central-1")

MAX_FILES = 20
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
URL_TTL_SECONDS = 300
CASE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
CASE_DOCS_PATH_RE = re.compile(r"^/v1/cases/([^/]+)/documents/?$")
DOC_NAMESPACE = uuid.UUID("5d3f0a52-7c1e-4a8b-9b36-6f1c2e0d7a11")

ddb = boto3.resource("dynamodb", region_name=REGION)
cases = ddb.Table(os.environ.get("CASES_TABLE", "wonderfulkb-uw-cases"))
docs = ddb.Table(os.environ.get("DOCS_TABLE", "wonderfulkb-uw-documents"))
# regional endpoint: the global one answers 307 for buckets outside us-east-1, which breaks presigned URLs
s3 = boto3.client("s3", region_name=REGION, endpoint_url=f"https://s3.{REGION}.amazonaws.com",
                  config=Config(signature_version="s3v4"))

app = FastAPI(title="wonderfulkb-ingest", docs_url=None, redoc_url=None, openapi_url=None)
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
    """Counts request body bytes, so the limit also holds for chunked uploads without Content-Length."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        total = 0

        async def counted():
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > MAX_TOTAL_BYTES + 1024 * 1024:
                    raise BodyTooLarge()
            return message

        await self.app(scope, counted, send)


@app.exception_handler(RequestValidationError)
async def validation_error(_, exc):
    return err(400, "invalid request: " + "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()))


@app.middleware("http")
async def guard(request: Request, call_next):
    """Auth and size limit run before the body is parsed, so unauthenticated uploads are never read."""
    if request.url.path == "/healthz":
        return await call_next(request)
    key = request.headers.get("x-api-key")
    if not key:
        return err(401, "missing x-api-key")
    if not hmac.compare_digest(key.encode(), API_KEY.encode()):
        return err(403, "invalid API key")
    match = CASE_DOCS_PATH_RE.match(request.url.path)
    if match:  # unknown case_id is rejected before the (possibly 100 MB) body is read
        try:
            await run_in_threadpool(require_case, match.group(1))
        except HTTPException as e:
            return err(e.status_code, str(e.detail))
    length = request.headers.get("content-length")
    if request.method == "POST" and length and length.isdigit() and int(length) > MAX_TOTAL_BYTES + 1024 * 1024:
        return err(413, f"request too large (limit {MAX_TOTAL_BYTES} bytes of files)")
    return await call_next(request)


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
    if not head:
        raise HTTPException(400, f"{clean_filename(upload.filename)} is empty")
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


def public(item, duplicate=None):
    out = {"document_id": item["document_id"], "filename": item["filename"], "received_at": item["received_at"],
           "content_type": item["content_type"], "size_bytes": int(item["size_bytes"])}
    if duplicate is not None:
        out["duplicate"] = duplicate
    return out


@router.post("/cases/{case_id}/documents", status_code=201)
def upload(case_id: str, files: List[UploadFile] = File(...), uploaded_by: Optional[str] = Form(None)):
    if uploaded_by is not None and len(uploaded_by) > 255:
        raise HTTPException(400, "uploaded_by is longer than 255 characters")
    if not 0 < len(files) <= MAX_FILES:
        raise HTTPException(400, f"send 1-{MAX_FILES} files in the 'files' field")

    # validate everything first; nothing is written when any file is invalid
    prepared, total = [], 0
    for upload_file in files:
        size, sha = inspect(upload_file)
        if size == 0:
            raise HTTPException(400, f"{clean_filename(upload_file.filename)} is empty")
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
    items = {}
    received_at = now_iso()
    for document_id, (upload_file, size, sha) in pending.items():
        key = f"cases/{case_id}/original/{document_id}.pdf"
        filename = clean_filename(upload_file.filename)
        # S3 metadata must be ASCII and max 2 KB in total: URL-encoded and cut; DynamoDB holds the full values
        meta = {"case_id": case_id, "document_id": document_id, "sha256": sha, "filename": quote(filename[:100])}
        if uploaded_by:
            meta["uploaded_by"] = quote(uploaded_by[:100])
        s3.upload_fileobj(upload_file.file, BUCKET, key,
                          ExtraArgs={"ContentType": "application/pdf", "Metadata": meta})
        item = {"case_id": case_id, "document_id": document_id, "filename": filename,
                "content_type": "application/pdf", "size_bytes": size, "sha256": sha, "received_at": received_at,
                "s3_key": key}
        if uploaded_by:
            item["uploaded_by"] = uploaded_by
        items[document_id] = item

    # 3) commit point: all new rows in ONE DynamoDB transaction, so the case lists all new documents or none.
    #    If a concurrent identical upload wins some row, the transaction is cancelled as a whole; we then
    #    treat the winners as duplicates and retry with the rest.
    for _ in range(3):
        todo = [item for document_id, item in items.items() if document_id not in existing]
        if not todo:
            break
        try:
            ddb.meta.client.transact_write_items(TransactItems=[
                {"Put": {"TableName": docs.name, "Item": item,  # the resource client serializes native values itself
                         "ConditionExpression": "attribute_not_exists(document_id)"}} for item in todo])
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

    out, seen = [], set()
    for document_id, *_ in plan:
        if document_id in existing:
            out.append(public(existing[document_id], duplicate=True))
        else:
            out.append(public(items[document_id], duplicate=document_id in seen))
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
app.add_middleware(BodyLimit)
