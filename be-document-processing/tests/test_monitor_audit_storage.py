import pytest
from moto import mock_aws
import boto3

try:
    from document_processing.audit.audit_events import FileReceived
    from document_processing.audit.audit_storage import AuditStore, AuditNotConfigured
except ModuleNotFoundError as exc:
    if not (exc.name == "document_processing.audit" or
            exc.name.startswith("document_processing.audit.")):
        raise
    FileReceived = AuditStore = AuditNotConfigured = None


def test_audit_api_contract_exists():
    assert callable(FileReceived), "Missing FileReceived audit contract"
    assert callable(AuditStore), "Missing AuditStore implementation"


@pytest.fixture
def audit_table():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="eu-central-1")
        table = dynamodb.create_table(
            TableName="wonderfulkb-uw-document-processing-audit",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table


def event(event_id="evt-1", document_id="doc-1", sequence=1):
    return FileReceived(schema_version=1, event_id=event_id, case_id="case-1", document_id=document_id,
                        sequence=sequence, type="FileReceived", occurred_at="2026-10-19T12:00:00Z")


def test_put_then_read_and_duplicate_preserves_first_event(audit_table):
    store = AuditStore(audit_table)
    original = event()
    store.put(original)
    store.put(original.__class__(**{**original.__dict__, "occurred_at": "2026-10-20T12:00:00Z"}))
    page = store.read_document("case-1", "doc-1", limit=10)
    assert page.items == [original]


def test_document_scope_and_bounded_pagination(audit_table):
    store = AuditStore(audit_table)
    store.put(event("evt-1", "doc-1", 1))
    store.put(event("evt-2", "doc-1", 2))
    store.put(event("evt-3", "doc-2", 1))
    first = store.read_document("case-1", "doc-1", limit=1)
    second = store.read_document("case-1", "doc-1", limit=1, next_token=first.next_token)
    assert [x.event_id for x in first.items] == ["evt-1"]
    assert [x.event_id for x in second.items] == ["evt-2"]
    assert second.next_token is None
    assert [x.event_id for x in store.read_document("case-1", "doc-2", limit=10).items] == ["evt-3"]


def test_query_error_propagates_and_never_scans(audit_table, monkeypatch):
    store = AuditStore(audit_table)
    calls = []

    def query(*args, **kwargs):
        calls.append("query")
        raise RuntimeError("read unavailable")

    monkeypatch.setattr(audit_table, "query", query)
    with pytest.raises(RuntimeError, match="read unavailable"):
        store.read_document("case-1", "doc-1", limit=10)
    assert calls == ["query"]


def test_duplicate_identity_does_not_depend_on_sequence(audit_table):
    assert callable(AuditStore), "Missing AuditStore implementation"
    store = AuditStore(audit_table)
    first = event()
    assert store.put(first) == "inserted"
    assert store.put(event(sequence=99)) == "duplicate"
    assert store.read_document("case-1", "doc-1", limit=10).items == [first]


def test_successful_read_is_one_bounded_query(audit_table, monkeypatch):
    assert callable(AuditStore), "Missing AuditStore implementation"
    store = AuditStore(audit_table)
    store.put(event())
    calls = []
    original = audit_table.query

    def query(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    def forbidden_scan(*args, **kwargs):
        pytest.fail("Audit reads must not Scan")

    monkeypatch.setattr(audit_table, "query", query)
    monkeypatch.setattr(audit_table, "scan", forbidden_scan)
    page = store.read_document("case-1", "doc-1", limit=1)
    assert [item.event_id for item in page.items] == ["evt-1"]
    assert len(calls) == 1
    assert calls[0]["Limit"] == 1
    assert calls[0]["ConsistentRead"] is True
    assert "KeyConditionExpression" in calls[0]
    raw = original(**calls[0])["Items"][0]
    assert set(raw) == {"pk", "sk", "schema_version", "event_id", "case_id",
                        "document_id", "sequence", "type", "occurred_at"}


@pytest.mark.parametrize("case_id,document_id", [("other-case", "doc-1"), ("case-1", "doc-2")])
def test_cursor_rejects_other_scope_before_query(audit_table, monkeypatch, case_id, document_id):
    assert callable(AuditStore), "Missing AuditStore implementation"
    store = AuditStore(audit_table)
    store.put(event())
    store.put(event("evt-2"))
    token = store.read_document("case-1", "doc-1", limit=1).next_token
    assert token
    monkeypatch.setattr(audit_table, "query", lambda **kwargs: pytest.fail("Unexpected Query"))
    with pytest.raises(ValueError):
        store.read_document(case_id, document_id, next_token=token)


@pytest.mark.parametrize("limit", [0, 101, True, 1.5])
def test_invalid_limit_rejected_before_query(audit_table, monkeypatch, limit):
    assert callable(AuditStore), "Missing AuditStore implementation"
    monkeypatch.setattr(audit_table, "query", lambda **kwargs: pytest.fail("Unexpected Query"))
    with pytest.raises(ValueError):
        AuditStore(audit_table).read_document("case-1", "doc-1", limit=limit)


@pytest.mark.parametrize("token", ["invalid!", "e30", "x" * 4097])
def test_malformed_cursor_rejected_before_query(audit_table, monkeypatch, token):
    assert callable(AuditStore), "Missing AuditStore implementation"
    monkeypatch.setattr(audit_table, "query", lambda **kwargs: pytest.fail("Unexpected Query"))
    with pytest.raises(ValueError):
        AuditStore(audit_table).read_document("case-1", "doc-1", next_token=token)


def test_unconfigured_store_is_explicitly_disabled(monkeypatch):
    assert callable(AuditStore), "Missing AuditStore implementation"
    monkeypatch.delenv("AUDIT_TABLE_NAME", raising=False)
    monkeypatch.setattr(boto3, "resource", lambda *args, **kwargs: pytest.fail("Unexpected AWS initialization"))
    store = AuditStore.from_env()
    assert store.enabled is False
    assert store.put(event()) == "disabled"
    with pytest.raises(AuditNotConfigured):
        store.read_document("case-1", "doc-1")


def test_write_outage_is_unavailable(audit_table, monkeypatch):
    assert callable(AuditStore), "Missing AuditStore implementation"
    def unavailable(**kwargs):
        raise RuntimeError("write unavailable")
    monkeypatch.setattr(audit_table, "put_item", unavailable)
    assert AuditStore(audit_table).put(event()) == "unavailable"


def test_configured_factory_has_finite_timeouts(audit_table, monkeypatch):
    assert callable(AuditStore), "Missing AuditStore implementation"
    monkeypatch.setenv("AUDIT_TABLE_NAME", audit_table.name)
    calls = []
    class Resource:
        def Table(self, name):
            assert name == audit_table.name
            return audit_table
    def resource(*args, **kwargs):
        calls.append((args, kwargs))
        return Resource()
    monkeypatch.setattr(boto3, "resource", resource)
    assert AuditStore.from_env().enabled is True
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("dynamodb",)
    assert kwargs["region_name"] == "eu-central-1"
    assert kwargs["config"].connect_timeout == 1
    assert kwargs["config"].read_timeout == 2
    assert kwargs["config"].retries["total_max_attempts"] == 1


def test_initialization_failure_is_not_disabled(monkeypatch):
    assert callable(AuditStore), "Missing AuditStore implementation"
    monkeypatch.setenv("AUDIT_TABLE_NAME", "configured")
    def unavailable(*args, **kwargs):
        raise RuntimeError("initialization unavailable")
    monkeypatch.setattr(boto3, "resource", unavailable)
    store = AuditStore.from_env()
    assert store.enabled is True
    assert store.put(event()) == "unavailable"
    with pytest.raises(RuntimeError, match="initialization unavailable"):
        store.read_document("case-1", "doc-1")


@pytest.mark.parametrize("changes", [
    {"schema_version": 2}, {"schema_version": True}, {"type": "Other"},
    {"event_id": ""}, {"case_id": " "}, {"document_id": ""},
    {"sequence": -1}, {"sequence": True}, {"sequence": 1.5},
    {"occurred_at": "2026-10-19T12:00:00"},
    {"occurred_at": "2026-10-19T12:00:00+02:00"},
])
def test_event_validates_small_envelope(changes):
    assert callable(FileReceived), "Missing FileReceived audit contract"
    with pytest.raises(ValueError):
        FileReceived(**{**event().__dict__, **changes})
