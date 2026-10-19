"""Dead-letter queue -> row marked `failed` with a reason, metric `DeadLettered`.

A document message lands in the DLQ after the worker failed on it `maxReceiveCount` times (an exception or a
Lambda timeout). The worker never marks the row on the way, because a killed worker cannot; this function does
it for every cause. Messages that are not ours (a malformed body, a discarded stream batch) are only logged
and counted. The message is deleted afterwards: re-queue by running backfill.py, which picks up `failed`."""
import logging

from botocore.exceptions import ClientError

from . import common

logging.getLogger().setLevel(logging.INFO)
log = logging.getLogger("trigger.dlq")
_ctx = None


def context():
    global _ctx
    if _ctx is None:
        _ctx = common.Context()
    return _ctx


def mark_failed(ctx, case_id, document_id, reason):
    """True when the row was changed. A completed row (a later duplicate finished it) is left alone."""
    try:
        ctx.analysis.update_item(
            Key={"case_id": case_id, "document_id": document_id},
            UpdateExpression="SET processing_status = :f, updated_at = :t, "
                             "failure_reason = if_not_exists(failure_reason, :r)",
            ConditionExpression="attribute_exists(case_id) AND processing_status <> :c",
            ExpressionAttributeValues={":f": "failed", ":c": "completed", ":r": reason,
                                       ":t": common.iso(common.now_dt())})
        return True
    except ClientError as error:
        if not common._conditional_failed(error):
            raise
        return False


def handler(event, _context=None):
    ctx, failures = context(), []
    for record in event.get("Records", []):
        try:
            try:
                message = common.parse_message(record["body"])
            except common.BadMessage as error:
                log.error("dead letter that is not ours (%s): %.500s", error, record.get("body"))
                common.emit_metric("DeadLettered")
                continue
            common.emit_metric("DeadLettered")
            if message["type"] != "document":
                log.error("case step for %s gave up after retries", message["case_id"])
                continue
            changed = mark_failed(ctx, message["case_id"], message["document_id"],
                                  "PROCESSING_GAVE_UP: the worker failed or timed out on every attempt, see its logs")
            log.error("%s/%s dead-lettered, row %s", message["case_id"], message["document_id"],
                      "marked failed" if changed else "left as it was")
            if changed and common.case_ready(ctx, message["case_id"]):
                common.queue_case(ctx, message["case_id"])
        except Exception:  # noqa: BLE001
            log.exception("dead letter %s could not be handled", record.get("messageId"))
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}
