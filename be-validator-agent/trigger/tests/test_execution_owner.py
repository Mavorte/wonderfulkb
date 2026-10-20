"""Owner-issued identities are returned by the actual queue and claim entrypoints."""
from trigger import common
from trigger import processing_execution_claims as ledger
from trigger import worker_handler
from botocore.exceptions import ClientError
import pytest
from document_processing.audit.audit_listener import FileReceivedAudit, NoOpAudit
from document_processing.audit.audit_storage import AuditStore

from .conftest import CASE, add_document, bodies, drain


def test_enqueue_returns_owner_run_identity(ctx):
    result = common.enqueue_document(ctx, CASE, "d1")
    assert isinstance(result.run_id, str) and result.run_id


def test_claim_returns_committed_attempt(ctx):
    common.enqueue_document(ctx, CASE, "d1")
    result = common.claim_document(ctx, CASE, "d1")
    assert result.attempt_no == 1
    state = ctx.execution.get_item(Key={"pk": ledger.pk(CASE, "d1"), "sk": "STATE"})["Item"]
    assert state["attempt_no"] == 1 and state["claim_token"] == result.execution_context.claim_token


def test_duplicate_and_new_generation_keep_immutable_request_history(ctx):
    first = common.enqueue_document(ctx, CASE, "d1", request_key="one")
    again = common.enqueue_document(ctx, CASE, "d1", request_key="one")
    assert first.run_id == again.run_id and first.generation == again.generation == 1
    assert all(m["run_id"] == first.run_id for m in bodies(drain(ctx)))
    assert common.claim_document(ctx, CASE, "d1", first.run_id, 1).attempt_no == 1
    ctx.analysis.update_item(Key={"case_id": CASE, "document_id": "d1"},
                             UpdateExpression="SET processing_status = :s",
                             ExpressionAttributeValues={":s": "failed"})
    second = common.enqueue_document(ctx, CASE, "d1", request_key="two")
    assert second.run_id != first.run_id and second.generation == 2
    assert common.enqueue_document(ctx, CASE, "d1", request_key="one") == "stale"
    assert common.claim_document(ctx, CASE, "d1", first.run_id, 1) == "stale"
    assert common.claim_document(ctx, CASE, "d1", second.run_id, 2).attempt_no == 1


def test_ambiguous_send_retries_same_committed_run(ctx, monkeypatch):
    original = ctx.send
    def accepted_then_crash(body):
        original(body)
        raise TimeoutError("response lost after acceptance")
    monkeypatch.setattr(ctx, "send", accepted_then_crash)
    with pytest.raises(common.SendAmbiguous):
        common.enqueue_document(ctx, CASE, "d1", request_key="stable")
    monkeypatch.setattr(ctx, "send", original)
    retried = common.enqueue_document(ctx, CASE, "d1", request_key="stable")
    messages = bodies(drain(ctx))
    assert len(messages) == 2 and messages[0]["run_id"] == messages[1]["run_id"] == retried.run_id


def test_ambiguous_transaction_readback_does_not_increment_twice(ctx, monkeypatch):
    first = common.enqueue_document(ctx, CASE, "d1")
    original = ledger._transaction
    def committed_then_timeout(context, actions):
        original(context, actions)
        raise ClientError({"Error": {"Code": "InternalServerError", "Message": "lost response"}}, "TransactWriteItems")
    monkeypatch.setattr(ledger, "_transaction", committed_then_timeout)
    claimed = common.claim_document(ctx, CASE, "d1", first.run_id, first.generation)
    assert claimed.attempt_no == 1
    assert ctx.execution.get_item(Key={"pk": ledger.pk(CASE, "d1"), "sk": "STATE"})["Item"]["attempt_no"] == 1


def test_legacy_message_cannot_claim_a_new_generation(ctx):
    add_document(ctx, "d1")
    common.enqueue_document(ctx, CASE, "d1")
    assert worker_handler.process_document(ctx, {"case_id": CASE, "document_id": "d1"}) == "stale"
    assert ctx.get_row(CASE, "d1")["processing_status"] == "queued"


@pytest.mark.parametrize("listener", [NoOpAudit(), FileReceivedAudit(AuditStore(initialization_error=RuntimeError("offline")))])
def test_audit_outage_keeps_send_claim_and_business_fields(ctx, listener):
    ctx.audit = listener
    queued = common.enqueue_document(ctx, CASE, "d1")
    assert queued.send_status == "confirmed" and len(drain(ctx)) == 1
    row = ctx.get_row(CASE, "d1")
    assert row["processing_status"] == "queued" and "run_id" not in row
    claim = common.claim_document(ctx, CASE, "d1", queued.run_id, queued.generation)
    assert claim.attempt_no == 1 and ctx.get_row(CASE, "d1")["processing_status"] == "processing"


def test_audit_events_use_owner_identity_and_are_idempotent(ctx):
    ctx.ddb.create_table(TableName="test-audit", BillingMode="PAY_PER_REQUEST",
                         AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"},
                                               {"AttributeName": "sk", "AttributeType": "S"}],
                         KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"},
                                    {"AttributeName": "sk", "KeyType": "RANGE"}])
    ctx.audit = FileReceivedAudit(AuditStore(ctx.ddb.Table("test-audit")))
    queued = common.enqueue_document(ctx, CASE, "d1")
    common.enqueue_document(ctx, CASE, "d1")  # confirmed duplicate send, same audit event
    claimed = common.claim_document(ctx, CASE, "d1", queued.run_id, queued.generation)
    assert claimed.attempt_no == 1
    events = ctx.ddb.Table("test-audit").scan()["Items"]
    assert sorted(event["type"] for event in events) == ["AttemptStarted", "RunQueued"]
    assert all(event["run_id"] == queued.run_id for event in events)


def test_valid_lease_and_expired_lease_assign_only_committed_ordinals(ctx):
    queued = common.enqueue_document(ctx, CASE, "d1")
    first = common.claim_document(ctx, CASE, "d1", queued.run_id, queued.generation)
    assert common.claim_document(ctx, CASE, "d1", queued.run_id, queued.generation) == "processing"
    ctx.analysis.update_item(Key={"case_id": CASE, "document_id": "d1"},
                             UpdateExpression="SET updated_at = :old",
                             ExpressionAttributeValues={":old": "2020-01-01T00:00:00Z"})
    second = common.claim_document(ctx, CASE, "d1", queued.run_id, queued.generation)
    assert first.attempt_no == 1 and second.attempt_no == 2
    assert first.execution_context != second.execution_context
    assert ctx.execution.get_item(Key={"pk": ledger.pk(CASE, "d1"), "sk": "STATE"})["Item"]["attempt_no"] == 2


def test_cas_loser_cannot_allocate_a_second_claim(ctx, monkeypatch):
    queued = common.enqueue_document(ctx, CASE, "d1")
    original = ledger._transaction
    called = []
    def racing(context, actions):
        if not called:
            called.append(None)
            called[0] = common.claim_document(ctx, CASE, "d1", queued.run_id, queued.generation)
        return original(context, actions)
    monkeypatch.setattr(ledger, "_transaction", racing)
    loser = common.claim_document(ctx, CASE, "d1", queued.run_id, queued.generation)
    assert called[0].attempt_no == 1 and loser == "processing"
    assert ctx.execution.get_item(Key={"pk": ledger.pk(CASE, "d1"), "sk": "STATE"})["Item"]["attempt_no"] == 1
