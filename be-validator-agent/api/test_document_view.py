"""Náhled dokumentu (`…/pages`, zamaskované stránky) a odkrytí originálu (`…/original`, odkaz 60 s + audit).
Spuštění: python3 -m pytest -q  (moto; předpodepsané adresy se jen skládají, nestahují)."""
import json
import logging
import urllib.parse

import pytest
from moto import mock_aws

import core
import fixtures

KEY = "fake-test-key-123"
AUDIT = "wonderfulkb.agent_api.audit"


@pytest.fixture
def env():
    with mock_aws():
        api, index, clients = fixtures.build(KEY)
        c = next(c for c in index["cases"] if c["client"] == "Stavby Fišer a.s.")
        d = next(d for d in c["documents"] if d["processing_status"] == "completed")
        yield api, clients, c["case_id"], d["document_id"]


def call(api, path, key=KEY, request=None):
    return core.handle("GET", "/v1" + path, {}, {"X-Api-Key": key} if key else {}, api=api, request=request)


def put(clients, key, body=b"x"):
    clients.s3.put_object(Bucket=clients.cfg.bucket, Key=key, Body=body)


def set_row(clients, cid, did, **attrs):
    row = clients.ddb.get_item(TableName=clients.cfg.analysis_table,
                               Key={"case_id": {"S": cid}, "document_id": {"S": did}})["Item"]
    for k, v in attrs.items():
        if v is None:
            row.pop(k, None)
        else:
            row[k] = {"N": str(v)} if isinstance(v, int) else {"S": v}
    clients.ddb.put_item(TableName=clients.cfg.analysis_table, Item=row)


def redact(clients, cid, did, pages=(1, 2)):
    rkey = f"cases/{cid}/redacted/{did}.pdf"
    put(clients, rkey, b"%PDF-redacted")
    for n in pages:
        put(clients, f"cases/{cid}/analysis/{did}/pages/{n}.png", b"\x89PNG")
    set_row(clients, cid, did, redacted_s3_key=rkey, page_count=max(pages))
    return rkey


def ingest(clients, cid, did, key=None, filename="Smlouva o úvěru.pdf"):
    key = key or f"cases/{cid}/original/{did}.pdf"
    fixtures._put(clients.ddb, clients.cfg.documents_table,
                  {"case_id": cid, "document_id": did, "s3_key": key, "filename": filename,
                   "content_type": "application/pdf", "sha256": "ab" * 32})
    return key


def audit_records(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == AUDIT]


# ---- náhled -----------------------------------------------------------------

def test_pages_from_redacted_copy(env):
    api, clients, cid, did = env
    redact(clients, cid, did, pages=(1, 2))
    put(clients, f"cases/{cid}/original/{did}.pdf", b"%PDF-original")
    st, b = call(api, f"/cases/{cid}/documents/{did}/pages")
    assert st == 200
    assert b["redacted"] is True and b["page_count"] == 2 and b["original_available"] is True
    assert [p["page"] for p in b["pages"]] == [1, 2]
    assert all(f"/analysis/{did}/pages/{p['page']}.png" in p["preview_url"] for p in b["pages"])
    assert f"/redacted/{did}.pdf" in b["preview_pdf_url"]
    assert b["reveal_path"] == f"/cases/{cid}/documents/{did}/original"
    assert "/original/" not in json.dumps(b)  # náhled nikdy neodkazuje na čitelný originál


def test_pages_missing_png_is_null(env):
    api, clients, cid, did = env
    redact(clients, cid, did, pages=(1,))
    set_row(clients, cid, did, page_count=3)
    st, b = call(api, f"/cases/{cid}/documents/{did}/pages")
    assert st == 200 and [p["preview_url"] is not None for p in b["pages"]] == [True, False, False]


def test_pages_without_redaction_not_served(env):
    """Stránky zpracované před redakcí vznikly z čitelného originálu: preview_url se nevydá."""
    api, clients, cid, did = env
    put(clients, f"cases/{cid}/analysis/{did}/pages/1.png", b"\x89PNG")
    set_row(clients, cid, did, redacted_s3_key=None, page_count=1)
    st, b = call(api, f"/cases/{cid}/documents/{did}/pages")
    assert st == 200 and b["redacted"] is False and b["preview_pdf_url"] is None
    assert b["pages"] == [{"page": 1, "preview_url": None}]


