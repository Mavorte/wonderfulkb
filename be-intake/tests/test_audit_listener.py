"""Audit-only identity and isolation checks without processing worker dependencies."""
import json
from unittest.mock import MagicMock
from uuid import NAMESPACE_URL, uuid5

import pytest

from document_processing.audit import audit_listener
from document_processing.audit.audit_events import EVENT_FIELDS, FileReceived
from document_processing.audit.audit_storage import AuditStore


def emit(listener, timestamp="2026-10-20T10:00:00Z"):
    return listener.file_received(case_id="case-test", document_id="doc-test", occurred_at=timestamp)


def test_identity_is_stable_and_envelope_is_content_free():
    store = MagicMock()
    listener = audit_listener.FileReceivedAudit(store)
    emit(listener)
    emit(listener, "2026-10-21T11:00:00Z")
    first, second = [call.args[0] for call in store.put.call_args_list]
    identity = json.dumps(["wonderfulkb.audit.v1", "FileReceived", "case-test", "doc-test"],
                          ensure_ascii=True, separators=(",", ":"))
    assert first.event_id == second.event_id == str(uuid5(NAMESPACE_URL, identity))
    assert first.occurred_at != second.occurred_at
    assert first.to_item() == dict(schema_version=1, event_id=first.event_id, case_id="case-test",
                                   document_id="doc-test", sequence=0, type="FileReceived",
                                   occurred_at="2026-10-20T10:00:00Z")
    assert set(first.to_item()) == set(EVENT_FIELDS)


@pytest.mark.parametrize("stage", ["identity", "event", "validation", "serialization", "sink"])
def test_entire_boundary_is_fail_open_without_retry(monkeypatch, stage):
    table = MagicMock()
    listener = audit_listener.FileReceivedAudit(AuditStore(table))
    failure = MagicMock(side_effect=RuntimeError("synthetic private error"))
    if stage == "identity":
        monkeypatch.setattr(audit_listener, "uuid5", failure)
    elif stage == "event":
        monkeypatch.setattr(audit_listener, "FileReceived", failure)
    elif stage == "serialization":
        monkeypatch.setattr(FileReceived, "to_item", failure)
    elif stage == "sink":
        table.put_item = failure
    assert emit(listener, "invalid" if stage == "validation" else "2026-10-20T10:00:00Z") is None
    assert table.put_item.call_count == (1 if stage == "sink" else 0)
    if stage != "validation":
        failure.assert_called_once()


def test_throwing_store_is_also_isolated():
    store = MagicMock()
    store.put.side_effect = RuntimeError("synthetic adapter failure")
    assert emit(audit_listener.FileReceivedAudit(store)) is None
    store.put.assert_called_once()


def test_factory_disabled_and_failure(monkeypatch):
    monkeypatch.delenv("AUDIT_TABLE_NAME", raising=False)
    assert isinstance(audit_listener.from_env(), audit_listener.NoOpAudit)
    monkeypatch.setattr(AuditStore, "from_env", MagicMock(side_effect=RuntimeError("init failure")))
    assert isinstance(audit_listener.from_env(), audit_listener.NoOpAudit)


def test_factory_reuses_bounded_store_config(monkeypatch):
    from document_processing.audit import audit_storage

    resource = MagicMock()
    create = MagicMock(return_value=resource)
    monkeypatch.setenv("AUDIT_TABLE_NAME", "synthetic-audit")
    monkeypatch.setattr(audit_storage.boto3, "resource", create)
    listener = audit_listener.from_env()
    assert isinstance(listener, audit_listener.FileReceivedAudit)
    config = create.call_args.kwargs["config"]
    assert (config.connect_timeout, config.read_timeout) == (1, 2)
    assert config.retries == {"total_max_attempts": 1}
    resource.Table.assert_called_once_with("synthetic-audit")
    emit(listener)
    resource.Table.return_value.put_item.assert_called_once()
