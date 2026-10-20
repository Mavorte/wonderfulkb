"""Actual execution owner -> worker -> audit persistence -> authorized intake HTTP."""
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from fastapi.testclient import TestClient
from document_processing.audit.audit_listener import FileReceivedAudit
from document_processing.audit.audit_storage import AuditStore
from pipeline import Options
from pipeline.aws import Aws
from pipeline.config import Settings
from trigger import common, worker_handler
from .conftest import add_document, drain, sqs_event, text_pdf

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "be-intake/tests"))
from test_monitor_file_received import intake  # noqa: E402,F401


def test_claim_listener_failure_does_not_change_committed_result(ctx):
    add_document(ctx, "doc-test", case_id="case-test")
    queued = common.enqueue_document(ctx, "case-test", "doc-test", request_key="fixture-claim")

    class BrokenListener:
        def attempt_started(self, **values):
            raise RuntimeError("synthetic audit unavailable")

    ctx.audit = BrokenListener()
    result = common.claim_document(ctx, "case-test", "doc-test", queued.run_id, queued.generation)
    assert result == "claimed"
    assert result.execution_context.run_id == queued.run_id
    assert result.attempt_no == 1


def test_actual_worker_publishes_terminal_visible_over_http(ctx, monkeypatch, request):
    table = ctx.ddb.create_table(
        TableName="test-worker-audit", BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": n, "AttributeType": "S"} for n in ("pk", "sk")],
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"},
                   {"AttributeName": "sk", "KeyType": "RANGE"}],
    )
    store = AuditStore(table)
    ctx.audit = FileReceivedAudit(store)
    add_document(ctx, "doc-test", case_id="case-test", pdf=text_pdf([
        "Synthetic public fixture for monitoring integration only with a readable text layer.",
        "No private document or paid inference is required for this local test.",
    ]))
    settings = Settings(skip=frozenset({"classify", "embed", "signatures", "copy"}), redact=False)
    monkeypatch.setattr(worker_handler, "_ctx", ctx)
    monkeypatch.setattr(worker_handler, "_options", Options(
        settings=settings, aws=Aws(settings), no_vision=True, reuse=False, defer_copy_check=True))
    queued = common.enqueue_document(ctx, "case-test", "doc-test", request_key="fixture-http")
    delivery = drain(ctx)[0]
    assert worker_handler.handler(sqs_event(delivery["Body"])) == {"batchItemFailures": []}
    assert ctx.get_row("case-test", "doc-test")["processing_status"] == "completed"

    main, _, docs, _, _, _ = request.getfixturevalue("intake")
    from processing_monitor_authorization import AuthorizationSecretSource
    token = "synthetic-worker-http-only"
    policy = {
        "version": 1,
        "credentials": [{"sha256": hashlib.sha256(token.encode()).hexdigest(), "principal_id": "fixture"}],
        "principals": [{"id": "fixture", "type": "SERVICE", "enabled": True, "case_ids": ["case-test"]}],
        "retained_documents": [],
    }
    arn = "arn:aws:secretsmanager:eu-central-1:000000000000:secret:local-worker-http"
    secrets = MagicMock()
    secrets.get_secret_value.return_value = {"SecretString": json.dumps(policy)}
    main.app.state.processing_monitor_authorization_source = AuthorizationSecretSource(arn, secrets)
    docs.get_item.side_effect = lambda **kw: ctx.documents.get_item(**kw)
    main.app.state.processing_monitor_audit_store = store
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/cases/case-test/processing/documents/doc-test/events?limit=100",
            headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    secrets.get_secret_value.assert_called_once_with(SecretId=arn, VersionStage="AWSCURRENT")
    assert response.headers["cache-control"] == "private, no-store"
    observations = response.json()["items"]
    terminal = [event for event in observations if event["type"] == "RunFinished"]
    assert len(terminal) == 1
    assert terminal[0]["run_id"] == queued.run_id
    assert terminal[0]["attempt_no"] == 1
    assert terminal[0]["run_status"] == "completed"
    assert {event["run_id"] for event in observations} == {queued.run_id}
    assert {event["attempt_no"] for event in observations if "attempt_no" in event} == {1}
    assert {event["type"] for event in observations} >= {
        "RunQueued", "AttemptStarted", "StepStarted", "StepFinished", "PageCompleted",
        "ResultPublished", "RunFinished", "AttemptFinished"}
    assert not any(event.get("stage") == "signature_detection" for event in observations)
    from processing_monitor_authorization import ServiceDocumentAuthorizer
    main.app.state.lifecycle_authorize_read = ServiceDocumentAuthorizer(secrets, arn, docs)
    main.app.state.lifecycle_audit_table = table
    base = "/v1/cases/case-test/processing/documents/doc-test"
    with TestClient(main.app) as client:
        for suffix in (f"/runs/{queued.run_id}/steps?attempt_no=1", f"/runs/{queued.run_id}/pages?attempt_no=1",
                       "/runs", f"/runs/{queued.run_id}", "/audit"):
            response = client.get(base + suffix, headers={"Authorization": f"Bearer {token}", "x-api-key": main.API_KEY})
            assert response.status_code == 200, (suffix, response.text)
            assert response.headers["cache-control"] == "private, no-store"
        for path in (base + "/events", base + f"/runs/{queued.run_id}/pages?attempt_no=1"):
            response = client.get(path, headers={"Authorization": "Bearer forged"})
            assert response.status_code in {403, 404}
            assert response.headers["cache-control"] == "private, no-store"
        response = client.get(base.replace("doc-test", "missing") + "/events",
                              headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 404


@pytest.fixture
def worker_path(ctx, monkeypatch):
    table = ctx.ddb.create_table(TableName="producer-audit", BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": n, "AttributeType": "S"} for n in ("pk", "sk")],
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}])
    store = AuditStore(table)
    ctx.audit = FileReceivedAudit(store)
    settings = Settings(skip=frozenset({"classify", "embed", "signatures", "copy", "regions"}), redact=False)
    opts = Options(settings=settings, aws=Aws(settings), no_vision=True, reuse=False, defer_copy_check=True)
    monkeypatch.setattr(worker_handler, "_ctx", ctx)
    monkeypatch.setattr(worker_handler, "_options", opts)
    # Resolve the real entrypoint, even when another unit test cached a FakePipeline.
    from pipeline import run_document
    monkeypatch.setattr(worker_handler, "run_document", run_document)
    return table, opts


