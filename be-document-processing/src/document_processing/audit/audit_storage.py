"""Best-effort writes and explicit, error-preserving audit reads."""

import os
from typing import Literal

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .audit_events import FileReceived, RunQueued, AttemptStarted, RetryEnqueued, AttemptFinished, RunFinished, StepStarted, StepFinished, StepFailed, PageCompleted, PageFailed, PageCacheReused
from .audit_events import ResultPublished
from .audit_queries import AuditPage, document_key, event_key, read_document


class AuditNotConfigured(RuntimeError):
    """Audit storage was explicitly disabled by configuration."""


PutResult = Literal["inserted", "duplicate", "disabled", "unavailable"]


class AuditStore:
    def __init__(self, table=None, *, initialization_error: Exception | None = None):
        self._table = table
        self._initialization_error = initialization_error
        self.enabled = table is not None or initialization_error is not None

    @classmethod
    def from_env(cls) -> "AuditStore":
        table_name = os.environ.get("AUDIT_TABLE_NAME", "").strip()
        if not table_name:
            return cls()
        try:
            resource = boto3.resource(
                "dynamodb", region_name="eu-central-1",
                config=Config(connect_timeout=1, read_timeout=2,
                              retries={"total_max_attempts": 1}),
            )
            return cls(resource.Table(table_name))
        except Exception as exc:
            # Preserve configured-but-unavailable separately from disabled.
            return cls(initialization_error=exc)

    def put(self, event: FileReceived | RunQueued | AttemptStarted | RetryEnqueued | AttemptFinished | RunFinished | StepStarted | StepFinished | StepFailed | PageCompleted | PageFailed | PageCacheReused | ResultPublished) -> PutResult:
        if not self.enabled:
            return "disabled"
        if self._initialization_error is not None:
            return "unavailable"
        try:
            item = event.to_item()
            item.update(pk=document_key(event.case_id, event.document_id),
                        sk=event_key(event.event_id))
            self._table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(pk) AND attribute_not_exists(sk)",
            )
            return "inserted"
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return "duplicate"
            return "unavailable"
        except Exception:
            # The audit boundary is deliberately fail-open, without payload logs.
            return "unavailable"

    def read_document(self, case_id: str, document_id: str, limit: int = 50,
                      next_token: str | None = None) -> AuditPage:
        if not self.enabled:
            raise AuditNotConfigured("Audit store is not configured")
        if self._initialization_error is not None:
            raise self._initialization_error
        return read_document(self._table, case_id, document_id, limit, next_token)
