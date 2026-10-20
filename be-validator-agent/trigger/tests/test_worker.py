import json

import pytest

from trigger import common, worker_handler

from .conftest import CASE, add_document, bodies, drain, sqs_event


class FakePipeline:
    """Stands in for pipeline.run_document: records the calls and finishes the row like the pipeline does."""

    def __init__(self, ctx, status="completed", error=None):
        self.ctx, self.status, self.error, self.calls = ctx, status, error, []

    def __call__(self, case_id, document_id, options=None, execution_context=None, audit_listener_factory=None):
        assert execution_context.case_id == case_id and execution_context.document_id == document_id
        self.calls.append((case_id, document_id))
        if self.error:
            raise self.error
        self.ctx.analysis.put_item(Item={"case_id": case_id, "document_id": document_id, "title": "x",
                                         "processing_status": self.status, "page_count": 1,
                                         "updated_at": common.iso(common.now_dt())})
        return self.ctx.get_row(case_id, document_id)


@pytest.fixture
def worker(ctx, monkeypatch):
    monkeypatch.setattr(worker_handler, "_ctx", ctx)
    fake = FakePipeline(ctx)
    monkeypatch.setattr(worker_handler, "run_document", fake)
    from pipeline import Options
    monkeypatch.setattr(worker_handler, "options", lambda: Options())
    fake.handler = worker_handler.handler
    return fake


def doc_message(document_id, **extra):
    return {"v": 1, "type": "document", "case_id": CASE, "document_id": document_id, **extra}


def queued_message(ctx, document_id, **extra):
    state = ctx.execution.get_item(Key={"pk": f"CASE#{CASE}#DOC#{document_id}", "sk": "STATE"}).get("Item")
    if not state:
        return doc_message(document_id, **extra)
    return {"v": 2, "type": "document", "case_id": CASE, "document_id": document_id,
            "run_id": state["run_id"], "generation": int(state["generation"]), **extra}


def test_document_is_processed_once(ctx, worker):
    add_document(ctx, "d1")
    common.enqueue_document(ctx, CASE, "d1")
    result = worker.handler(sqs_event(queued_message(ctx, "d1")))
    assert result == {"batchItemFailures": []}
    assert worker.calls == [(CASE, "d1")]
    assert ctx.get_row(CASE, "d1")["processing_status"] == "completed"


def test_completed_document_is_skipped(ctx, worker):
    add_document(ctx, "d1")
    ctx.analysis.put_item(Item={"case_id": CASE, "document_id": "d1", "processing_status": "completed", "title": "x",
                                "updated_at": "2026-10-19T10:00:00Z"})
    assert worker.handler(sqs_event(doc_message("d1"))) == {"batchItemFailures": []}
    assert worker.calls == []
    assert ctx.get_row(CASE, "d1")["updated_at"] == "2026-10-19T10:00:00Z"


def test_repeated_message_does_nothing_twice(ctx, worker):
    add_document(ctx, "d1")
    common.enqueue_document(ctx, CASE, "d1")
    worker.handler(sqs_event(queued_message(ctx, "d1")))
    worker.handler(sqs_event(queued_message(ctx, "d1")))
    worker.handler(sqs_event(queued_message(ctx, "d1")))
    assert worker.calls == [(CASE, "d1")]


def test_force_goes_through_the_queued_row(ctx, worker):
    """--force: enqueue_document sets the completed row to `queued` first; only then a worker takes it."""
    add_document(ctx, "d1")
    ctx.analysis.put_item(Item={"case_id": CASE, "document_id": "d1", "processing_status": "completed", "title": "x",
                                "updated_at": "2026-10-19T10:00:00Z"})
    worker.handler(sqs_event(queued_message(ctx, "d1", force=True)))
    assert worker.calls == []  # a late "force" message alone does nothing
    common.enqueue_document(ctx, CASE, "d1", force=True)
    worker.handler(sqs_event(queued_message(ctx, "d1", force=True)))
    assert worker.calls == [(CASE, "d1")]
    worker.handler(sqs_event(queued_message(ctx, "d1", force=True)))  # and a duplicate of it does nothing again
    assert worker.calls == [(CASE, "d1")]


def test_a_live_claim_is_left_alone_and_a_dead_one_is_taken_over(ctx, worker):
    add_document(ctx, "d1")
    ctx.analysis.put_item(Item={"case_id": CASE, "document_id": "d1", "processing_status": "processing", "title": "x",
                                "updated_at": common.iso(common.now_dt())})
    worker.handler(sqs_event(queued_message(ctx, "d1")))
    assert worker.calls == []
    ctx.analysis.update_item(Key={"case_id": CASE, "document_id": "d1"}, UpdateExpression="SET updated_at = :t",
                             ExpressionAttributeValues={":t": "2026-10-19T10:00:00Z"})
    worker.handler(sqs_event(queued_message(ctx, "d1")))
    assert worker.calls == [(CASE, "d1")]