def produced(table):
    # Local test inspection only; production HTTP continues to use a bounded Query.
    return table.scan()["Items"]


@pytest.mark.parametrize("listener", ["healthy", "noop", "sink_failure", "throwing", "factory_failure"])
def test_real_worker_listener_failures_preserve_business_result(ctx, worker_path, monkeypatch, listener):
    table, opts = worker_path
    if listener == "noop":
        from document_processing.audit.audit_listener import NoOpAudit
        ctx.audit = NoOpAudit()
    elif listener == "sink_failure":
        monkeypatch.setattr(ctx.audit._store, "put", MagicMock(side_effect=RuntimeError("sink unavailable")))
    elif listener == "throwing":
        class Throwing:
            def __getattr__(self, name):
                raise RuntimeError("listener lookup unavailable")
        ctx.audit = Throwing()
    elif listener == "factory_failure":
        monkeypatch.setattr(common.Context, "audit_listener", property(lambda self: (_ for _ in ()).throw(RuntimeError("factory"))))
    add_document(ctx, "doc-test", case_id="case-test", pdf=text_pdf(["Benign public readable fixture for audit parity."]))
    queued = common.enqueue_document(ctx, "case-test", "doc-test", request_key="parity")
    assert worker_handler.handler(sqs_event(drain(ctx)[0]["Body"])) == {"batchItemFailures": []}
    row = ctx.get_row("case-test", "doc-test")
    assert row["processing_status"] == "completed" and row["page_count"] == 1
    assert opts.aws.get_bytes(row["text_s3_key"]).decode().strip() == "Benign public readable fixture for audit parity."
    state = ctx.execution.get_item(Key={"pk": "CASE#case-test#DOC#doc-test", "sk": "STATE"})["Item"]
    assert state["run_id"] == queued.run_id
    assert len(drain(ctx)) == 1  # existing downstream case send unchanged
    if listener == "healthy":
        assert len([e for e in produced(table) if e["type"] == "RunFinished"]) == 1
    else:
        assert produced(table) == []


