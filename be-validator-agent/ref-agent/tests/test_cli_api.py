"""CLI, klient API, ingest a offline seznam dokumentů."""
import json

import pytest

import validate_case
from conftest import KEY, clean_case, sig
from refagent.api import ApiError, HttpClient, documents_from_file, documents_from_ingest


def test_client_sends_key_header_and_retries_5xx_but_not_4xx(stub):
    cid = clean_case(stub)
    slept = []
    stub.fail["/documents"] = 2
    http = HttpClient(stub.base_url, KEY, sleep=slept.append)
    assert http.get(f"/cases/{cid}/documents")["documents"]
    assert http.calls == 3 and len(slept) == 2
    with pytest.raises(ApiError) as e:
        HttpClient(stub.base_url, "spatny-klic-1", sleep=slept.append).get(f"/cases/{cid}/documents")
    assert e.value.status == 403 and "spatny-klic-1" not in str(e.value)
    with pytest.raises(ApiError) as e:
        http.get("/cases/NEEXISTUJE/documents")
    assert e.value.status == 404


def test_client_gives_up_after_retries(stub):
    cid = clean_case(stub)
    stub.fail["/documents"] = 99
    http = HttpClient(stub.base_url, KEY, retries=2, sleep=lambda s: None)
    with pytest.raises(ApiError) as e:
        http.get(f"/cases/{cid}/documents")
    assert e.value.status == 503 and http.calls == 3


def test_ingest_listing_paginates(stub):
    stub.ingest["C1"] = [{"document_id": f"d{i}", "filename": f"{i}.pdf"} for i in range(230)]
    docs = documents_from_ingest(stub.ingest_url, KEY, "C1")
    assert len(docs) == 230 and docs[0]["filename"] == "0.pdf"


def test_documents_file_accepts_ingest_shape_and_bare_list(tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps({"case_id": "X", "documents": [{"document_id": "a", "filename": "a.pdf"}], "next_token": None}))
    assert documents_from_file(str(p)) == [{"document_id": "a", "filename": "a.pdf"}]
    p.write_text(json.dumps([{"document_id": "b"}]))
    assert documents_from_file(str(p)) == [{"document_id": "b"}]
    p.write_text(json.dumps({"x": 1}))
    with pytest.raises(ValueError):
        documents_from_file(str(p))


def test_cli_no_llm_with_ingest_url(stub, monkeypatch, capsys, tmp_path):
    cid = clean_case(stub)
    stub.ingest[cid] = [{"document_id": d["id"], "filename": d["title"]} for d in stub.cases[cid].values()]
    monkeypatch.setenv("AGENT_API_KEY", KEY)
    out = tmp_path / "r.json"
    rc = validate_case.main(["--case-id", cid, "--base-url", stub.base_url, "--ingest-url", stub.ingest_url, "--no-llm", "--json-out", str(out)])
    text = capsys.readouterr().out
    assert rc == 0 and "Doporučení: SCHVÁLIT" in text and "bez LLM" in text and "ingest API" in text
    assert KEY not in text and KEY not in out.read_text()
    assert json.loads(out.read_text())["recommendation"] == "schválit"


def test_cli_documents_file_and_review_report(stub, monkeypatch, capsys, tmp_path):
    cid = clean_case(stub)
    stub.cases[cid]["d-contract"]["sigs"] = []
    f = tmp_path / "docs.json"
    f.write_text(json.dumps({"documents": [{"document_id": d["id"], "filename": d["title"]} for d in stub.cases[cid].values()]}))
    monkeypatch.setenv("AGENT_API_KEY", KEY)
    rc = validate_case.main(["--case-id", cid, "--base-url", stub.base_url, "--documents-file", str(f), "--no-llm"])
    text = capsys.readouterr().out
    assert rc == 0 and "KE KONTROLE ČLOVĚKEM" in text and "není důkaz" in text and "soubor docs.json" in text
    assert "volání agent API" in text


def test_cli_wrong_key_reports_error_without_leaking_it(stub, monkeypatch, capsys):
    cid = clean_case(stub)
    monkeypatch.setenv("AGENT_API_KEY", "tajny-klic-12345")
    monkeypatch.delenv("API_KEY", raising=False)
    rc = validate_case.main(["--case-id", cid, "--base-url", stub.base_url, "--no-llm"])
    cap = capsys.readouterr()
    assert rc == 2 and "403" in cap.err and "tajny-klic-12345" not in cap.out + cap.err


def test_cli_refuses_model_55(stub, monkeypatch, capsys):
    cid = clean_case(stub)
    monkeypatch.setenv("AGENT_API_KEY", KEY)
    rc = validate_case.main(["--case-id", cid, "--base-url", stub.base_url, "--model-id", "eu.anthropic.claude-opus-5-5"])
    assert rc == 2 and "nepoužívá" in capsys.readouterr().err


def test_signed_crop_url_query_is_stripped_unless_requested(stub, monkeypatch, capsys, tmp_path):
    cid = clean_case(stub)
    stub.cases[cid]["d-contract"]["sigs"] = [dict(sig(1, "provider", 3, suspected=True), crop_url="https://s3.invalid/c.png?X-Amz-Signature=SECRETSIG"), sig(2, "borrower", 3)]
    monkeypatch.setenv("AGENT_API_KEY", KEY)
    out = tmp_path / "r.json"
    validate_case.main(["--case-id", cid, "--base-url", stub.base_url, "--no-llm", "--json-out", str(out)])
    text = capsys.readouterr().out
    assert "SECRETSIG" not in text and "SECRETSIG" not in out.read_text() and "https://s3.invalid/c.png" in text
    validate_case.main(["--case-id", cid, "--base-url", stub.base_url, "--no-llm", "--full-crop-urls"])
    assert "SECRETSIG" in capsys.readouterr().out


def test_new_signature_shape_shows_preview_and_reveal_path(stub, monkeypatch, capsys, tmp_path):
    """Volání 3 po redakci: místo crop_url přijde zkreslený preview_url a reveal_path; podepsaná query se ořízne."""
    cid = clean_case(stub)
    new = dict(sig(1, "provider", 3, suspected=True), preview_url="https://s3.invalid/p.png?X-Amz-Signature=PREVSIG",
               reveal_path=f"/cases/{cid}/documents/d-contract/signatures/sig_01/image", crop_available=True)
    new.pop("crop_url", None)
    stub.cases[cid]["d-contract"]["sigs"] = [new, sig(2, "borrower", 3)]
    monkeypatch.setenv("AGENT_API_KEY", KEY)
    out = tmp_path / "r.json"
    validate_case.main(["--case-id", cid, "--base-url", stub.base_url, "--no-llm", "--json-out", str(out)])
    text = capsys.readouterr().out
    assert "PREVSIG" not in text and "PREVSIG" not in out.read_text()
    assert "náhled (zkreslený): https://s3.invalid/p.png" in text
    assert f"GET /cases/{cid}/documents/d-contract/signatures/sig_01/image" in text
