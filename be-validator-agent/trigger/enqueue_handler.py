"""DynamoDB Stream of wonderfulkb-uw-documents (INSERT only) -> `queued` row + SQS message.

The ingest writes a document row in one transaction after the PDF is in S3, so an INSERT means "a new document
whose original exists". A duplicate upload writes nothing and therefore starts nothing. The event source
mapping already filters on INSERT; the check here keeps the function correct without the filter."""
import logging

from boto3.dynamodb.types import TypeDeserializer

from . import common

logging.getLogger().setLevel(logging.INFO)
log = logging.getLogger("trigger.enqueue")
_ctx = None
_deserialize = TypeDeserializer().deserialize


def context():
    global _ctx
    if _ctx is None:
        _ctx = common.Context()
    return _ctx


def handler(event, _context=None):
    """Partial batch response: only the failed records are retried."""
    ctx, failures = context(), []
    for record in event.get("Records", []):
        sequence = record.get("dynamodb", {}).get("SequenceNumber")
        try:
            if record.get("eventName") != "INSERT":
                continue
            image = {k: _deserialize(v) for k, v in (record["dynamodb"].get("NewImage") or {}).items()}
            case_id, document_id = image.get("case_id"), image.get("document_id")
            if not (common._valid_id(case_id) and common._valid_id(document_id)):
                log.error("stream record %s has no usable keys, dropped", sequence)
                common.emit_metric("BadStreamRecord")
                continue
            outcome = common.enqueue_document(ctx, case_id, document_id, image.get("filename"))
            log.info("%s/%s: %s", case_id, document_id, outcome)
        except Exception:  # noqa: BLE001 - retried by the event source mapping, then discarded to the DLQ
            log.exception("stream record %s failed", sequence)
            failures.append({"itemIdentifier": sequence})
    return {"batchItemFailures": failures}