@pytest.mark.parametrize("failure", ["download", "invalid_pdf", "oversize", "extraction", "publication"])
def test_real_worker_failure_fragments(ctx, worker_path, monkeypatch, failure):
    table, opts = worker_path
    data = b"not a PDF" if failure == "invalid_pdf" else text_pdf(["Public text fixture for bounded failure test."])
    add_document(ctx, "doc-test", case_id="case-test", pdf=None if failure == "download" else data)
    if failure == "oversize":
        from dataclasses import replace
        opts.settings = replace(opts.settings, max_pdf_bytes=1)
    elif failure == "extraction":
        from pipeline import pdf
        monkeypatch.setattr(pdf, "extract_pages", MagicMock(side_effect=RuntimeError("local extraction failed")))
    elif failure == "publication":
        monkeypatch.setattr(opts.aws, "put_bytes", MagicMock(side_effect=RuntimeError("local write failed")))
    queued = common.enqueue_document(ctx, "case-test", "doc-test", request_key="failure")
    body = drain(ctx)[0]["Body"]
    response = worker_handler.handler(sqs_event(body))
    events = produced(table)
    assert {e["run_id"] for e in events} == {queued.run_id}
    assert not any(e["type"] == "RetryEnqueued" for e in events)
    if failure == "publication":
        assert response == {"batchItemFailures": [{"itemIdentifier": "m0"}]}
        assert not any(e["type"] in {"RunFinished", "ResultPublished"} for e in events)
        assert ctx.get_row("case-test", "doc-test")["processing_status"] == "queued"
        # Redelivery uses the existing execution owner, not receive count, to assign ordinal 2.
        monkeypatch.undo()
        monkeypatch.setattr(worker_handler, "_ctx", ctx)
        monkeypatch.setattr(worker_handler, "_options", opts)
        assert worker_handler.handler(sqs_event(body, receive_count=99)) == {"batchItemFailures": []}
        assert {int(e["attempt_no"]) for e in produced(table) if e["type"] == "AttemptStarted"} == {1, 2}
    else:
        assert response == {"batchItemFailures": []}
        assert len([e for e in events if e["type"] == "StepFailed"]) == 1
        assert [e["run_status"] for e in events if e["type"] == "RunFinished"] == ["failed"]


@pytest.mark.parametrize("mode", ["success", "failure", "disabled", "cache"])
def test_actual_transcription_and_cache_are_distinct_producers(ctx, worker_path, mode):
    table, opts = worker_path
    opts.force_vision = True
    opts.no_vision = mode == "disabled"
    opts.vision = MagicMock()
    opts.vision.transcribe.return_value = "Benign fake provider transcription"
    if mode == "failure":
        opts.vision.transcribe.side_effect = RuntimeError("synthetic provider unavailable")
    if mode == "cache":
        opts.aws.put_bytes(f"cases/case-test/analysis/doc-test/vision/{opts.settings.vision_model}/1.txt",
                           b"Previously stored benign page", "text/plain")
    add_document(ctx, "doc-test", case_id="case-test", pdf=text_pdf(["Benign fixture with explicit forced visual transcription."]))
    common.enqueue_document(ctx, "case-test", "doc-test", request_key="page")
    assert worker_handler.handler(sqs_event(drain(ctx)[0]["Body"])) == {"batchItemFailures": []}
    pages = [e for e in produced(table) if e.get("stage") == "page_transcription"]
    if mode == "cache":
        opts.vision.transcribe.assert_not_called()
        assert [e["type"] for e in pages] == ["PageCacheReused"]
        assert pages[0]["attempt_no"] == 1
    elif mode == "disabled":
        opts.vision.transcribe.assert_not_called()
        assert [e["type"] for e in pages] == ["PageFailed"]
    else:
        opts.vision.transcribe.assert_called_once()
        assert {e["type"] for e in pages} == {"StepStarted", "PageFailed" if mode == "failure" else "PageCompleted"}
        assert all(e.get("duration_ms", 0) >= 0 for e in pages)


