"""Shared by the enqueue Lambda, the worker, the DLQ marker and backfill.py: queue messages and row states.

The analysis row is the only state. A document moves queued -> processing -> completed / partial / failed.
Every step here is a conditional write, so the same message or stream record can arrive twice (SQS and
DynamoDB Streams are at-least-once) and nothing is processed or marked twice.
"""
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

log = logging.getLogger("trigger")

MESSAGE_VERSION = 1
ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")  # the ingest's case_id rule; document ids (uuid5) fit as well
TERMINAL = ("completed", "partial", "failed")
# A worker that died keeps the row in `processing`. The Lambda limit is 900 s, so a claim older than this is dead.
# Shorter than the queue's visibility timeout (1200 s) by more than a cold start, so the retry of a killed worker
# always finds the claim expired.
LEASE_SECONDS = 930
NAMESPACE = "wonderfulkb/Trigger"


class BadMessage(ValueError):
    """A queue message that no retry can fix."""


def now_dt():
    return datetime.now(timezone.utc)


def iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")  # the format of the pipeline; compares lexicographically


def make_message(kind, case_id, document_id=None, force=False):
    body = {"v": MESSAGE_VERSION, "type": kind, "case_id": case_id}
    if kind == "document":
        body["document_id"] = document_id
        if force:
            body["force"] = True
    return json.dumps(body, separators=(",", ":"))


def _valid_id(value):
    return isinstance(value, str) and bool(ID_RE.fullmatch(value)) and set(value) != {"."}


def parse_message(body):
    """Returns {"type", "case_id", "document_id"?, "force"}. Raises BadMessage for anything else."""
    try:
        data = json.loads(body)
    except (TypeError, ValueError) as error:
        raise BadMessage(f"not JSON: {error}") from None
    if not isinstance(data, dict) or data.get("v") != MESSAGE_VERSION:
        raise BadMessage("unknown message version")
    kind = data.get("type")
    if kind not in ("document", "case"):
        raise BadMessage(f"unknown type {kind!r}")
    if not _valid_id(data.get("case_id")):
        raise BadMessage("invalid case_id")
    out = {"type": kind, "case_id": data["case_id"], "force": data.get("force") is True}
    if kind == "document":
        if not _valid_id(data.get("document_id")):
            raise BadMessage("invalid document_id")
        out["document_id"] = data["document_id"]
    return out


def emit_metric(name, value=1):
    """CloudWatch embedded metric format: a log line becomes a metric, no PutMetricData permission needed."""
    print(json.dumps({"_aws": {"Timestamp": int(time.time() * 1000),
                               "CloudWatchMetrics": [{"Namespace": NAMESPACE, "Dimensions": [[]],
                                                      "Metrics": [{"Name": name, "Unit": "Count"}]}]},
                      name: value}), flush=True)


class Context:
    """boto3 handles and names, created lazily from the environment (tests pass their own)."""

    def __init__(self, region=None, analysis_table=None, documents_table=None, bucket=None, queue_url=None,
                 dlq_url=None, ddb=None, sqs=None, s3=None):
        self.region = region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "eu-central-1"
        self.analysis_name = analysis_table or os.environ.get("ANALYSIS_TABLE", "wonderfulkb-uw-document-analysis")
        self.documents_name = documents_table or os.environ.get("DOCUMENTS_TABLE", "wonderfulkb-uw-documents")
        self.bucket = bucket or os.environ.get("RAW_BUCKET", "wonderfulkb-raw-document-storage")
        self.queue_url = queue_url or os.environ.get("QUEUE_URL", "")
        self.dlq_url = dlq_url or os.environ.get("DLQ_URL", "")
        self._ddb, self._sqs, self._s3 = ddb, sqs, s3

    @property
    def ddb(self):
        if self._ddb is None:
            self._ddb = boto3.resource("dynamodb", region_name=self.region)
        return self._ddb

    @property
    def sqs(self):
        if self._sqs is None:
            self._sqs = boto3.client("sqs", region_name=self.region)
        return self._sqs

    @property
    def s3(self):
        if self._s3 is None:
            self._s3 = boto3.client("s3", region_name=self.region)
        return self._s3

    @property
    def analysis(self):
        return self.ddb.Table(self.analysis_name)

    @property
    def documents(self):
        return self.ddb.Table(self.documents_name)

    def get_document(self, case_id, document_id):
        return self.documents.get_item(Key={"case_id": case_id, "document_id": document_id}).get("Item")

    def list_documents(self, case_id):
        items, kwargs = [], {"KeyConditionExpression": Key("case_id").eq(case_id)}
        while True:
            page = self.documents.query(**kwargs)
            items += page["Items"]
            if "LastEvaluatedKey" not in page:
                return sorted(items, key=lambda i: i["document_id"])
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def get_row(self, case_id, document_id):
        return self.analysis.get_item(Key={"case_id": case_id, "document_id": document_id},
                                      ConsistentRead=True).get("Item")

    def send(self, body):
        self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=body)


