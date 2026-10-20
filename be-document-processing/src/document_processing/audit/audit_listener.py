"""Small injected, fail-open boundary for confirmed document intake."""

import json
from datetime import datetime, timezone
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from .audit_events import FileReceived, RunQueued, AttemptStarted
from .audit_storage import AuditStore
from . import audit_events


def dispatch(listener_factory, callback_name, **values):
    """Isolate dependency lookup as well as listener code, including after a commit."""
    try:
        getattr(listener_factory(), callback_name)(**values)
    except Exception:
        pass


class ExecutionAudit:
    """Explicit per-call identity; never stored in warm Options or inferred from SQS."""
    def __init__(self, context, listener_factory):
        self.context = context
        self.listener_factory = listener_factory

    def emit(self, kind, **fields):
        if self.context is None:
            return
        try:
            context = self.context
            dispatch(self.listener_factory, "observe", kind=kind,
                     case_id=context.case_id, document_id=context.document_id,
                     run_id=context.run_id, attempt_no=context.attempt_no,
                     occurred_at=datetime.now(timezone.utc).isoformat(), **fields)
        except Exception:
            pass


class AuditListener(Protocol):
    def observe(self, *, kind: str, **fields) -> None: ...
    def file_received(self, *, case_id: str, document_id: str, occurred_at: str) -> None: ...
    def run_queued(self, *, case_id: str, document_id: str, run_id: str, occurred_at: str) -> None: ...
    def attempt_started(self, *, case_id: str, document_id: str, run_id: str,
                        attempt_no: int, occurred_at: str) -> None: ...


class NoOpAudit:
    def observe(self, **kwargs) -> None:
        pass

    def file_received(self, *, case_id: str, document_id: str, occurred_at: str) -> None:
        pass

    def run_queued(self, **kwargs) -> None:
        pass

    def attempt_started(self, **kwargs) -> None:
        pass


class FileReceivedAudit:
    def __init__(self, store: AuditStore):
        self._store = store

    def observe(self, *, kind, **fields):
        try:
            event_type = getattr(audit_events, kind)
            identity = json.dumps(["wonderfulkb.audit.v1", kind, fields["case_id"],
                fields["document_id"], fields["run_id"], fields["attempt_no"],
                fields.get("stage"), fields.get("page_number")], separators=(",", ":"))
            self._store.put(event_type(schema_version=1, sequence=0, type=kind,
                event_id=str(uuid5(NAMESPACE_URL, identity)), **fields))
        except Exception:
            pass

    def file_received(self, *, case_id: str, document_id: str, occurred_at: str) -> None:
        try:
            identity = json.dumps(
                ["wonderfulkb.audit.v1", "FileReceived", case_id, document_id],
                ensure_ascii=True, separators=(",", ":"),
            )
            event = FileReceived(
                schema_version=1, event_id=str(uuid5(NAMESPACE_URL, identity)),
                case_id=case_id, document_id=document_id, sequence=0,
                type="FileReceived", occurred_at=occurred_at,
            )
            self._store.put(event)
        except Exception:
            # Creation, validation, serialization and sink failure cannot affect intake.
            # No payload logging, retry or recovery: this is best-effort telemetry.
            pass

    def _execution_event(self, kind, case_id, document_id, run_id, occurred_at, attempt_no=None):
        try:
            identity = json.dumps(["wonderfulkb.audit.v1", kind.__name__, case_id, document_id,
                                   run_id, attempt_no], ensure_ascii=True, separators=(",", ":"))
            fields = dict(schema_version=1, event_id=str(uuid5(NAMESPACE_URL, identity)),
                          case_id=case_id, document_id=document_id, sequence=0,
                          type=kind.__name__, occurred_at=occurred_at, run_id=run_id)
            if attempt_no is not None:
                fields["attempt_no"] = attempt_no
            self._store.put(kind(**fields))
        except Exception:
            pass

    def run_queued(self, *, case_id: str, document_id: str, run_id: str, occurred_at: str) -> None:
        self._execution_event(RunQueued, case_id, document_id, run_id, occurred_at)

    def attempt_started(self, *, case_id: str, document_id: str, run_id: str,
                        attempt_no: int, occurred_at: str) -> None:
        self._execution_event(AttemptStarted, case_id, document_id, run_id, occurred_at, attempt_no)


def from_env() -> AuditListener:
    try:
        store = AuditStore.from_env()
        return FileReceivedAudit(store) if store.enabled else NoOpAudit()
    except Exception:
        return NoOpAudit()
