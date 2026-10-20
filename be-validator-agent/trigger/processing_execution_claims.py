"""DynamoDB execution-only generation and claim ledger; business writes share the transaction."""
import hashlib
import uuid
from datetime import timedelta

from botocore.exceptions import ClientError

from .processing_execution_context import ClaimResult, EnqueueResult, ExecutionContext

def av(item):
    # The resource's meta.client has a DynamoDB serialization hook; passing wire
    # AttributeValues here would double-serialize them into nested maps.
    return item


def pk(case_id, document_id):
    return f"CASE#{case_id}#DOC#{document_id}"


def request_sk(request_key):
    return "REQUEST#" + hashlib.sha256(request_key.encode("utf-8")).hexdigest()


def _transaction(ctx, actions):
    ctx.ddb.meta.client.transact_write_items(TransactItems=actions)


def _conflict(error):
    return isinstance(error, ClientError) and error.response["Error"]["Code"] in (
        "TransactionCanceledException", "ConditionalCheckFailedException") and (
        error.response["Error"]["Code"] != "TransactionCanceledException" or
        all(reason.get("Code") in ("None", "ConditionalCheckFailed")
            for reason in error.response.get("CancellationReasons", [])))


def _state(ctx, key):
    return ctx.execution.get_item(Key={"pk": key, "sk": "STATE"}, ConsistentRead=True).get("Item")


def _mapping(ctx, key, request_key):
    return ctx.execution.get_item(Key={"pk": key, "sk": request_sk(request_key)}, ConsistentRead=True).get("Item")


def legacy_binding(ctx, case_id, document_id):
    """Bind an already-queued pre-upgrade row once; never bind old messages to a newer generation."""
    key = pk(case_id, document_id)
    state = _state(ctx, key)
    if state:
        return {"run_id": state["run_id"], "generation": int(state["generation"])} if state.get("legacy") else None
    row = ctx.get_row(case_id, document_id)
    if not row or row.get("processing_status") not in ("queued", "processing"):
        return None
    item = {"pk": key, "sk": "STATE", "generation": 1, "run_id": str(uuid.uuid4()),
            "attempt_no": 0, "legacy": True}
    try:
        _transaction(ctx, [
            {"ConditionCheck": {"TableName": ctx.analysis_name,
                                "Key": av({"case_id": case_id, "document_id": document_id}),
                                "ConditionExpression": "processing_status IN (:q, :p) AND updated_at = :at",
                                "ExpressionAttributeValues": av({":q": "queued", ":p": "processing",
                                                                 ":at": row["updated_at"]})}},
            {"Put": {"TableName": ctx.execution_name, "Item": av(item),
                     "ConditionExpression": "attribute_not_exists(pk)"}}])
        return {"run_id": item["run_id"], "generation": 1}
    except ClientError as error:
        if not _conflict(error):
            raise
        state = _state(ctx, key)
        if state and state.get("legacy"):
            return {"run_id": state["run_id"], "generation": int(state["generation"])}
        return None