def test_pages_foreign_redacted_key_ignored(env):
    api, clients, cid, did = env
    put(clients, f"cases/jiny/redacted/{did}.pdf")
    set_row(clients, cid, did, redacted_s3_key=f"cases/jiny/redacted/{did}.pdf")
    st, b = call(api, f"/cases/{cid}/documents/{did}/pages")
    assert st == 200 and b["redacted"] is False and b["preview_pdf_url"] is None


def test_pages_errors(env):
    api, clients, cid, did = env
    assert call(api, f"/cases/{cid}/documents/neexistuje/pages")[0] == 404
    assert call(api, f"/cases/{cid}/documents/{did}/pages", key="")[0] == 401
    assert call(api, f"/cases/{cid}/documents/{did}/pages", key="spatny")[0] == 403
    set_row(clients, cid, did, processing_status="processing")
    st, b = call(api, f"/cases/{cid}/documents/{did}/pages")
    assert st == 409 and b["processing_status"] == "processing"


# ---- odkrytí originálu ------------------------------------------------------

def test_original_reveal_url_and_audit(env, caplog):
    api, clients, cid, did = env
    key = ingest(clients, cid, did)
    put(clients, key, b"%PDF-original")
    caplog.set_level(logging.INFO, logger=AUDIT)
    st, b = call(api, f"/cases/{cid}/documents/{did}/original", request={"request_id": "r-1"})
    assert st == 200 and b["expires_in"] == 60 and b["content_type"] == "application/pdf"
    assert b["filename"] == "Smlouva o úvěru.pdf"
    u = urllib.parse.urlparse(b["url"])
    q = urllib.parse.parse_qs(u.query)
    assert u.path.endswith(f"/original/{did}.pdf") and q["X-Amz-Expires"] == ["60"]
    assert q["response-content-disposition"][0].startswith("inline; filename*=UTF-8''Smlouva%20o%20%C3%BAv%C4%9Bru.pdf")
    [rec] = audit_records(caplog)
    assert rec["event"] == "document_reveal" and rec["outcome"] == "revealed" and "signature_id" not in rec
    assert rec["request_id"] == "r-1" and rec["caller"].startswith("fp:")
    assert KEY not in caplog.text and b["url"] not in caplog.text  # klíč ani odkaz v logu nejsou


def test_original_before_processing(env):
    """Originál jde ukázat i u dokumentu, který ještě čeká na zpracování (jen řádek ingestu)."""
    api, clients, cid, _ = env
    key = ingest(clients, cid, "novy-dokument")
    put(clients, key, b"%PDF")
    st, b = call(api, f"/cases/{cid}/documents/novy-dokument/original")
    assert st == 200 and b["document_id"] == "novy-dokument"


def test_original_fallback_key_without_ingest(env):
    api, clients, cid, did = env
    put(clients, f"cases/{cid}/original/{did}.pdf", b"%PDF")
    st, b = call(api, f"/cases/{cid}/documents/{did}/original")
    assert st == 200 and b["filename"] == f"{did}.pdf"


@pytest.mark.parametrize("bad", ["cases/jiny/original/x.pdf", "cases/{cid}/redacted/{did}.pdf",
                                 "cases/{cid}/analysis/{did}/text.txt", "cases/{cid}/../jiny/original/x.pdf"])
def test_original_rejects_foreign_or_masked_key(env, bad, caplog):
    """Klíč z tabulky ingestu mimo `cases/<case>/` nebo do analysis/redacted se nepoužije; bez originálu 404."""
    api, clients, cid, did = env
    bad = bad.format(cid=cid, did=did)
    put(clients, bad.replace("/../", "/"), b"data")
    put(clients, bad, b"data")
    ingest(clients, cid, did, key=bad)
    caplog.set_level(logging.INFO, logger=AUDIT)
    st, _ = call(api, f"/cases/{cid}/documents/{did}/original")
    assert st == 404
    assert audit_records(caplog)[-1]["outcome"] == "not_found"


def test_original_auth_not_audited(env, caplog):
    api, clients, cid, did = env
    caplog.set_level(logging.INFO, logger=AUDIT)
    assert call(api, f"/cases/{cid}/documents/{did}/original", key="")[0] == 401
    assert call(api, f"/cases/{cid}/documents/{did}/original", key="spatny")[0] == 403
    assert call(api, f"/cases/{cid}/documents/..%2F/original")[0] in (400, 404)
    assert audit_records(caplog) == []
