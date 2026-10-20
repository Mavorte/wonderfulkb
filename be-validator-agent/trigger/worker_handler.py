"""SQS -> pipeline.run_document (or the case step).

Batch size 1, concurrency capped by the event source mapping (the team shares 50 Bedrock requests a minute).
A document message: claim the row (idempotence), run the pipeline, and when this was the last document of the
case, queue a `case` message. Exceptions go back to the queue (partial batch response); after
maxReceiveCount the message lands in the DLQ and dlq_handler marks the row `failed`."""
import json
import logging
import resource
import sys
import time
from document_processing.audit.audit_listener import ExecutionAudit

from . import case_step, common

logging.getLogger().setLevel(logging.INFO)
log = logging.getLogger("trigger.worker")
_ctx = None
_options = None
run_document = None  # resolved lazily: importing the pipeline loads PDF and image libraries


def context():
    global _ctx
    if _ctx is None:
        _ctx = common.Context()
    return _ctx


def _pipeline_run():
    global run_document
    if run_document is None:
        from pipeline import run_document as function
        run_document = function
    return run_document


def options():
    """One Options per warm container: keeps the Bedrock rate limiter state and the boto3 clients."""
    global _options
    if _options is None:
        from pipeline import Options
        # defer_copy_check: the comparison across the case runs once per case (a `case` message), not after every document
        _options = Options(defer_copy_check=True)
    return _options


def dead_letter(ctx, body, reason):
    """A message nobody can ever process goes straight to the DLQ (and is counted), not through three retries."""
    common.emit_metric("MalformedMessage")
    if not ctx.dlq_url:
        raise RuntimeError(f"malformed message and no DLQ configured: {reason}")
    ctx.sqs.send_message(QueueUrl=ctx.dlq_url, MessageBody=body if isinstance(body, str) else json.dumps(body),
                         MessageAttributes={"reason": {"DataType": "String", "StringValue": reason[:200]}})


def process_document(ctx, message, execution_context=None):
    case_id, document_id = message["case_id"], message["document_id"]
    if ctx.get_document(case_id, document_id) is None:
        log.error("%s/%s is not in %s, message dropped", case_id, document_id, ctx.documents_name)
        common.emit_metric("UnknownDocument")
        return "unknown"
    if execution_context is not None:
        message = {**message, "run_id": execution_context.run_id,
                   "generation": execution_context.generation}
    if "run_id" not in message:
        # A legacy delivery can only claim an explicitly bootstrapped legacy generation;
        # it must never claim a newer owner-issued generation.
        from .processing_execution_claims import legacy_binding
        binding = legacy_binding(ctx, case_id, document_id)
        if binding is None:
            return "stale"
        message = {**message, **binding}
    outcome = common.claim_document(ctx, case_id, document_id, message["run_id"], message["generation"])
    if outcome != "claimed":
        log.info("%s/%s: %s, nothing to do", case_id, document_id, outcome)
        return outcome
    audit = ExecutionAudit(outcome.execution_context, lambda: ctx.audit_listener)
    started = time.monotonic()
    try:
        row = _pipeline_run()(case_id, document_id, options=options(),
                               execution_context=outcome.execution_context,
                               audit_listener_factory=lambda: ctx.audit_listener)
    except Exception as error:
        _remember(ctx, case_id, document_id, f"{type(error).__name__}: {error}")
        audit.emit("AttemptFinished", attempt_status="failed", error_code="PROCESSING_FAILED",
                   duration_ms=(time.monotonic() - started) * 1000)
        raise
    status = row.get("processing_status")
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024)
    log.info("%s/%s: %s (max rss %d MB)", case_id, document_id, status, rss_mb)
    try:
        if status in common.TERMINAL and common.case_ready(ctx, case_id):
            common.queue_case(ctx, case_id)
    except Exception:
        audit.emit("AttemptFinished", attempt_status="failed", error_code="PROCESSING_FAILED",
                   duration_ms=(time.monotonic() - started) * 1000)
        raise
    if status in common.TERMINAL:
        audit.emit("AttemptFinished", attempt_status=status, duration_ms=(time.monotonic() - started) * 1000)
    return status


def _remember(ctx, case_id, document_id, reason):
    """The claim is released (`queued`) so the retry can take it, and the last error stays on the row for
    whoever looks at it before the DLQ marker runs. Best effort: a failure here must not hide the original one."""
    try:
        ctx.analysis.update_item(Key={"case_id": case_id, "document_id": document_id},
                                 UpdateExpression="SET failure_reason = :r, processing_status = :q, updated_at = :t",
                                 ConditionExpression="attribute_exists(case_id) AND processing_status = :p",
                                 ExpressionAttributeValues={":r": reason[:500], ":q": "queued", ":p": "processing",
                                                            ":t": common.iso(common.now_dt())})
    except Exception:  # noqa: BLE001
        log.warning("could not record the failure on the row", exc_info=True)


def handle_record(ctx, record):
    try:
        message = common.parse_message(record["body"])
    except common.BadMessage as error:
        log.error("malformed message %s: %s", record.get("messageId"), error)
        dead_letter(ctx, record.get("body"), f"MALFORMED: {error}")
        return "malformed"
    if message["type"] == "case":
        return case_step.run(message["case_id"], options(), ctx)
    return process_document(ctx, message)


def handler(event, _context=None):
    ctx, failures = context(), []
    for record in event.get("Records", []):
        try:
            handle_record(ctx, record)
        except Exception:  # noqa: BLE001
            log.exception("message %s failed (receive count %s)", record.get("messageId"),
                          record.get("attributes", {}).get("ApproximateReceiveCount"))
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}
