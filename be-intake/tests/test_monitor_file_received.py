"""Exercise the actual intake HTTP caller with mocks only at provider boundaries."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock
import copy
import sys
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def intake(monkeypatch, request):
    configuration = getattr(request, "param", {})
    for key, value in {"API_KEY": "test-key", "RAW_BUCKET": "test-raw",
                       "CASES_TABLE": "test-cases", "DOCS_TABLE": "test-docs",
                       "HASHES_TABLE": "test-hashes", "AUDIT_TABLE_NAME": ""}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("MONITOR_AUTH_SECRET_ARN", "")
    monkeypatch.setenv("PROCESSING_MONITOR_AUTHORIZATION_SECRET_ARN", "")
    for key, value in configuration.items():
        monkeypatch.setenv(key, value)
    resource, cases, docs, s3 = (MagicMock() for _ in range(4))
    hashes = MagicMock()
    audit, secrets = MagicMock(), MagicMock()
    resource.monitor_audit = audit
    resource.monitor_secrets = secrets
    resource.Table.side_effect = lambda name: {"test-cases": cases, "test-docs": docs,
                                               "test-hashes": hashes, "test-audit": audit}[name]
    cases.get_item.return_value = {"Item": {"case_id": "case-test"}}
    docs.get_item.return_value = {}
    docs.name = "test-docs"
    monkeypatch.setattr(boto3, "resource", lambda *a, **kw: resource)
    monkeypatch.setattr(boto3, "client", lambda service, **kw: secrets if service == "secretsmanager" else s3)
    path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    monkeypatch.syspath_prepend(str(path.parent))
    hash_spec = importlib.util.spec_from_file_location("content_hashes", path.with_name("content_hashes.py"))
    hash_module = importlib.util.module_from_spec(hash_spec)
    hash_spec.loader.exec_module(hash_module)
    clock = MagicMock(wraps=datetime)
    clock.now.return_value = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
    monkeypatch.setattr(hash_module, "datetime", clock)
    monkeypatch.setitem(sys.modules, "content_hashes", hash_module)
    spec = importlib.util.spec_from_file_location("intake_under_test", path)
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)
    monkeypatch.setattr(main, "now_iso", lambda: "2026-10-20T10:00:00Z")
    calls, order = [], []
    s3.put_object.side_effect = lambda **kw: order.append("s3") or {}
    resource.meta.client.transact_write_items.side_effect = lambda **kw: order.append("commit")

    class Recorder:
        def file_received(self, **values):
            order.append("audit")
            calls.append(values)

    main.app.state.audit_listener = Recorder()
    return main, resource, docs, s3, calls, order


def post(main, contents=(b"%PDF-1.4\nsynthetic",)):
    with TestClient(main.app) as client:
        return client.post(
            "/v1/cases/case-test/documents", headers={"x-api-key": "test-key"},
            files=[("files", (f"{i}.pdf", content, "application/pdf"))
                   for i, content in enumerate(contents)],
        )


def test_new_upload_emits_once_after_commit(intake):
    main, resource, docs, s3, calls, order = intake
    response = post(main)
    assert response.status_code == 201
    row = resource.meta.client.transact_write_items.call_args.kwargs["TransactItems"][0]["Put"]["Item"]
    assert calls == [{"case_id": row["case_id"], "document_id": row["document_id"],
                      "occurred_at": row["received_at"]}]
    assert order == ["s3", "commit", "audit"]


@pytest.mark.parametrize("scenario", ["new", "duplicate", "loser", "mixed", "metadata_failure", "s3_failure"])
def test_business_parity_with_noop_working_and_failing_audit(intake, scenario):
    from document_processing.audit.audit_listener import FileReceivedAudit, NoOpAudit
    from document_processing.audit.audit_storage import AuditStore

    main, resource, docs, s3, calls, order = intake
    snapshots = []
    for mode in ("noop", "working", "failing"):
        persisted, winners, trace, events = {}, {}, [], []
        attempts = 0
        table = MagicMock()

        def audit_put(**kwargs):
            trace.append(("audit",))
            if mode == "failing":
                raise RuntimeError("synthetic sink failure")
            events.append(kwargs["Item"])

        table.put_item.side_effect = audit_put
        main.app.state.audit_listener = NoOpAudit() if mode == "noop" else FileReceivedAudit(AuditStore(table))

        def get_item(**kwargs):
            trace.append(("get", copy.deepcopy(kwargs)))
            row = persisted.get(kwargs["Key"]["document_id"])
            return {"Item": row} if row else {}

        def put_object(**kwargs):
            data = kwargs.pop("Body").read()
            trace.append(("s3", kwargs, data))
            if scenario == "s3_failure":
                raise ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")
            return {"VersionId": "synthetic-version"}

        def commit(**kwargs):
            nonlocal attempts
            attempts += 1
            trace.append(("commit", copy.deepcopy(kwargs)))
            rows = [entry["Put"]["Item"] for entry in kwargs["TransactItems"]]
            if scenario == "metadata_failure":
                raise ClientError({"Error": {"Code": "ProvisionedThroughputExceededException"}}, "TransactWriteItems")
            if scenario in ("loser", "mixed") and attempts == 1:
                winner = dict(rows[0], received_at="2026-10-19T09:00:00Z", filename="winner.pdf")
                persisted[winner["document_id"]] = winner
                winners[winner["document_id"]] = winner
                raise ClientError({"Error": {"Code": "TransactionCanceledException"},
                                   "CancellationReasons": [{"Code": "ConditionalCheckFailed"}]}, "TransactWriteItems")
            persisted.update({row["document_id"]: row for row in rows})

        docs.get_item.side_effect = get_item
        main.content_hashes.table().update_item.side_effect = lambda **kw: trace.append(("hash", kw)) or {}
        s3.put_object.side_effect = put_object
        s3.delete_object.side_effect = lambda **kw: trace.append(("delete", kw)) or {}
        resource.meta.client.transact_write_items.side_effect = commit
        contents = (b"%PDF-1.4\na", b"%PDF-1.4\nb") if scenario == "mixed" else (b"%PDF-1.4\na",)
        if scenario == "duplicate":
            contents = contents * 2
        if scenario.endswith("failure"):
            with pytest.raises(ClientError) as failure:
                post(main, contents)
            result = (type(failure.value).__name__, failure.value.response)
        else:
            response = post(main, contents)
            result = (response.status_code, response.json())
            assert response.status_code == 201
            if scenario == "duplicate":
                assert [d["duplicate"] for d in response.json()["documents"]] == [False, True]
                before = table.put_item.call_count
                repeated = post(main, contents)
                assert all(d["duplicate"] for d in repeated.json()["documents"])
                assert table.put_item.call_count == before
            if scenario in ("loser", "mixed"):
                assert response.json()["documents"][0]["filename"] == "winner.pdf"

        own_rows = {key: row for key, row in persisted.items() if key not in winners}
        expected_count = len(own_rows) if mode != "noop" else 0
        assert table.put_item.call_count == expected_count
        assert {e["document_id"] for e in events} == (set(own_rows) if mode == "working" else set())
        for event in events:
            row = own_rows[event["document_id"]]
            assert (event["case_id"], event["occurred_at"]) == (row["case_id"], row["received_at"])
        if expected_count:
            audit_index = next(i for i, entry in enumerate(trace) if entry[0] == "audit")
            assert audit_index > max(i for i, entry in enumerate(trace) if entry[0] == "commit")
        snapshots.append((result, persisted, [entry for entry in trace if entry[0] != "audit"]))
    assert snapshots[0] == snapshots[1] == snapshots[2]
