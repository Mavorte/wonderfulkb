"""Step facts from one evaluated document window; no paired state."""

import base64
import binascii
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from document_processing.audit.audit_events import STEP_ERROR_CODES
from processing_monitor_authorization import validate_identifier
from processing_monitor_routes import PRIVATE, authorized_document, read_authorized_window
from processing_monitor_page_routes import page_observations


router = APIRouter(prefix="/v1/cases/{case_id}/processing/documents/{document_id}")
FACT_FIELDS = {"event_id", "sequence", "occurred_at", "type", "stage", "run_id", "attempt_no"}
# Page terminals retain persisted identity/type; never synthesize StepFinished.
EXECUTED_PAGE_TYPES = {"StepStarted", "PageCompleted", "PageFailed"}
OBSERVATION_FIELDS = {
    ("StepStarted", "source_validation"): FACT_FIELDS,
    ("StepFinished", "source_validation"): FACT_FIELDS | {"duration_ms"},
    ("StepFailed", "source_validation"): FACT_FIELDS | {"duration_ms", "error_code"},
    ("StepStarted", "extraction"): FACT_FIELDS,
    ("StepFinished", "extraction"): FACT_FIELDS | {"duration_ms"},
    ("StepFailed", "extraction"): FACT_FIELDS | {"duration_ms", "error_code"},
}


def _wrap(reader, case_id, document_id, run_id, attempt_no):
    if reader is None:
        return None
    data = {"v": 1, "operation": "steps", "case_id": case_id, "document_id": document_id,
            "run_id": run_id, "attempt_no": attempt_no, "reader": reader}
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")


def _unwrap(token, case_id, document_id, run_id, attempt_no):
    if token is None:
        return None
    try:
        raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
        if len(raw) > 6144:
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
                or set(data) != {"v", "operation", "case_id", "document_id", "run_id", "attempt_no", "reader"}
                or type(data["v"]) is not int or data["v"] != 1
                or type(data["attempt_no"]) is not int
                or (data["operation"], data["case_id"], data["document_id"], data["run_id"], data["attempt_no"])
                != ("steps", case_id, document_id, run_id, attempt_no)
                or not isinstance(data["reader"], str) or not 1 <= len(data["reader"]) <= 4096):
            raise ValueError
        return data["reader"]
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        raise HTTPException(400, "invalid next_token") from None


def step_observations(events, run_id, attempt_no):
    items = []
    for event in events:
        if event.type in EXECUTED_PAGE_TYPES and getattr(event, "stage", None) == "page_transcription":
            items.extend(page_observations([event], run_id, attempt_no))
            continue
        fields = OBSERVATION_FIELDS.get((event.type, getattr(event, "stage", None)))
        if fields is None or event.run_id != run_id or event.attempt_no != attempt_no:
            continue
        item = {key: value for key, value in event.to_item().items() if key in fields}
        if "error_code" in item and item["error_code"] not in STEP_ERROR_CODES:
            raise ValueError("unsupported stored error code")
        items.append(jsonable_encoder(item))
    return items


@router.get("/runs/{run_id}/steps")
def steps(request: Request, case_id: str, document_id: str, run_id: str,
          attempt_no: int = Query(..., ge=1), limit: int = Query(50, ge=1, le=100),
          next_token: str | None = Query(None, min_length=1, max_length=8192)):
    scope = authorized_document(request, case_id, document_id)
    validate_identifier(run_id)
    reader = _unwrap(next_token, case_id, document_id, run_id, attempt_no)
    page = read_authorized_window(request, scope, limit, reader)
    try:
        return JSONResponse({"items": step_observations(page.items, run_id, attempt_no),
                             "next_token": _wrap(page.next_token, case_id, document_id, run_id, attempt_no),
                             "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                             "coverage": "partial"}, headers=PRIVATE)
    except Exception:
        raise HTTPException(503, "audit read unavailable") from None
