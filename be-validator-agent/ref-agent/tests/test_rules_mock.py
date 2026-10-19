"""Deterministická část proti skutečnému mocku (bez LLM). Texty jsou vzorové dokumenty se vloženými nesrovnalostmi."""
import json

from conftest import KEY
from helpers import run
from refagent import agent
from refagent.api import HttpClient, list_all_documents, AgentApi


def listing(mock, case_id):
    api = AgentApi(HttpClient(mock.base_url, KEY), case_id)
    return list_all_documents(lambda t: api.list_case_documents(next_token=t))


def by_rule(rep, rule, sev=None):
    return [f for f in rep["findings"] if f["rule_id"] == rule and (sev is None or f["severity"] == sev)]


def test_stavby_findings(mock):
    rep = run(mock.base_url, mock.stavby, listing(mock, mock.stavby))
    assert rep["recommendation"] == agent.REC_REVIEW
    # číslo smlouvy: referenční je záznam ze systému (99_), smlouva a zajišťovací převod mají jiné číslo
    bad = by_rule(rep, "R-CONTRACT-NO", "review")
    assert {f["title"].split("nesoulad v ")[1] for f in bad} == {"0_F_Smlouva.pdf", "2_Form_Zajišťovací převod vl. práva.pdf"}
    ev = [e for f in bad for e in f["evidence"]]
    assert any("17171/25" in e.get("quote", "") and e["page"] == 1 for e in ev)
    assert all(e["document_id"] and e.get("page") for e in ev)
    # faktura chybí v sadě (systematický nález ve vzorcích)
    assert any("faktura" in f["title"] for f in by_rule(rep, "R-COMPLETE", "review"))
    # částečně přečtený dokument
    assert any("částečně" in f["title"] for f in by_rule(rep, "R-READY", "review"))
    # výrobní číslo a cena sedí
    assert by_rule(rep, "R-SERIAL", "ok") and not by_rule(rep, "R-SERIAL", "review")
    assert by_rule(rep, "R-PRICE", "ok")


def test_solom_findings(mock):
    rep = run(mock.base_url, mock.solom, listing(mock, mock.solom))
    assert any("není zpracovaný" in f["title"] for f in by_rule(rep, "R-READY", "review"))      # 409 u Protokolu
    assert by_rule(rep, "R-VAT", "ok")                                                          # 340 200 = 21 % z 1 620 000
    missing = " ".join(f["title"] for f in by_rule(rep, "R-COMPLETE", "review"))
    assert "faktura" in missing and "úhradě DPH" in missing
    nums = " ".join(f["title"] for f in by_rule(rep, "R-CONTRACT-NO", "review"))
    assert "09_Form_Dohoda" in nums and "4_Form_Ručení" in nums                                   # 17023644/25 místo 170170/25


def test_unready_document_is_not_dropped(mock):
    rep = run(mock.base_url, mock.solom, listing(mock, mock.solom))
    d = next(d for d in rep["documents"] if d["title"].startswith("11_"))
    assert d["processing_status"] == "processing" and d["error"]


def test_report_has_evidence_for_every_review_finding(mock):
    rep = run(mock.base_url, mock.stavby, listing(mock, mock.stavby))
    for f in rep["findings"]:
        if f["severity"] == "review":
            assert f["evidence"], f["title"]


def test_label_check_only_for_predicted_and_uses_neighbors(mock):
    rep = run(mock.base_url, mock.solom, listing(mock, mock.solom))
    flagged = [f["title"] for f in by_rule(rep, "R-LABEL", "review")]
    assert any("VOP" in t for t in flagged)       # sousedé mají jiný štítek
    assert any("objedn" in t for t in flagged)  # confidence null
    assert rep["stats"]["vectors_calls"] <= 6      # jen u predicted, ne u každého dokumentu


def test_never_requests_vector_values(mock):
    # parametry velikosti posílá kód vždy sám; ověří se přímo na klientovi
    seen = []
    http = HttpClient(mock.base_url, KEY)
    real = http.get
    http.get = lambda path, params=None: (seen.append(params), real(path, params))[1]
    api = AgentApi(http, mock.stavby)
    did = listing(mock, mock.stavby)[0]["document_id"]
    api.get_document_vectors(did)
    api.get_document_signatures(did)
    assert seen[0]["include_values"] is False and seen[1]["include_vectors"] is False


def test_json_report_is_serializable(mock):
    rep = run(mock.base_url, mock.stavby, listing(mock, mock.stavby))
    assert json.loads(json.dumps(rep, ensure_ascii=False))["case_id"] == mock.stavby
    assert KEY not in json.dumps(rep)
