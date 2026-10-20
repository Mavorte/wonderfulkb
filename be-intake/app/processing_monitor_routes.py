"""Shared authorization/membership facade and bounded document event endpoint.

The existing reader uses event-identity continuation, not global chronology.
The chronology contract remains an explicit acceptance blocker (see README).
"""

import base64
import binascii
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from document_processing.audit.audit_queries import _decode_token, document_key
from processing_monitor_authorization import authorize_document, validate_identifier


router = APIRouter(prefix="/v1/cases/{case_id}/processing/documents/{document_id}")
PRIVATE = {"Cache-Control": "private, no-store"}
PUBLIC_ENVELOPE = {"event_id", "case_id", "document_id", "sequence", "type", "occurred_at"}
PUBLIC_EVENT_FIELDS = {
    "FileReceived": (),
    "RunQueued": ("run_id",),
    "AttemptStarted": ("run_id", "attempt_no"),
    "StepStarted": ("run_id", "attempt_no", "stage", "page_number"),
    "StepFinished": ("run_id", "attempt_no", "stage", "duration_ms"),
    "StepFailed": ("run_id", "attempt_no", "stage", "duration_ms", "error_code"),
    "PageCacheReused": ("run_id", "attempt_no", "stage", "page_number", "cached_status", "cached_method", "cached_model", "artifact_ids"),
    "PageCompleted": ("run_id", "attempt_no", "stage", "page_number", "duration_ms", "method", "model"),
    "PageFailed": ("run_id", "attempt_no", "stage", "page_number", "error_code"),
    "ResultPublished": ("run_id", "attempt_no", "result_status", "artifact_ids"),
    "RetryEnqueued": ("run_id", "attempt_no", "reason_code"),
    "AttemptFinished": ("run_id", "attempt_no", "attempt_status", "duration_ms", "error_code"),
    "RunFinished": ("run_id", "attempt_no", "run_status", "error_code"),
}
PUBLIC_ERROR_CODES = {
    "StepFailed": {"PIPELINE_CONFIG_CHANGED", "SOURCE_HASH_MISMATCH", "PROCESSING_FAILED", "EXTRACTION_FAILED", "SIGNATURE_DETECTION_FAILED"},
    "AttemptFinished": {"PROCESSING_FAILED"},
    "RunFinished": {"RETRY_EXHAUSTED", "PROCESSING_FAILED"},
}


def authorized_document(request, case_id, document_id):
    """Shared seam for monitoring modules; no client scope claims are trusted."""
    return authorize_document(
        getattr(request.state, "processing_monitor_access", None),
        request.app.state.processing_monitor_documents, case_id, document_id,
    )


def read_authorized_window(request, scope, limit, next_token):
    """Distinguish invalid request cursors from stored-data decoder errors."""
    if next_token is not None:
        try:
            _decode_token(next_token, scope.case_id, scope.document_id,
                          document_key(scope.case_id, scope.document_id))
        except ValueError:
            raise HTTPException(400, "invalid next_token") from None
    try:
        page = request.app.state.processing_monitor_audit_store.read_document(
            scope.case_id, scope.document_id, limit, next_token,
        )
        if any(event.case_id != scope.case_id or event.document_id != scope.document_id for event in page.items):
            raise ValueError("stored scope mismatch")
        return page
    except Exception:
        raise HTTPException(503, "audit read unavailable") from None


def _wrap_run_cursor(reader, case_id, document_id, run_id, operation="run_events"):
    if reader is None:
        return None
    data = {"version": 1, "operation": operation, "case_id": case_id,
            "document_id": document_id, "run_id": run_id, "reader": reader}
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")