def test_finished_rows_are_not_processed_again_by_a_late_message(ctx, worker):
    for document_id, status in (("f", "failed"), ("p", "partial")):
        add_document(ctx, document_id)
        ctx.analysis.put_item(Item={"case_id": CASE, "document_id": document_id, "processing_status": status,
                                    "title": "x", "updated_at": "2026-10-19T10:00:00Z"})
        worker.handler(sqs_event(doc_message(document_id)))
    assert worker.calls == []
    common.enqueue_document(ctx, CASE, "f")  # backfill --statuses failed: the row goes to `queued` first
    worker.handler(sqs_event(queued_message(ctx, "f")))
    assert worker.calls == [(CASE, "f")]


def test_unknown_document_is_dropped_and_no_row_appears(ctx, worker):
    assert worker.handler(sqs_event(doc_message("ghost"))) == {"batchItemFailures": []}
    assert worker.calls == [] and ctx.get_row(CASE, "ghost") is None


def test_exception_goes_back_to_the_queue_and_releases_the_claim(ctx, worker):
    add_document(ctx, "d1")
    common.enqueue_document(ctx, CASE, "d1")
    worker.error = RuntimeError("Bedrock exploded")
    result = worker.handler(sqs_event(queued_message(ctx, "d1")))
    assert result == {"batchItemFailures": [{"itemIdentifier": "m0"}]}
    row = ctx.get_row(CASE, "d1")
    assert row["processing_status"] == "queued" and "Bedrock exploded" in row["failure_reason"]
    worker.error = None  # the retry takes the claim at once and finishes the document
    assert worker.handler(sqs_event(queued_message(ctx, "d1"), receive_count=2)) == {"batchItemFailures": []}
    assert ctx.get_row(CASE, "d1")["processing_status"] == "completed"
    assert "failure_reason" not in ctx.get_row(CASE, "d1")


@pytest.mark.parametrize("body", [
    "not json at all", "[]", "{}", json.dumps({"v": 2, "type": "document", "case_id": CASE, "document_id": "d"}),
    json.dumps({"v": 1, "type": "document", "case_id": CASE}),
    json.dumps({"v": 1, "type": "document", "case_id": "../etc", "document_id": "d"}),
    json.dumps({"v": 1, "type": "document", "case_id": CASE, "document_id": ".."}),
    json.dumps({"v": 1, "type": "launch", "case_id": CASE}),
    json.dumps({"v": 1, "type": "document", "case_id": 5, "document_id": "d"}),
    None,
])
def test_malformed_message_goes_straight_to_the_dlq(ctx, worker, body):
    result = worker.handler(sqs_event(body) if body is not None else {"Records": [{"messageId": "m0", "body": None}]})
    assert result == {"batchItemFailures": []}
    assert worker.calls == []
    dead = drain(ctx, ctx.dlq_url)
    assert len(dead) == 1 and dead[0]["MessageAttributes"]["reason"]["StringValue"].startswith("MALFORMED")


def test_last_document_of_the_case_queues_the_case_step(ctx, worker):
    for document_id in ("d1", "d2"):
        add_document(ctx, document_id)
        common.enqueue_document(ctx, CASE, document_id)
    drain(ctx)
    worker.handler(sqs_event(queued_message(ctx, "d1")))
    assert drain(ctx) == []  # d2 is still queued
    worker.handler(sqs_event(queued_message(ctx, "d2")))
    assert bodies(drain(ctx)) == [{"v": 1, "type": "case", "case_id": CASE}]


def test_failed_last_document_also_completes_the_case(ctx, worker):
    add_document(ctx, "d1")
    add_document(ctx, "d2")
    ctx.analysis.put_item(Item={"case_id": CASE, "document_id": "d1", "processing_status": "completed", "title": "x",
                                "updated_at": "2026-10-19T10:00:00Z"})
    common.enqueue_document(ctx, CASE, "d2")
    drain(ctx)
    worker.status = "failed"
    worker.handler(sqs_event(queued_message(ctx, "d2")))
    assert bodies(drain(ctx)) == [{"v": 1, "type": "case", "case_id": CASE}]


def test_case_message_runs_the_case_step_once_per_message(ctx, worker, monkeypatch):
    calls = []
    monkeypatch.setattr(worker_handler.case_step, "run", lambda case_id, options, ctx=None: calls.append(case_id) or {})
    worker.handler(sqs_event({"v": 1, "type": "case", "case_id": CASE}))
    assert calls == [CASE]


def test_case_step_failure_is_retried(ctx, worker, monkeypatch):
    def boom(case_id, options, ctx=None):
        raise RuntimeError("S3 down")
    monkeypatch.setattr(worker_handler.case_step, "run", boom)
    assert worker.handler(sqs_event({"v": 1, "type": "case", "case_id": CASE}))["batchItemFailures"] == [
        {"itemIdentifier": "m0"}]


def test_one_bad_record_does_not_block_the_others(ctx, worker):
    add_document(ctx, "d1")
    common.enqueue_document(ctx, CASE, "d1")
    result = worker.handler(sqs_event("garbage", queued_message(ctx, "d1")))
    assert result == {"batchItemFailures": []} and worker.calls == [(CASE, "d1")]
