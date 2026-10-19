from trigger import common, dlq_handler

from .conftest import CASE, add_document, bodies, drain, sqs_event


def run(ctx, *messages):
    dlq_handler._ctx = ctx
    return dlq_handler.handler(sqs_event(*messages))


def message(document_id, kind="document"):
    body = {"v": 1, "type": kind, "case_id": CASE}
    if kind == "document":
        body["document_id"] = document_id
    return body


def test_dead_lettered_document_is_marked_failed_with_a_reason(ctx):
    add_document(ctx, "d1")
    common.enqueue_document(ctx, CASE, "d1")
    drain(ctx)
    assert run(ctx, message("d1")) == {"batchItemFailures": []}
    row = ctx.get_row(CASE, "d1")
    assert row["processing_status"] == "failed" and row["failure_reason"].startswith("PROCESSING_GAVE_UP")


def test_the_workers_own_reason_is_kept(ctx):
    add_document(ctx, "d1")
    common.enqueue_document(ctx, CASE, "d1")
    ctx.analysis.update_item(Key={"case_id": CASE, "document_id": "d1"}, UpdateExpression="SET failure_reason = :r",
                             ExpressionAttributeValues={":r": "RuntimeError: boom"})
    run(ctx, message("d1"))
    assert ctx.get_row(CASE, "d1")["failure_reason"] == "RuntimeError: boom"


def test_a_document_completed_in_the_meantime_is_left_alone(ctx):
    add_document(ctx, "d1")
    ctx.analysis.put_item(Item={"case_id": CASE, "document_id": "d1", "processing_status": "completed", "title": "x",
                                "updated_at": "2026-10-19T10:00:00Z"})
    run(ctx, message("d1"))
    assert ctx.get_row(CASE, "d1")["processing_status"] == "completed"


def test_no_row_is_invented_for_an_unknown_document(ctx):
    run(ctx, message("ghost"))
    assert ctx.get_row(CASE, "ghost") is None


def test_messages_that_are_not_ours_are_counted_and_not_retried(ctx, capsys):
    result = run(ctx, "garbage", {"DDBStreamBatchInfo": {"shardId": "x"}}, message(None, "case"))
    assert result == {"batchItemFailures": []}
    assert capsys.readouterr().out.count('"DeadLettered"') >= 3  # metric line per message


def test_failing_the_last_open_document_queues_the_case_step(ctx):
    add_document(ctx, "d1")
    add_document(ctx, "d2")
    ctx.analysis.put_item(Item={"case_id": CASE, "document_id": "d1", "processing_status": "completed", "title": "x",
                                "updated_at": "2026-10-19T10:00:00Z"})
    common.enqueue_document(ctx, CASE, "d2")
    drain(ctx)
    run(ctx, message("d2"))
    assert bodies(drain(ctx)) == [{"v": 1, "type": "case", "case_id": CASE}]


def test_error_while_marking_is_retried(ctx):
    broken = common.Context(queue_url=ctx.queue_url, ddb=None, sqs=ctx.sqs, s3=ctx.s3, analysis_table="missing-table",
                            documents_table="missing-table-2", dlq_url=ctx.dlq_url)
    broken._ddb = ctx.ddb
    dlq_handler._ctx = broken
    result = dlq_handler.handler(sqs_event(message("d1")))
    assert result == {"batchItemFailures": [{"itemIdentifier": "m0"}]}
