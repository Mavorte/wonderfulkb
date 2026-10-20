import boto3
from decimal import Decimal
import pytest
from moto import mock_aws

from document_processing.audit.audit_events import PageCacheReused
from document_processing.audit.audit_storage import AuditStore
from document_processing.audit.audit_queries import _event_from_item
from document_processing.audit.audit_listener import FileReceivedAudit, NoOpAudit


BASE = dict(
    schema_version=1, event_id="cache-use-1", case_id="case-1",
    document_id="doc-1", sequence=1, type="PageCacheReused",
    occurred_at="2026-10-20T12:00:00Z", run_id="run-1", attempt_no=1,
    stage="page_transcription", page_number=1, cached_status="failed",
)


def event(**changes):
    return PageCacheReused(**(BASE | changes))


def test_cache_reused_roundtrip_preserves_cached_status():
    with mock_aws():
        table = boto3.resource("dynamodb", region_name="eu-central-1").create_table(
            TableName="cache-reused-audit",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"},
                       {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"},
                                  {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        event = PageCacheReused(
            schema_version=1, event_id="cache-use-1", case_id="case-1",
            document_id="doc-1", sequence=1, type="PageCacheReused",
            occurred_at="2026-10-20T12:00:00Z", run_id="run-1", attempt_no=1,
            stage="page_transcription", page_number=1, cached_status="failed",
        )
        store = AuditStore(table)
        assert store.put(event) == "inserted"
        assert store.put(event) == "duplicate"
        assert store.read_document("case-1", "doc-1").items == [event]


def test_cache_reused_completed_opaque_allowlist_and_changed_duplicate():
    with mock_aws():
        table = boto3.resource("dynamodb", region_name="eu-central-1").create_table(
            TableName="cache-reused-allowlist",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"},
                       {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"},
                                  {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        store = AuditStore(table)
        first = event(cached_status="completed", cached_method="vision",
                      cached_model="model-x", artifact_ids=("opaque-ref",))
        changed = event(cached_status="failed", cached_method="native",
                        cached_model=None, artifact_ids=None,
                        occurred_at="2026-10-20T13:00:00Z")
        assert store.put(first) == "inserted"
        assert store.put(changed) == "duplicate"
        item = store.read_document("case-1", "doc-1").items
        assert item[0] == first
        assert len(item) == 1
        persisted = table.scan()["Items"][0]
        assert set(persisted) == {"pk", "sk", *first.to_item()}
        assert "text" not in persisted and "error" not in persisted and "url" not in persisted


@pytest.mark.parametrize("field,value", [
    ("run_id", ""), ("attempt_no", True), ("attempt_no", 0),
    ("attempt_no", -1), ("attempt_no", 1.5), ("page_number", True),
    ("page_number", 0), ("page_number", -1), ("page_number", 1.5),
    ("stage", "extraction"), ("cached_status", "unknown"),
    ("cached_method", "invented"), ("cached_model", "bad model"),
    ("artifact_ids", ("",)),
])
def test_cache_reused_rejects_malformed_direct_input(field, value):
    with pytest.raises(ValueError):
        event(**{field: value})


def test_cache_reused_decimal_mapping_roundtrip_and_unknown_optionals():
    original = event(cached_status="completed", cached_method="native")
    mapped = original.to_item() | {"attempt_no": Decimal("1"), "page_number": Decimal("1")}
    assert PageCacheReused.from_item(mapped) == original
    unknown = event(cached_status="failed")
    assert unknown.cached_model is None and unknown.artifact_ids is None
    assert "cached_model" not in unknown.to_item() and "artifact_ids" not in unknown.to_item()


def test_cache_reused_required_arguments_and_missing_run_are_rejected():
    fields = BASE.copy()
    del fields["run_id"]
    with pytest.raises(TypeError):
        PageCacheReused(**fields)
    with pytest.raises(ValueError):
        event(run_id=" ")


@pytest.mark.parametrize("field,value", [
    ("attempt_no", False), ("attempt_no", 0), ("attempt_no", -2),
    ("attempt_no", 1.0), ("page_number", False), ("page_number", 0),
    ("page_number", -1), ("page_number", 1.0),
])
def test_cache_reused_rejects_invalid_scope_types(field, value):
    with pytest.raises(ValueError):
        event(**{field: value})


def test_cache_reused_document_partition_isolates_run_attempt_page_and_document():
    with mock_aws():
        table = boto3.resource("dynamodb", region_name="eu-central-1").create_table(
            TableName="cache-reused-isolation",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"},
                       {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"},
                                  {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        store = AuditStore(table)
        cases = [event(event_id="base"), event(event_id="run", run_id="run-2"),
                 event(event_id="attempt", attempt_no=2),
                 event(event_id="page", page_number=2),
                 event(event_id="document", document_id="doc-2")]
        for value in cases:
            assert store.put(value) == "inserted"
        assert len(store.read_document("case-1", "doc-1").items) == 4
        assert len(store.read_document("case-1", "doc-2").items) == 1
        assert {item.type for item in store.read_document("case-1", "doc-1").items} == {"PageCacheReused"}


def test_cache_reused_allowlist_excludes_all_page_content_and_dispatches_exact_type():
    value = event(cached_status="completed", cached_method="vision",
                  cached_model="model-x", artifact_ids=("opaque-reference",))
    payload = value.to_item()
    payload.update(text="page text", blocks=[{"text": "block"}], tables=[["cell"]],
                   storage_key="s3://bucket/key", url="https://example.invalid",
                   error="raw error", page_content="content", image_bytes="secret")
    assert set(value.to_item()).isdisjoint({"text", "blocks", "tables", "storage_key", "url", "error"})
    assert _event_from_item(payload) == value
    assert _event_from_item(payload).__class__ is PageCacheReused


def test_cache_reused_construction_does_not_touch_external_services(monkeypatch):
    import boto3
    from document_processing.audit.audit_storage import AuditStore

    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected external access")

    monkeypatch.setattr(boto3, "resource", forbidden)
    monkeypatch.setattr(AuditStore, "from_env", classmethod(forbidden))
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "sentinel")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "sentinel")
    monkeypatch.setenv("AUDIT_TABLE_NAME", "sentinel")
    assert event().to_item()["type"] == "PageCacheReused"
    assert NoOpAudit() is not None


def test_existing_file_received_seam_is_fail_open_and_not_a_cache_producer():
    class FailingSink:
        def put(self, event):
            raise RuntimeError("sink unavailable")

    FileReceivedAudit(FailingSink()).file_received(
        case_id="case-1", document_id="doc-1", occurred_at="2026-10-20T12:00:00Z")
    NoOpAudit().file_received(case_id="case-1", document_id="doc-1",
                              occurred_at="2026-10-20T12:00:00Z")