def allocate(ctx, case_id, document_id, title, force, request_key, stamp, stale):
    """Commit generation + original queued transition together; never reallocate a request key."""
    key = pk(case_id, document_id)
    business_key = {"case_id": case_id, "document_id": document_id}
    for _ in range(5):
        mapped, state = _mapping(ctx, key, request_key), _state(ctx, key)
        if mapped:
            if not state or state.get("generation") != mapped["generation"]:
                return EnqueueResult("stale", mapped["run_id"], int(mapped["generation"]))
            row = ctx.get_row(case_id, document_id)
            if row and row.get("processing_status") not in ("queued",):
                return EnqueueResult("completed" if row.get("processing_status") == "completed" else "processing",
                                     mapped["run_id"], int(mapped["generation"]))
            return EnqueueResult("queued", mapped["run_id"], int(mapped["generation"]))
        row = ctx.get_row(case_id, document_id)
        if state and row and row.get("processing_status") == "queued":
            request_item = {"pk": key, "sk": request_sk(request_key), "request_key": request_key,
                            "generation": state["generation"], "run_id": state["run_id"]}
            try:
                _transaction(ctx, [
                    {"ConditionCheck": {"TableName": ctx.analysis_name, "Key": av(business_key),
                        "ConditionExpression": "processing_status = :q",
                        "ExpressionAttributeValues": av({":q": "queued"})}},
                    {"ConditionCheck": {"TableName": ctx.execution_name,
                        "Key": av({"pk": key, "sk": "STATE"}),
                        "ConditionExpression": "generation = :gen AND run_id = :run",
                        "ExpressionAttributeValues": av({":gen": state["generation"], ":run": state["run_id"]})}},
                    {"Put": {"TableName": ctx.execution_name, "Item": av(request_item),
                             "ConditionExpression": "attribute_not_exists(pk)"}}])
                return EnqueueResult("queued", state["run_id"], int(state["generation"]))
            except ClientError as error:
                mapped = _mapping(ctx, key, request_key)
                if mapped:
                    return EnqueueResult("queued", mapped["run_id"], int(mapped["generation"]))
                if _conflict(error):
                    continue
                raise
        if row and row.get("processing_status") not in ("queued", "failed", "partial") and not (
            force and row.get("processing_status") == "completed") and not (
            row.get("processing_status") == "processing" and row.get("updated_at", "") < stale):
            return EnqueueResult("completed" if row.get("processing_status") == "completed" else "processing")
        generation = int(state["generation"]) + 1 if state else 1
        run_id = str(uuid.uuid4())  # opaque value committed by the owner, never derived from delivery metadata
        state_item = {"pk": key, "sk": "STATE", "generation": generation, "run_id": run_id,
                      "attempt_no": 0}
        request_item = {"pk": key, "sk": request_sk(request_key), "request_key": request_key,
                        "generation": generation, "run_id": run_id}
        if row:
            allowed = ["queued", "failed", "partial"] + (["completed"] if force else [])
            values = {":q": "queued", ":t": stamp, ":stale": stale, ":proc": "processing"}
            values.update({f":a{i}": status for i, status in enumerate(allowed)})
            names = ", ".join(f":a{i}" for i in range(len(allowed)))
            business = {"Update": {"TableName": ctx.analysis_name, "Key": av(business_key),
                "UpdateExpression": "SET processing_status = :q, updated_at = :t REMOVE failure_reason",
                "ConditionExpression": f"attribute_exists(case_id) AND (processing_status IN ({names}) OR "
                                       "(processing_status = :proc AND updated_at < :stale))",
                "ExpressionAttributeValues": av(values)}}
        else:
            business = {"Put": {"TableName": ctx.analysis_name,
                "Item": av({**business_key, "title": title or document_id, "page_count": 0,
                            "processing_status": "queued", "label_status": "predicted", "description": "",
                            "pipeline_version": "pending", "updated_at": stamp}),
                "ConditionExpression": "attribute_not_exists(case_id)"}}
        state_write = {"Put": {"TableName": ctx.execution_name, "Item": av(state_item),
                               "ConditionExpression": "attribute_not_exists(pk)"}} if not state else {
            "Put": {"TableName": ctx.execution_name, "Item": av(state_item),
                    "ConditionExpression": "generation = :generation AND run_id = :run",
                    "ExpressionAttributeValues": av({":generation": state["generation"], ":run": state["run_id"]})}}
        actions = [business, state_write, {"Put": {"TableName": ctx.execution_name, "Item": av(request_item),
                                            "ConditionExpression": "attribute_not_exists(pk)"}}]
        try:
            _transaction(ctx, actions)
            return EnqueueResult("queued", run_id, generation)
        except ClientError as error:
            if not _conflict(error):
                # A transport/unknown response can have committed. Read back before any new allocation.
                mapped = _mapping(ctx, key, request_key)
                if mapped:
                    return EnqueueResult("queued", mapped["run_id"], int(mapped["generation"]))
                raise
    raise RuntimeError(f"cannot allocate {case_id}/{document_id}: concurrent changes")


def claim(ctx, case_id, document_id, run_id=None, generation=None):
    from .common import LEASE_SECONDS, iso, now_dt
    key = pk(case_id, document_id)
    business_key = {"case_id": case_id, "document_id": document_id}
    token = str(uuid.uuid4())
    for _ in range(5):
        state = _state(ctx, key)
        if not state:
            raise RuntimeError("execution generation missing; recovery required")
        if run_id is not None and (state["run_id"] != run_id or int(state["generation"]) != generation):
            return ClaimResult("stale")
        row = ctx.get_row(case_id, document_id)
        stamp, stale = iso(now_dt()), iso(now_dt() - timedelta(seconds=LEASE_SECONDS))
        if not row or (row.get("processing_status") != "queued" and not (
            row.get("processing_status") == "processing" and row.get("updated_at", "") < stale)):
            return ClaimResult(row.get("processing_status", "unknown") if row else "unknown")
        ordinal = int(state["attempt_no"]) + 1
        actions = [{"Update": {"TableName": ctx.analysis_name, "Key": av(business_key),
            "UpdateExpression": "SET processing_status = :proc, updated_at = :t",
            "ConditionExpression": "attribute_exists(case_id) AND (processing_status = :q OR "
                                   "(processing_status = :proc AND updated_at < :stale))",
            "ExpressionAttributeValues": av({":proc": "processing", ":q": "queued", ":t": stamp,
                                             ":stale": stale})}},
            {"Update": {"TableName": ctx.execution_name, "Key": av({"pk": key, "sk": "STATE"}),
                "UpdateExpression": "SET attempt_no = :next, claim_token = :token, claim_at = :t",
                "ConditionExpression": "run_id = :run AND generation = :gen AND attempt_no = :old",
                "ExpressionAttributeValues": av({":next": ordinal, ":token": token, ":t": stamp,
                                                 ":run": state["run_id"], ":gen": state["generation"],
                                                 ":old": state["attempt_no"]})}}]
        try:
            _transaction(ctx, actions)
        except ClientError as error:
            current = _state(ctx, key)
            if current and current.get("claim_token") == token:
                ordinal = int(current["attempt_no"])
            elif _conflict(error):
                continue
            else:
                raise
        execution = ExecutionContext(case_id, document_id, state["run_id"], int(state["generation"]),
                                     ordinal, token)
        return ClaimResult("claimed", execution)
    raise RuntimeError(f"cannot claim {case_id}/{document_id}: concurrent changes")
