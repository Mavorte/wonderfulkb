"""Shared queue and business-row operations; owner-only execution identity lives in the ledger."""
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from . import processing_execution_claims as execution
from .processing_execution_context import EnqueueResult

log = logging.getLogger("trigger")

MESSAGE_VERSION = 1
ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")  # the ingest's case_id rule; document ids (uuid5) fit as well
TERMINAL = ("completed", "partial", "failed")
# A worker that died keeps the row in `processing`. The Lambda limit is 900 s, so a claim older than this is dead.
# Shorter than the queue's visibility timeout (1200 s) by more than a cold start, so the retry of a killed worker
# always finds the claim expired.
LEASE_SECONDS = 930
NAMESPACE = "wonderfulkb/Trigger"
# Case statuses this side sets (architecture/case-statuses.md); Wonderful sets the others through the agent API.
INTAKE_FROM = ("open", "awaiting_clarification")  # a new document starts intake; later states are left alone
EVALUATE_FROM = ("open", "intake_in_progress")


class BadMessage(ValueError):
    """A queue message that no retry can fix."""


def now_dt():
    return datetime.now(timezone.utc)


def iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")  # the format of the pipeline; compares lexicographically


def make_message(kind, case_id, document_id=None, force=False, run_id=None, generation=None):
    body = {"v": MESSAGE_VERSION, "type": kind, "case_id": case_id}
    if kind == "document":
        if run_id is not None:
            body.update(v=2, run_id=run_id, generation=generation)
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
    if not isinstance(data, dict) or data.get("v") not in (1, 2):
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
        if data["v"] == 2:
            if not _valid_id(data.get("run_id")) or type(data.get("generation")) is not int or data["generation"] < 1:
                raise BadMessage("invalid execution identity")
            out.update(run_id=data["run_id"], generation=data["generation"])
    elif data["v"] != 1:
        raise BadMessage("unknown case message version")
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
                 dlq_url=None, ddb=None, sqs=None, s3=None, cases_table=None,
                 execution_table=None, audit=None):
        self.region = region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "eu-central-1"
        self.analysis_name = analysis_table or os.environ.get("ANALYSIS_TABLE", "wonderfulkb-uw-document-analysis")
        self.documents_name = documents_table or os.environ.get("DOCUMENTS_TABLE", "wonderfulkb-uw-documents")
        self.cases_name = cases_table or os.environ.get("CASES_TABLE", "wonderfulkb-uw-cases")
        self.bucket = bucket or os.environ.get("RAW_BUCKET", "wonderfulkb-raw-document-storage")
        self.queue_url = queue_url or os.environ.get("QUEUE_URL", "")
        self.dlq_url = dlq_url or os.environ.get("DLQ_URL", "")
        self.execution_name = execution_table or os.environ.get("EXECUTION_TABLE", "wonderfulkb-trigger-execution")
        self.audit = audit
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

    @property
    def cases(self):
        return self.ddb.Table(self.cases_name)

    def get_case(self, case_id):
        return self.cases.get_item(
            Key={"case_id": case_id}, ConsistentRead=True
        ).get("Item")

    @property
    def execution(self):
        return self.ddb.Table(self.execution_name)

    @property
    def audit_listener(self):
        if self.audit is None:
            from document_processing.audit.audit_listener import from_env
            self.audit = from_env()
        return self.audit

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
        response = self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=body)
        if not response.get("MessageId"):
            raise RuntimeError("ambiguous SQS send: no MessageId")
        return response["MessageId"]


def _conditional_failed(error):
    return error.response["Error"]["Code"] == "ConditionalCheckFailedException"


def enqueue_document(ctx, case_id, document_id, title=None, force=False, request_key=None):
    """Atomically queue the row and owner generation; send the same generation on ambiguous retry."""
    # Direct callers must retain the returned request key across ambiguous retries; stream and
    # backfill pass stable keys explicitly. A queued row always reuses its current generation.
    request_key = request_key or f"direct:{case_id}:{document_id}"
    result = execution.allocate(ctx, case_id, document_id, title, force, request_key,
                                iso(now_dt()), iso(now_dt() - timedelta(seconds=LEASE_SECONDS)))
    if result != "queued":
        return result
    try:
        ctx.send(make_message("document", case_id, document_id, force, result.run_id, result.generation))
    except ClientError as error:
        code = error.response["Error"]["Code"]
        if code in ("InvalidMessageContents", "InvalidParameterValue", "AWS.SimpleQueueService.NonExistentQueue"):
            raise SendRejected(code) from error
        raise SendAmbiguous(code) from error
    except Exception as error:
        raise SendAmbiguous("send outcome unknown") from error
    from document_processing.audit.audit_listener import dispatch
    dispatch(lambda: ctx.audit_listener, "run_queued", case_id=case_id, document_id=document_id, run_id=result.run_id,
                                  occurred_at=iso(now_dt()))
    return EnqueueResult("queued", result.run_id, result.generation, "confirmed")


def claim_document(ctx, case_id, document_id, run_id=None, generation=None):
    """Commit the business claim and its owner-issued attempt ordinal in one transaction."""
    result = execution.claim(ctx, case_id, document_id, run_id, generation)
    if result == "claimed":
        from document_processing.audit.audit_listener import dispatch
        dispatch(lambda: ctx.audit_listener, "attempt_started", case_id=case_id, document_id=document_id,
            run_id=result.execution_context.run_id, attempt_no=result.attempt_no,
            occurred_at=iso(now_dt()))
    return result


class SendRejected(RuntimeError):
    """Known non-acceptance by SQS."""


class SendAmbiguous(RuntimeError):
    """Acceptance cannot be determined; retry with the same request key."""


def set_case_status(ctx, case_id, status, from_statuses):
    """Move the case to `status` if it is in one of `from_statuses`. True when the row changed.

    A missing case or one in another status is left alone (a repeated message, or Wonderful already moved it on)."""
    values = {":s": status, ":t": iso(now_dt())}
    values.update({f":f{i}": s for i, s in enumerate(from_statuses)})
    try:
        ctx.cases.update_item(
            Key={"case_id": case_id}, UpdateExpression="SET #s = :s, status_updated_at = :t",
            ConditionExpression=f"attribute_exists(case_id) AND #s IN ({', '.join(f':f{i}' for i in range(len(from_statuses)))})",
            ExpressionAttributeNames={"#s": "status"}, ExpressionAttributeValues=values)
        log.info("case %s: status %s", case_id, status)
        return True
    except ClientError as error:
        if not _conditional_failed(error):
            raise
        return False


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