def _unwrap_run_cursor(token, case_id, document_id, run_id, operation="run_events"):
    if token is None:
        return None
    try:
        if not 1 <= len(token) <= 8192:
            raise ValueError
        raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
        # Accept only the canonical unpadded URL-safe encoding emitted here.
        if base64.urlsafe_b64encode(raw).decode().rstrip("=") != token:
            raise ValueError
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError
                result[key] = value
            return result
        data = json.loads(raw, object_pairs_hook=unique_object)
        if (not isinstance(data, dict)
                or set(data) != {"version", "operation", "case_id", "document_id", "run_id", "reader"}
                or type(data["version"]) is not int or data["version"] != 1
                or any(type(data[key]) is not str for key in ("operation", "case_id", "document_id", "run_id", "reader"))
                or (data["operation"], data["case_id"], data["document_id"], data["run_id"])
                != (operation, case_id, document_id, run_id)
                or not 1 <= len(data["reader"]) <= 4096):
            raise ValueError
        return data["reader"]
    except (ValueError, TypeError, UnicodeError, binascii.Error, RecursionError):
        raise HTTPException(400, "invalid next_token") from None


@router.get("/runs/{run_id}/events")
def run_events(request: Request, case_id: str, document_id: str, run_id: str,
               limit: int = Query(50, ge=1, le=100),
               next_token: str | None = Query(None, min_length=1, max_length=8192)):
    scope = authorized_document(request, case_id, document_id)
    validate_identifier(run_id)
    reader = _unwrap_run_cursor(next_token, case_id, document_id, run_id)
    page = read_authorized_window(request, scope, limit, reader)
    try:
        return JSONResponse({"items": [event_dto(event) for event in page.items
                                       if getattr(event, "run_id", None) == run_id],
                             "next_token": _wrap_run_cursor(page.next_token, case_id, document_id, run_id),
                             "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                             "coverage": "partial"}, headers=PRIVATE)
    except Exception:
        raise HTTPException(503, "audit read unavailable") from None


@router.get("/runs/{run_id}/attempts")
def run_attempts(request: Request, case_id: str, document_id: str, run_id: str,
                 limit: int = Query(50, ge=1, le=100),
                 next_token: str | None = Query(None, min_length=1, max_length=8192)):
    scope = authorized_document(request, case_id, document_id)
    validate_identifier(run_id)
    reader = _unwrap_run_cursor(next_token, case_id, document_id, run_id, "attempts")
    page = read_authorized_window(request, scope, limit, reader)
    try:
        return JSONResponse({"items": [attempt_dto(event) for event in page.items
                                       if event.type == "AttemptStarted" and event.run_id == run_id],
                             "next_token": _wrap_run_cursor(page.next_token, case_id, document_id, run_id, "attempts"),
                             "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                             "coverage": "partial"}, headers=PRIVATE)
    except Exception:
        raise HTTPException(503, "audit read unavailable") from None


def attempt_dto(event):
    # Event identities remain separate, including conflicting attempt ordinals.
    return {key: value for key, value in event.to_item().items()
            if key in {"event_id", "attempt_no", "occurred_at"}}


def event_dto(event):
    # Internal event serialization and the public DTO have different allowlists.
    fields = PUBLIC_ENVELOPE | set(PUBLIC_EVENT_FIELDS[event.type])
    item = {key: value for key, value in event.to_item().items() if key in fields}
    allowed_codes = PUBLIC_ERROR_CODES.get(event.type)
    if allowed_codes is not None and "error_code" in item and item["error_code"] not in allowed_codes:
        item["error_code"] = "PROCESSING_FAILED"
    if (event.type == "RetryEnqueued" and "reason_code" in item
            and item["reason_code"] not in {"RETRYABLE_FAILURE", "RETRY_EXHAUSTED", "PROCESSING_FAILED"}):
        # Optional internal diagnostic codes do not establish a public outcome.
        item.pop("reason_code")
    return jsonable_encoder(item)


@router.get("/events")
def document_events(request: Request, case_id: str, document_id: str,
                    limit: int = Query(50, ge=1, le=100),
                    next_token: str | None = Query(None, min_length=1, max_length=4096)):
    scope = authorized_document(request, case_id, document_id)
    page = read_authorized_window(request, scope, limit, next_token)
    try:
        return JSONResponse({"items": [event_dto(event) for event in page.items],
                             "next_token": page.next_token,
                             "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                             "coverage": "partial"}, headers=PRIVATE)
    except Exception:
        raise HTTPException(503, "audit read unavailable") from None
