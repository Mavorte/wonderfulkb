import json

from trigger import common, enqueue_handler

from .conftest import CASE, bodies, drain, stream_record


def run(ctx, *records):
    enqueue_handler._ctx = ctx
    return enqueue_handler.handler({"Records": list(records)})


def test_insert_creates_queued_row_and_one_message(ctx):
    result = run(ctx, stream_record(CASE, "d1", filename="Smlouva.pdf"))
    assert result == {"batchItemFailures": []}
    row = ctx.get_row(CASE, "d1")
    assert row["processing_status"] == "queued" and row["title"] == "Smlouva.pdf"
    assert {"label_status", "description", "page_count", "pipeline_version", "updated_at"} <= set(row)
    assert bodies(drain(ctx)) == [{"v": 1, "type": "document", "case_id": CASE, "document_id": "d1"}]


def test_only_inserts_start_work(ctx):
    run(ctx, stream_record(CASE, "d1", event="MODIFY"), stream_record(CASE, "d2", event="REMOVE"))
    assert ctx.get_row(CASE, "d1") is None and drain(ctx) == []


def test_completed_or_running_documents_are_not_queued_again(ctx):
    ctx.analysis.put_item(Item={"case_id": CASE, "document_id": "done", "processing_status": "completed",
                                "title": "x", "updated_at": "2026-10-19T10:00:00Z"})
    ctx.analysis.put_item(Item={"case_id": CASE, "document_id": "busy", "processing_status": "processing",
                                "title": "x", "updated_at": common.iso(common.now_dt())})
    run(ctx, stream_record(CASE, "done"), stream_record(CASE, "busy"))
    assert drain(ctx) == []
    assert ctx.get_row(CASE, "done")["processing_status"] == "completed"
    assert ctx.get_row(CASE, "busy")["processing_status"] == "processing"


def test_dead_claim_is_queued_again(ctx):
    ctx.analysis.put_item(Item={"case_id": CASE, "document_id": "dead", "processing_status": "processing",
                                "title": "x", "updated_at": "2026-10-19T10:00:00Z"})
    run(ctx, stream_record(CASE, "dead"))
    assert ctx.get_row(CASE, "dead")["processing_status"] == "queued" and len(drain(ctx)) == 1


def test_redelivered_record_still_sends_when_the_first_attempt_died_after_the_row(ctx):
    """Row written, send failed, stream retries: the `queued` row must not suppress the message."""
    ctx.analysis.put_item(Item={"case_id": CASE, "document_id": "d1", "processing_status": "queued",
                                "title": "x", "updated_at": common.iso(common.now_dt())})
    run(ctx, stream_record(CASE, "d1"))
    assert len(drain(ctx)) == 1


def test_existing_row_keeps_its_data_when_requeued(ctx):
    ctx.analysis.put_item(Item={"case_id": CASE, "document_id": "p", "processing_status": "partial", "title": "x",
                                "label": "smlouva", "text_s3_key": "k", "failure_reason": "old",
                                "updated_at": "2026-10-19T10:00:00Z"})
    run(ctx, stream_record(CASE, "p"))
    row = ctx.get_row(CASE, "p")
    assert row["processing_status"] == "queued" and row["label"] == "smlouva" and row["text_s3_key"] == "k"
    assert "failure_reason" not in row


def test_send_failure_is_reported_for_retry_and_other_records_go_on(ctx):
    broken = common.Context(queue_url=ctx.queue_url + "-missing", ddb=ctx.ddb, sqs=ctx.sqs, s3=ctx.s3)
    result = run(broken, stream_record(CASE, "d1", sequence="10"))
    assert result["batchItemFailures"] == [{"itemIdentifier": "10"}]
    result = run(ctx, stream_record(CASE, "d1", sequence="10"), stream_record(CASE, "d2", sequence="11"))
    assert result["batchItemFailures"] == [] and len(drain(ctx)) == 2  # the retry works, d1 had a queued row


def test_record_without_usable_keys_is_dropped_not_retried(ctx):
    bad = {"eventName": "INSERT", "dynamodb": {"SequenceNumber": "5", "NewImage": {"case_id": {"S": "../x"}}}}
    assert run(ctx, bad) == {"batchItemFailures": []} and drain(ctx) == []


def test_enqueue_is_conditional_on_missing_row(ctx):
    """Two concurrent first deliveries: the loser must not overwrite the row the winner (or a worker) changed."""
    common.enqueue_document(ctx, CASE, "d1", "a.pdf")
    ctx.analysis.update_item(Key={"case_id": CASE, "document_id": "d1"}, UpdateExpression="SET label = :l",
                             ExpressionAttributeValues={":l": "smlouva"})
    common.enqueue_document(ctx, CASE, "d1", "a.pdf")
    assert ctx.get_row(CASE, "d1")["label"] == "smlouva"
    assert json.loads(drain(ctx)[0]["Body"])["document_id"] == "d1"
