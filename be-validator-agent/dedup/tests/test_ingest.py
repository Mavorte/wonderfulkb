"""Ingest (infra/ingest/app/main.py) s indexem hashů: `also_in`, registrace, odolnost proti výpadku indexu."""
import importlib
import io
import logging
import sys
from pathlib import Path

import boto3
import pytest

from dedup import hashindex, lookup

from .conftest import BUCKET, HASHES, REGION

APP = Path(__file__).resolve().parents[3] / "ingest" / "app"


def pdf(marker):
    return b"%PDF-1.4\n" + marker.encode() + b"\n%%EOF\n"


@pytest.fixture
def ingest(aws, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("multipart")
    monkeypatch.setenv("API_KEY", "test-key-not-a-secret")
    monkeypatch.setenv("RAW_BUCKET", BUCKET)
    monkeypatch.delenv("HASHES_TABLE", raising=False)
    monkeypatch.syspath_prepend(str(APP))
    for name in ("main", "content_hashes"):
        sys.modules.pop(name, None)
    main = importlib.import_module("main")
    ddb = boto3.client("dynamodb", region_name=REGION)
    ddb.create_table(TableName="wonderfulkb-uw-cases", BillingMode="PAY_PER_REQUEST",
                     AttributeDefinitions=[{"AttributeName": "case_id", "AttributeType": "S"}],
                     KeySchema=[{"AttributeName": "case_id", "KeyType": "HASH"}])
    for case in ("case-1", "case-2", "case-3"):
        ddb.put_item(TableName="wonderfulkb-uw-cases", Item={"case_id": {"S": case}})
    from fastapi.testclient import TestClient
    client = TestClient(main.app, raise_server_exceptions=False)

    def upload(case, *files):
        return client.post(f"/v1/cases/{case}/documents", headers={"x-api-key": "test-key-not-a-secret"},
                           files=[("files", (name, io.BytesIO(data), "application/pdf")) for name, data in files])
    main.upload_as = upload
    yield main
    sys.modules.pop("main", None)
    sys.modules.pop("content_hashes", None)


def sha(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


def test_first_upload_has_empty_also_in_and_is_registered(ingest):
    data = pdf("prvni")
    r = ingest.upload_as("case-1", ("a.pdf", data))
    assert r.status_code == 201
    doc = r.json()["documents"][0]
    assert doc["duplicate"] is False and doc["also_in"] == []
    assert lookup(sha(data)) == [{"case_id": "case-1", "document_id": doc["document_id"], "label": None}]


def test_same_file_in_another_case_reports_also_in_and_still_stores_a_new_document(ingest):
    data = pdf("faktura")
    first = ingest.upload_as("case-1", ("faktura.pdf", data)).json()["documents"][0]
    second = ingest.upload_as("case-2", ("faktura.pdf", data)).json()["documents"][0]
    assert second["document_id"] != first["document_id"] and second["duplicate"] is False
    assert second["also_in"] == [{"case_id": "case-1", "document_id": first["document_id"]}]
    # nový dokument existuje normálně (S3 kopie i řádek) a je v indexu
    s3 = boto3.client("s3", region_name=REGION)
    s3.head_object(Bucket=BUCKET, Key=f"cases/case-2/original/{second['document_id']}.pdf")
    assert len(lookup(sha(data))) == 2
    third = ingest.upload_as("case-3", ("x.pdf", data)).json()["documents"][0]
    assert [m["case_id"] for m in third["also_in"]] == ["case-1", "case-2"]


def test_duplicate_flag_stays_per_case_and_also_in_never_lists_own_case(ingest):
    data = pdf("dvakrat")
    first = ingest.upload_as("case-1", ("a.pdf", data), ("b.pdf", data)).json()["documents"]
    assert [d["duplicate"] for d in first] == [False, True] and all(d["also_in"] == [] for d in first)
    again = ingest.upload_as("case-1", ("a.pdf", data)).json()["documents"][0]
    assert again["duplicate"] is True and again["also_in"] == []
    other = ingest.upload_as("case-2", ("a.pdf", data)).json()["documents"][0]
    assert other["duplicate"] is False and len(other["also_in"]) == 1
    back = ingest.upload_as("case-1", ("a.pdf", data)).json()["documents"][0]
    assert back["duplicate"] is True and back["also_in"] == [{"case_id": "case-2", "document_id": other["document_id"]}]


def test_response_stays_backward_compatible(ingest):
    doc = ingest.upload_as("case-1", ("a.pdf", pdf("kompat"))).json()["documents"][0]
    assert {"document_id", "filename", "received_at", "content_type", "size_bytes", "duplicate"} <= set(doc)
    assert set(doc) - {"document_id", "filename", "received_at", "content_type", "size_bytes", "duplicate"} == {"also_in"}


def test_index_outage_never_fails_the_upload_and_logs_without_content(ingest, caplog, monkeypatch):
    data = pdf("vypadek")
    ingest.upload_as("case-1", ("a.pdf", data))
    boto3.client("dynamodb", region_name=REGION).delete_table(TableName=HASHES)  # tabulka zmizela
    caplog.set_level(logging.INFO)
    r = ingest.upload_as("case-2", ("a.pdf", data), ("b.pdf", pdf("jiny")))
    assert r.status_code == 201
    docs = r.json()["documents"]
    assert len(docs) == 2 and all("also_in" not in d for d in docs)  # pole vynecháno, ne prázdné
    log = "\n".join(r.getMessage() for r in caplog.records if r.name == "wonderfulkb-ingest")  # bez logu HTTP klienta testu
    assert "lookup failed" in log and "ResourceNotFoundException" in log
    assert sha(data) not in log and docs[0]["document_id"] not in log and "case-2" not in log and "a.pdf" not in log
    # dokument se uložil
    boto3.client("s3", region_name=REGION).head_object(Bucket=BUCKET, Key=f"cases/case-2/original/{docs[0]['document_id']}.pdf")


def test_index_timeout_or_error_in_register_is_ignored(ingest, monkeypatch, caplog):
    def boom(*args, **kwargs):
        raise RuntimeError("secret detail " + args[0])
    monkeypatch.setattr(ingest.content_hashes, "register", boom)
    caplog.set_level(logging.INFO)
    r = ingest.upload_as("case-1", ("a.pdf", pdf("registrace")))
    assert r.status_code == 201 and r.json()["documents"][0]["also_in"] == []
    own = "\n".join(r.getMessage() for r in caplog.records if r.name == "wonderfulkb-ingest")
    assert "register failed: RuntimeError" in own and "secret detail" not in caplog.text


def test_empty_table_name_disables_the_index(ingest, monkeypatch):
    monkeypatch.setattr(ingest.content_hashes, "TABLE_NAME", "")
    doc = ingest.upload_as("case-1", ("a.pdf", pdf("vypnuto"))).json()["documents"][0]
    assert "also_in" not in doc
    assert boto3.resource("dynamodb", region_name=REGION).Table(HASHES).scan()["Items"] == []


def test_concurrent_uploads_of_the_same_content_in_different_cases(ingest):
    import threading
    data, results = pdf("soubeh"), {}

    def go(case):
        results[case] = ingest.upload_as(case, ("a.pdf", data))
    threads = [threading.Thread(target=go, args=(c,)) for c in ("case-1", "case-2", "case-3")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert all(r.status_code == 201 for r in results.values())
    assert len(lookup(sha(data))) == 3  # nikdo nevypadl z indexu


def test_ingest_copy_of_index_code_matches_the_library(ingest):
    """Ingest má vlastní kopii zápisu a čtení (samostatný obraz); musí psát a číst totéž co dedup/hashindex.py."""
    data = pdf("shoda")
    s = sha(data)
    ingest.content_hashes.register(s, "case-1", "doc-x")
    table = boto3.resource("dynamodb", region_name=REGION).Table(HASHES)
    item = table.scan()["Items"][0]
    assert set(item) == {"sha256", "case_document", "case_id", "document_id", "registered_at"}
    assert item["case_document"] == hashindex.sort_key("case-1", "doc-x")
    hashindex.register(s, "case-2", "doc-y", "faktura")
    assert ingest.content_hashes.lookup_other_cases(s, "case-1") == [{"case_id": "case-2", "document_id": "doc-y"}]
    assert [m["document_id"] for m in lookup(s, exclude_case_id="case-2")] == ["doc-x"]
    ingest.content_hashes.register(s, "case-2", "doc-y")   # ingest nesmaže štítek od pipeline
    assert next(m for m in lookup(s) if m["case_id"] == "case-2")["label"] == "faktura"