@pytest.mark.parametrize("mode", ["success", "raised", "returned_failure", "kept", "disabled"])
def test_actual_signature_caller_only_observes_real_detection(ctx, worker_path, monkeypatch, mode):
    from dataclasses import replace
    from pipeline import adapters
    table, opts = worker_path
    if mode != "disabled":
        opts.settings = replace(opts.settings, skip=opts.settings.skip - {"signatures"})
    detector = MagicMock(return_value=[] if mode != "returned_failure" else None)
    if mode == "raised":
        detector.side_effect = RuntimeError("synthetic detector unavailable")
    monkeypatch.setattr(adapters, "detect_signatures", detector)
    if mode == "kept":
        opts.aws.put_bytes("cases/case-test/analysis/doc-test/signatures.json", b'{"signatures":[]}', "application/json")
    add_document(ctx, "doc-test", case_id="case-test", pdf=text_pdf(["Benign fixture for signature caller proof."]))
    common.enqueue_document(ctx, "case-test", "doc-test", request_key="signatures")
    assert worker_handler.handler(sqs_event(drain(ctx)[0]["Body"])) == {"batchItemFailures": []}
    events = [e for e in produced(table) if e.get("stage") == "signature_detection"]
    if mode in {"kept", "disabled"}:
        detector.assert_not_called()
        assert events == []
    else:
        detector.assert_called_once()
        assert {e["type"] for e in events} == {"StepStarted", "StepFinished" if mode == "success" else "StepFailed"}


@pytest.mark.parametrize("boundary", ["text", "page", "report", "analysis"])
def test_partial_publication_never_becomes_run_terminal(ctx, worker_path, monkeypatch, boundary):
    table, opts = worker_path
    original = opts.aws.put_bytes
    def put(key, *args, **kwargs):
        matches = {"text": key.endswith("text.txt"), "page": key.endswith("1.png"),
                   "report": key.endswith("run.json")}
        if matches.get(boundary):
            raise RuntimeError("synthetic owned write failed")
        return original(key, *args, **kwargs)
    monkeypatch.setattr(opts.aws, "put_bytes", put)
    if boundary == "analysis":
        monkeypatch.setattr(opts.aws.analysis, "put_item", MagicMock(side_effect=RuntimeError("synthetic final row failed")))
    add_document(ctx, "doc-test", case_id="case-test", pdf=text_pdf(["Benign partial publication fixture."]))
    common.enqueue_document(ctx, "case-test", "doc-test", request_key="partial")
    assert worker_handler.handler(sqs_event(drain(ctx)[0]["Body"])) == {"batchItemFailures": [{"itemIdentifier": "m0"}]}
    events = produced(table)
    assert not any(e["type"] in {"ResultPublished", "RunFinished", "RetryEnqueued"} for e in events)
    assert [e["attempt_status"] for e in events if e["type"] == "AttemptFinished"] == ["failed"]


@pytest.mark.parametrize("transport", ["duplicate", "lost", "late", "terminal_only"])
def test_loss_delay_duplicate_are_actual_producer_observations(ctx, worker_path, monkeypatch, transport):
    from document_processing.audit.audit_lifecycle_observations import reduce_observations
    table, opts = worker_path
    delayed = []
    original = ctx.audit._store.put
    def deliver(event):
        if transport == "duplicate":
            first = original(event)
            assert original(event) == "duplicate"
            return first
        if transport in {"lost", "late"} and event.type in {"RunFinished", "AttemptFinished"}:
            delayed.append(event)
            return "unavailable"
        if transport == "terminal_only" and event.type != "RunFinished":
            return "unavailable"
        return original(event)
    monkeypatch.setattr(ctx.audit._store, "put", deliver)
    add_document(ctx, "doc-test", case_id="case-test", pdf=text_pdf(["Public fixture for transport loss proof."]))
    common.enqueue_document(ctx, "case-test", "doc-test", request_key="transport")
    assert worker_handler.handler(sqs_event(drain(ctx)[0]["Body"])) == {"batchItemFailures": []}
    events = produced(table)
    assert len({e["event_id"] for e in events}) == len(events)
    summary = reduce_observations(events, next_token=None)
    assert summary.coverage != "complete"
    if transport in {"lost", "late"}:
        assert not any(e["type"] == "RunFinished" for e in events)
    if transport == "late":
        for event in reversed(delayed):
            assert original(event) == "inserted"
            assert original(event) == "duplicate"
        assert any(e["type"] == "RunFinished" for e in produced(table))
    if transport == "terminal_only":
        assert [e["type"] for e in events] == ["RunFinished"]
        assert summary.attempts == ()


