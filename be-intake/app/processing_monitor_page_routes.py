"""Page facts from one evaluated document window, without inferred page state."""

import base64
import binascii
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from document_processing.audit.audit_page_observations import to_page_observations
from processing_monitor_authorization import validate_identifier
from processing_monitor_routes import PRIVATE, authorized_document, read_authorized_window


router = APIRouter(prefix="/v1/cases/{case_id}/processing/documents/{document_id}")
PAGE_TYPES = {"StepStarted", "PageCompleted", "PageFailed", "PageCacheReused"}


def page_observations(events, run_id, attempt_no):
    # Filter mixed document events before the pure mapper's strict attempt validation.
    rows = [event.to_item() for event in events
            if event.type in PAGE_TYPES and getattr(event, "stage", None) == "page_transcription"
            and getattr(event, "page_number", None) is not None
            and event.run_id == run_id and event.attempt_no == attempt_no]
    return jsonable_encoder(to_page_observations(rows, run_id=run_id, attempt_no=attempt_no))


def _wrap(reader, case_id, document_id, run_id, attempt_no):
    if reader is None:
        return None
    data = {"version": 1, "operation": "pages", "case_id": case_id, "document_id": document_id,
            "run_id": run_id, "attempt_no": attempt_no, "reader": reader}
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")


def _unwrap(token, case_id, document_id, run_id, attempt_no):
    if token is None:
        return None
    try:
        raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
        if len(raw) > 3072:
            raise ValueError
        data = json.loads(raw)
        if (not isinstance(data, dict)
                or set(data) != {"version", "operation", "case_id", "document_id", "run_id", "attempt_no", "reader"}
                or type(data["version"]) is not int or data["version"] != 1
                or type(data["attempt_no"]) is not int
                or any(type(data[key]) is not str for key in ("operation", "case_id", "document_id", "run_id", "reader"))
                or (data["operation"], data["case_id"], data["document_id"], data["run_id"], data["attempt_no"])
                != ("pages", case_id, document_id, run_id, attempt_no)
                or not 1 <= len(data["reader"]) <= 4096):
            raise ValueError
        return data["reader"]
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        raise HTTPException(400, "invalid next_token") from None


@router.get("/runs/{run_id}/pages")
def pages(request: Request, case_id: str, document_id: str, run_id: str,
          attempt_no: int = Query(..., ge=1), limit: int = Query(50, ge=1, le=100),
          next_token: str | None = Query(None, min_length=1, max_length=4096)):
    scope = authorized_document(request, case_id, document_id)
    validate_identifier(run_id)
    reader = _unwrap(next_token, case_id, document_id, run_id, attempt_no)
    page = read_authorized_window(request, scope, limit, reader)
    try:
        return JSONResponse({"items": page_observations(page.items, run_id, attempt_no),
                             "next_token": _wrap(page.next_token, case_id, document_id, run_id, attempt_no),
                             "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                             "coverage": "partial"}, headers=PRIVATE)
    except Exception:
        raise HTTPException(503, "audit read unavailable") from None
