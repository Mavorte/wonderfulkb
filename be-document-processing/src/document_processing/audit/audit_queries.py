"""One bounded document Query, with scope-bound continuation.

Ordering is technical event identity order, not chronology or a history snapshot.
Tokens are continuation hints, never authorization credentials.
"""

import base64
import binascii
import json
from dataclasses import dataclass

from boto3.dynamodb.conditions import Key

from .audit_events import AttemptStarted, FileReceived, RunQueued, RetryEnqueued, AttemptFinished, RunFinished, StepStarted, StepFinished, StepFailed, PageCompleted, PageFailed, PageCacheReused
from .audit_events import ResultPublished


@dataclass(frozen=True)
class AuditPage:
    items: list[FileReceived | RunQueued | AttemptStarted | RetryEnqueued | AttemptFinished | RunFinished | StepStarted | StepFinished | StepFailed | PageCompleted | PageFailed | PageCacheReused | ResultPublished]
    next_token: str | None


def document_key(case_id: str, document_id: str) -> str:
    for value in (case_id, document_id):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Document scope requires nonempty IDs")
    return json.dumps([case_id, document_id], ensure_ascii=True, separators=(",", ":"))


def event_key(event_id: str) -> str:
    return f"EVENT#{event_id}"


def _encode_token(case_id: str, document_id: str, key: dict) -> str:
    payload = {"version": 1, "operation": "document_events", "case_id": case_id,
               "document_id": document_id, "key": key}
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")


def _decode_token(token: str, case_id: str, document_id: str, pk: str) -> dict:
    try:
        if not isinstance(token, str) or not token or len(token) > 4096:
            raise ValueError("Invalid audit continuation token")
        payload = json.loads(base64.b64decode(
            token + "=" * (-len(token) % 4), altchars=b"-_", validate=True,
        ))
        if (not isinstance(payload, dict)
                or set(payload) != {"version", "operation", "case_id", "document_id", "key"}
                or type(payload["version"]) is not int or payload["version"] != 1
                or payload["operation"] != "document_events"
                or payload["case_id"] != case_id or payload["document_id"] != document_id):
            raise ValueError("Invalid audit continuation scope")
        key = payload["key"]
        if (not isinstance(key, dict) or set(key) != {"pk", "sk"}
                or key["pk"] != pk or not isinstance(key["sk"], str)
                or not key["sk"].startswith("EVENT#") or not key["sk"][6:].strip()):
            raise ValueError("Invalid audit continuation key")
        return key
    except (ValueError, TypeError, UnicodeError, binascii.Error) as exc:
        raise ValueError("Invalid audit continuation token") from exc


def read_document(table, case_id: str, document_id: str, limit: int = 50,
                  next_token: str | None = None) -> AuditPage:
    pk = document_key(case_id, document_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    params = {"KeyConditionExpression": Key("pk").eq(pk),
              "Limit": limit, "ConsistentRead": True}
    if next_token is not None:
        params["ExclusiveStartKey"] = _decode_token(next_token, case_id, document_id, pk)
    response = table.query(**params)
    key = response.get("LastEvaluatedKey")
    return AuditPage(
        items=[_event_from_item(item) for item in response["Items"]],
        next_token=_encode_token(case_id, document_id, key) if key else None,
    )


def _event_from_item(item: dict):
    event_type = item.get("type")
    event_class = {
        "FileReceived": FileReceived,
        "RunQueued": RunQueued,
        "AttemptStarted": AttemptStarted,
        "RetryEnqueued": RetryEnqueued,
        "AttemptFinished": AttemptFinished,
        "RunFinished": RunFinished,
        "StepStarted": StepStarted,
        "StepFinished": StepFinished,
        "StepFailed": StepFailed,
        "PageCompleted": PageCompleted,
        "PageFailed": PageFailed,
        "PageCacheReused": PageCacheReused,
        "ResultPublished": ResultPublished,
    }.get(event_type)
    if event_class is None:
        raise ValueError("Unsupported audit event type")
    return event_class.from_item(item)