@pytest.mark.parametrize("partial_copy", [False, True])
def test_actual_document_reuse_requires_all_owned_page_copies_for_audit_terminal(ctx, worker_path, monkeypatch, partial_copy):
    table, opts = worker_path
    ctx.ddb.create_table(TableName="wonderfulkb-uw-content-hashes", BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": n, "AttributeType": "S"} for n in ("sha256", "case_document")],
        KeySchema=[{"AttributeName": "sha256", "KeyType": "HASH"}, {"AttributeName": "case_document", "KeyType": "RANGE"}])
    data = text_pdf(["Public reusable document generated by the actual first worker execution."])
    add_document(ctx, "origin", case_id="origin-case", pdf=data)
    common.enqueue_document(ctx, "origin-case", "origin", request_key="origin")
    assert worker_handler.handler(sqs_event(drain(ctx)[0]["Body"])) == {"batchItemFailures": []}
    drain(ctx)
    opts.reuse = True
    opts.vision = MagicMock()
    if partial_copy:
        error = opts.aws.s3.exceptions.ClientError({"Error": {"Code": "SyntheticCopyFailure"}}, "CopyObject")
        monkeypatch.setattr(opts.aws.s3, "copy_object", MagicMock(side_effect=error))
    add_document(ctx, "doc-test", case_id="case-test", pdf=data)
    queued = common.enqueue_document(ctx, "case-test", "doc-test", request_key="reuse")
    assert worker_handler.handler(sqs_event(drain(ctx)[0]["Body"])) == {"batchItemFailures": []}
    row = ctx.get_row("case-test", "doc-test")
    assert row["processing_status"] == "completed"  # existing business best-effort page-copy behavior is unchanged
    assert row["reused_from"] == {"case_id": "origin-case", "document_id": "origin"}
    opts.vision.transcribe.assert_not_called()
    events = [e for e in produced(table) if e["run_id"] == queued.run_id]
    assert not any(e["type"] == "PageCacheReused" for e in events)
    assert len([e for e in events if e["type"] == "RunFinished"]) == (0 if partial_copy else 1)
    assert len([e for e in events if e["type"] == "ResultPublished"]) == (0 if partial_copy else 1)


def test_audit_injection_preserves_warm_provider_and_limiter_dependency(ctx, worker_path, monkeypatch):
    import importlib
    pipeline_run = importlib.import_module("pipeline.run")
    table, opts = worker_path
    opts.force_vision, opts.no_vision = True, False
    provider = MagicMock()
    provider.transcribe.return_value = "Benign fake external transcription"
    factory = MagicMock(return_value=provider)
    monkeypatch.setattr(pipeline_run, "MantleVision", factory)
    for document in ("first", "second"):
        add_document(ctx, document, case_id="case-test", pdf=text_pdf(["Warm provider dependency fixture."]))
        common.enqueue_document(ctx, "case-test", document, request_key=document)
        messages = [m for m in drain(ctx) if json.loads(m["Body"])["type"] == "document"]
        assert worker_handler.handler(sqs_event(messages[0]["Body"])) == {"batchItemFailures": []}
    factory.assert_called_once()
    assert opts.vision is provider
    assert provider.transcribe.call_count == 2
    assert not hasattr(opts, "execution_context")
