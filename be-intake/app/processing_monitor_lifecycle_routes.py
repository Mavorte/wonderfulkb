"""Bounded lifecycle views, gated on a service-owned trusted entitlement provider.

The shared API key authenticates a service, not a case reader. Until the owning
service installs ``app.state.lifecycle_authorize_read`` and its audit table,
the default is denial without an audit read.
"""

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from document_processing.audit.audit_queries import read_document, document_key, _decode_token
from document_processing.audit.audit_lifecycle_observations import reduce_observations


router = APIRouter(prefix="/v1/cases/{case_id}/processing/documents/{document_id}")
PRIVATE = {"Cache-Control": "private, no-store"}


@dataclass(frozen=True)
class AuthorizedDocumentScope:
    """Issued only by the service owner's trusted caller-to-case/document policy."""

    case_id: str
    document_id: str


def _error(code, message):
    return JSONResponse({"error": message}, status_code=code, headers=PRIVATE)


def _authorize(request, case_id, document_id):
    provider = getattr(request.app.state, "lifecycle_authorize_read", None)
    if not callable(provider):
        return None
    try:
        scope = provider(request, case_id, document_id)
    except HTTPException as exc:
        if exc.status_code in (403, 404):
            return _error(exc.status_code, "case read access denied" if exc.status_code == 403 else "not found")
        return _error(403, "case read access denied")
    except Exception:
        return _error(403, "case read access unavailable")
    if (type(scope) is not AuthorizedDocumentScope or scope.case_id != case_id
            or scope.document_id != document_id):
        return _error(403, "case read access denied")
    return scope


def _wrap(token, operation, case_id, document_id, run_id):
    if token is None:
        return None
    data = {"v": 1, "operation": operation, "case_id": case_id,
            "document_id": document_id, "run_id": run_id, "reader": token}
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")


def _unwrap(token, operation, case_id, document_id, run_id):
    if token is None:
        return None
    try:
        if not isinstance(token, str) or not token or len(token) > 8192:
            raise ValueError
        raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
        data = json.loads(raw)
        if (not isinstance(data, dict) or set(data) != {"v", "operation", "case_id", "document_id", "run_id", "reader"}
                or type(data["v"]) is not int or data["v"] != 1
                or (data["operation"], data["case_id"], data["document_id"], data["run_id"])
                != (operation, case_id, document_id, run_id)
                or not isinstance(data["reader"], str) or not data["reader"]):
            raise ValueError
        return data["reader"]
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        raise HTTPException(400, "invalid next_token") from None


def _evidence(evidence):
    return [{"event_id": item.event_id, "sequence": item.sequence, "event_type": item.event_type}
            for item in evidence]


def _run(item):
    return {"run_id": item.run_id, "state": item.state, "evidence": _evidence(item.evidence)}


def _attempt(item):
    return {"run_id": item.run_id, "attempt_id": item.attempt_id,
            "attempt_number": item.attempt_number, "terminal_state": item.terminal_state,
            "evidence": _evidence(item.evidence)}


def _publication(item):
    return {"run_id": item.run_id, "publication_id": item.publication_id,
            "evidence": _evidence(item.evidence)}


def _window(request, case_id, document_id, operation, run_id, limit, next_token):
    scope = _authorize(request, case_id, document_id)
    if scope is None:
        return _error(403, "case read access unavailable")
    if isinstance(scope, JSONResponse):
        return scope
    try:
        reader_token = _unwrap(next_token, operation, case_id, document_id, run_id)
        if reader_token is not None:
            _decode_token(reader_token, case_id, document_id, document_key(case_id, document_id))
    except (HTTPException, ValueError):
        return _error(400, "invalid next_token")
    table = getattr(request.app.state, "lifecycle_audit_table", None)
    if table is None:
        return _error(503, "audit read unavailable")
    try:
        page = read_document(table, case_id, document_id, limit=limit, next_token=reader_token)
        # The reader is the only data source; reducer sees precisely this evaluated window.
        summary = reduce_observations([event.to_item() for event in page.items], next_token=page.next_token)
    except Exception:
        return _error(503, "audit read unavailable")
    result = {"observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
              "coverage": summary.coverage, "availability": summary.availability,
              "next_token": _wrap(page.next_token, operation, case_id, document_id, run_id)}
    if operation == "runs":
        result["items"] = [_run(item) for item in summary.runs]
    elif operation == "detail":
        match = next((item for item in summary.runs if item.run_id == run_id), None)
        result["items"] = [{**(_run(match) if match else {"run_id": run_id, "state": "unknown", "evidence": []}),
                            "attempts": [_attempt(item) for item in summary.attempts if item.run_id == run_id],
                            "published_results": [_publication(item) for item in summary.published_results
                                                  if item.run_id == run_id]}]
    else:
        result["items"] = [{"document_id": document_id, "runs": [_run(item) for item in summary.runs],
                            "attempts": [_attempt(item) for item in summary.attempts],
                            "published_results": [_publication(item) for item in summary.published_results],
                            "unscoped_evidence": _evidence(summary.unscoped_evidence),
                            "conflicts": [{"evidence": _evidence(item.evidence)} for item in summary.conflicts]}]
    return JSONResponse(result, headers=PRIVATE)


@router.get("/runs")
def observed_runs(request: Request, case_id: str, document_id: str,
                  limit: int = Query(50, ge=1, le=100), next_token: Optional[str] = None):
    return _window(request, case_id, document_id, "runs", None, limit, next_token)


@router.get("/runs/{run_id}")
def observed_run(request: Request, case_id: str, document_id: str, run_id: str,
                 limit: int = Query(50, ge=1, le=100), next_token: Optional[str] = None):
    return _window(request, case_id, document_id, "detail", run_id, limit, next_token)


@router.get("/audit")
def observed_audit(request: Request, case_id: str, document_id: str,
                   limit: int = Query(50, ge=1, le=100), next_token: Optional[str] = None):
    return _window(request, case_id, document_id, "audit", None, limit, next_token)