def _conditional_failed(error):
    return error.response["Error"]["Code"] == "ConditionalCheckFailedException"


def enqueue_document(ctx, case_id, document_id, title=None, force=False):
    """Make the document visible as `queued` and put it on the queue.

    Returns "queued", "completed" (nothing to do) or "processing" (a worker holds it). The row is written
    before the message: if the send fails the caller retries and finds the row `queued`, which still sends.
    Messages may therefore be duplicated, never lost; the worker's claim makes duplicates harmless."""
    key = {"case_id": case_id, "document_id": document_id}
    stamp = iso(now_dt())
    for _ in range(3):
        try:  # same attributes as pipeline._mark creates for a missing row
            ctx.analysis.put_item(
                Item={**key, "title": title or document_id, "page_count": 0, "processing_status": "queued",
                      "label_status": "predicted", "description": "", "pipeline_version": "pending",
                      "updated_at": stamp},
                ConditionExpression="attribute_not_exists(case_id)")
            break
        except ClientError as error:
            if not _conditional_failed(error):
                raise
        allowed = ["queued", "failed", "partial"] + (["completed"] if force else [])
        values = {":q": "queued", ":t": stamp, ":stale": iso(now_dt() - timedelta(seconds=LEASE_SECONDS)),
                  ":proc": "processing"}
        values.update({f":a{i}": s for i, s in enumerate(allowed)})
        names = ", ".join(f":a{i}" for i in range(len(allowed)))
        try:  # an existing row keeps its other attributes (label, text key) until the new run replaces them
            ctx.analysis.update_item(
                Key=key, UpdateExpression="SET processing_status = :q, updated_at = :t REMOVE failure_reason",
                ConditionExpression=f"attribute_exists(case_id) AND (processing_status IN ({names}) OR "
                                    f"(processing_status = :proc AND updated_at < :stale))",
                ExpressionAttributeValues=values)
            break
        except ClientError as error:
            if not _conditional_failed(error):
                raise
        row = ctx.get_row(case_id, document_id)
        if row is None:  # deleted between the two writes: try the create again
            continue
        return "completed" if row.get("processing_status") == "completed" else "processing"
    else:
        raise RuntimeError(f"cannot queue {case_id}/{document_id}: row keeps changing")
    ctx.send(make_message("document", case_id, document_id, force))
    return "queued"


def claim_document(ctx, case_id, document_id):
    """Move the row from `queued` to `processing` for this worker. Returns "claimed" or the status that stopped it.

    Only `queued` is claimable (plus a dead `processing` claim older than the lease): a `completed`, `partial` or
    `failed` row means the document was already handled, so a late duplicate message does nothing. Anything that
    wants a document processed again (the stream, backfill.py, also with --force) first sets the row to `queued`
    in enqueue_document. A missing row is created first, so a worker never writes a sparse item."""
    key = {"case_id": case_id, "document_id": document_id}
    if ctx.get_row(case_id, document_id) is None:
        doc = ctx.get_document(case_id, document_id) or {}
        try:
            ctx.analysis.put_item(
                Item={**key, "title": doc.get("filename") or document_id, "page_count": 0,
                      "processing_status": "queued", "label_status": "predicted", "description": "",
                      "pipeline_version": "pending", "updated_at": iso(now_dt())},
                ConditionExpression="attribute_not_exists(case_id)")
        except ClientError as error:
            if not _conditional_failed(error):
                raise
    try:
        ctx.analysis.update_item(
            Key=key, UpdateExpression="SET processing_status = :proc, updated_at = :t",
            ConditionExpression="attribute_exists(case_id) AND (processing_status = :q OR "
                                "(processing_status = :proc AND updated_at < :stale))",
            ExpressionAttributeValues={":proc": "processing", ":q": "queued", ":t": iso(now_dt()),
                                       ":stale": iso(now_dt() - timedelta(seconds=LEASE_SECONDS))})
        return "claimed"
    except ClientError as error:
        if not _conditional_failed(error):
            raise
    row = ctx.get_row(case_id, document_id)
    return row.get("processing_status", "unknown") if row else "unknown"


def case_ready(ctx, case_id):
    """True when every document of the case has a row in a final state (completed, partial or failed)."""
    documents = ctx.list_documents(case_id)
    if not documents:
        return False
    found = {}
    for start in range(0, len(documents), 100):
        keys = [{"case_id": case_id, "document_id": d["document_id"]} for d in documents[start:start + 100]]
        request = {ctx.analysis_name: {"Keys": keys, "ConsistentRead": True,
                                       "ProjectionExpression": "document_id, processing_status"}}
        while request:  # the resource takes and returns plain Python values
            response = ctx.ddb.batch_get_item(RequestItems=request)
            for item in response["Responses"].get(ctx.analysis_name, []):
                found[item["document_id"]] = item["processing_status"]
            request = response.get("UnprocessedKeys") or None
            if request:
                time.sleep(0.2)
    return all(found.get(d["document_id"]) in TERMINAL for d in documents)


def queue_case(ctx, case_id):
    ctx.send(make_message("case", case_id))
