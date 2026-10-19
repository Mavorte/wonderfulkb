"""Pravidla na vlastních datech (stub API): schválení, podpisy, chyby API, výměna pravidel."""
import yaml

from conftest import CONTRACT, clean_case, sig
from helpers import listed_of, run, titles
from refagent import agent


def rep_for(stub, case_id, **kw):
    return run(stub.base_url, case_id, listed_of(stub, case_id), **kw)


def test_clean_case_is_approved(stub):
    cid = clean_case(stub)
    rep = rep_for(stub, cid)
    assert rep["recommendation"] == agent.REC_APPROVE, titles(rep, "review")
    assert not any(f["severity"] == "review" for f in rep["findings"])


def test_missing_required_document_goes_to_review(stub):
    text = CONTRACT.replace("b) smlouvu o zajišťovacím", "b) kopii daňového dokladu dodavatele a smlouvu o zajišťovacím")
    cid = clean_case(stub, contract_text=text)
    rep = rep_for(stub, cid)
    assert rep["recommendation"] == agent.REC_REVIEW
    f = next(f for f in rep["findings"] if f["rule_id"] == "R-COMPLETE" and f["severity"] == "review")
    assert f["uncertain"] and "nenalezen v sadě" in f["title"]


def test_contract_number_mismatch_has_evidence(stub):
    cid = clean_case(stub)
    stub.cases[cid]["d-order"]["text"] = "Objednávka k smlouvě č. 7777/25\nVýr. č.: SN1234567\nCena celkem bez DPH:\n1 000 000,00 CZK\n"
    rep = rep_for(stub, cid)
    f = next(f for f in rep["findings"] if f["rule_id"] == "R-CONTRACT-NO" and f["severity"] == "review")
    assert "7777/25" in f["detail"] and "5555/25" in f["detail"]
    assert any(e["document_id"] == "d-order" and "7777/25" in e["quote"] and e["page"] == 1 for e in f["evidence"])


def test_serial_and_price_mismatch(stub):
    cid = clean_case(stub)
    stub.cases[cid]["d-zaj"]["text"] = stub.cases[cid]["d-zaj"]["text"].replace("SN1234567", "SN7654321")
    stub.cases[cid]["d-order"]["text"] = stub.cases[cid]["d-order"]["text"].replace("1 000 000,00", "1 100 000,00")
    rep = rep_for(stub, cid)
    assert any(f["rule_id"] == "R-SERIAL" and f["severity"] == "review" for f in rep["findings"])
    assert any(f["rule_id"] == "R-PRICE" and f["severity"] == "review" for f in rep["findings"])


def test_empty_signatures_are_not_proof_of_missing_signature(stub):
    cid = clean_case(stub)
    stub.cases[cid]["d-contract"]["sigs"] = []
    rep = rep_for(stub, cid)
    f = next(f for f in rep["findings"] if f["rule_id"] == "R-SIGNATURES" and f["severity"] == "review")
    assert rep["recommendation"] == agent.REC_REVIEW and f["uncertain"]
    text = (f["title"] + " " + f["detail"]).lower()
    assert "není důkaz" in text and "92 %" in text and "59 %" in text
    # jediný výskyt „chybí“ smí být ve vyvrácení („neznamená, že podpis chybí“)
    assert text.count("chybí") == text.count("neznamená, že podpis chybí") == 1
    for forbidden in ("nepodeps", "bez podpisu", "není podeps"):
        assert forbidden not in text
    assert "nenašel" in text


def test_signature_api_error_is_not_read_as_no_signatures(stub):
    cid = clean_case(stub)
    stub.cases[cid]["d-contract"]["sigs"] = "error"
    rep = rep_for(stub, cid)
    f = next(f for f in rep["findings"] if f["rule_id"] == "R-SIGNATURES" and f["severity"] == "review")
    assert "nešlo načíst" in f["title"] and "nenašel žádný" not in f["detail"]


def test_missing_role_and_unknown_role_go_to_review_without_guessing(stub):
    cid = clean_case(stub)
    stub.cases[cid]["d-contract"]["sigs"] = [sig(1, "provider", 3), sig(2, "unknown", 3)]
    rep = rep_for(stub, cid)
    f = next(f for f in rep["findings"] if f["rule_id"] == "R-SIGNATURES" and f["severity"] == "review")
    assert "roli" in f["detail"] and "borrower" in f["detail"]
    assert "nenašel podpis s rolí borrower" in f["detail"] and "podpis chybí" not in f["detail"].replace("neznamená, že podpis chybí", "")


def test_copy_suspicion_never_claims_authenticity(stub):
    cid = clean_case(stub)
    stub.cases[cid]["d-contract"]["sigs"] = [sig(1, "provider", 3, suspected=True), sig(2, "borrower", 3)]
    rep = rep_for(stub, cid)
    f = next(f for f in rep["findings"] if f["rule_id"] == "R-SIGNATURES" and f["severity"] == "review")
    assert "nic o pravosti" in f["detail"]
    for word in ("padělan", "nepravý", "falešn"):
        assert word not in f["detail"].lower()
    assert any(e.get("crop_url") and e.get("page") == 3 for e in f["evidence"])


def test_partial_document_is_flagged_not_concluded(stub):
    cid = clean_case(stub)
    d = stub.cases[cid]["d-contract"]
    d.update(status="partial", pages_failed=[3], pages=3)
    d["sigs"] = [sig(1, "provider", 2), sig(2, "borrower", 2)]
    rep = rep_for(stub, cid)
    assert any(f["rule_id"] == "R-READY" and "částečně" in f["title"] for f in rep["findings"])
    sigf = next(f for f in rep["findings"] if f["rule_id"] == "R-SIGNATURES" and f["severity"] == "review")
    assert "nebyly přečtené" in sigf["detail"]


def test_label_confidence_null_or_low_and_neighbor_disagreement(stub):
    extra = [
        dict(id="d-pred-null", title="a.pdf", label="ruceni", label_status="predicted", confidence=None, text="Prohlášení o ručení\n",
             sigs=[sig(1, "provider", 1), sig(2, "guarantor", 1)],
             neighbors=[{"document_id": "n1", "label": "ruceni", "score": 0.9}]),
        dict(id="d-pred-nb", title="b.pdf", label="vop", label_status="predicted", confidence=0.95, text="VOP\n",
             neighbors=[{"document_id": "n1", "label": "smlouva_o_uveru", "score": 0.8}] * 3),
        dict(id="d-ok", title="c.pdf", label="faktura", label_status="predicted", confidence=0.93, text="Faktura\n",
             neighbors=[{"document_id": "n1", "label": "faktura", "score": 0.8}]),
    ]
    cid = clean_case(stub, extra=extra)
    rep = rep_for(stub, cid)
    flagged = {f["title"] for f in rep["findings"] if f["rule_id"] == "R-LABEL" and f["severity"] == "review"}
    assert any("a.pdf" in t for t in flagged) and any("b.pdf" in t for t in flagged) and not any("c.pdf" in t for t in flagged)
    nb = next(f for f in rep["findings"] if f["rule_id"] == "R-LABEL" and "b.pdf" in f["title"])
    assert "ne důkaz chyby" in nb["detail"]


def test_vectors_error_does_not_crash_run(stub):
    extra = [dict(id="d-p", title="p.pdf", label="faktura", label_status="predicted", confidence=0.9, text="Faktura\n")]
    cid = clean_case(stub, extra=extra)
    stub.fail["/vectors"] = 99
    rep = rep_for(stub, cid)
    assert any("nešlo načíst" in f["detail"] for f in rep["findings"] if f["rule_id"] == "R-LABEL")


def test_rules_can_be_swapped(stub, tmp_path):
    cid = clean_case(stub)
    stub.cases[cid]["d-order"]["text"] = "Objednávka k smlouvě č. 7777/25\n"
    only = {"version": 1, "settings": {}, "rules": [r for r in yaml.safe_load(open(agent.DEFAULT_RULES, encoding="utf-8"))["rules"] if r["id"] == "R-READY"]}
    p = tmp_path / "r.yaml"
    p.write_text(yaml.safe_dump(only, allow_unicode=True), encoding="utf-8")
    rep = rep_for(stub, cid, rules=str(p))
    assert {f["rule_id"] for f in rep["findings"]} == {"R-READY"} and rep["recommendation"] == agent.REC_APPROVE
    assert rep["stats"]["signatures_calls"] == 0


def test_unknown_rule_type_is_rejected(tmp_path):
    p = tmp_path / "r.yaml"
    p.write_text("rules:\n  - {id: X, type: nonsense}\n", encoding="utf-8")
    try:
        agent.load_rules(str(p))
    except ValueError as e:
        assert "nonsense" in str(e)
    else:
        raise AssertionError("měla být výjimka")


def test_no_documents_goes_to_review(stub):
    cid = stub.add_case("CASE-EMPTY", [])
    rep = run(stub.base_url, cid, [])
    assert rep["recommendation"] == agent.REC_REVIEW


SYN_CONTRACT = """SMLOUVA O ÚVĚRU Č. 860001/26
Předmět a výrobní číslo HX26000001
Kupní cena bez DPH 1 749 000,00 CZK
\fPříloha Identifikace
Objednávka OBJ-A-26-0001
Faktura uvedená v podkladech FV-A-26-0001
Pojistná smlouva PS-26-A-000001
Zajištění Zajišťovací převod vlastnického práva
Ručení Nesjednáno
"""


def test_attachment_table_variant_requires_listed_documents_only(stub):
    cid = clean_case(stub, contract_text=SYN_CONTRACT)
    rep = rep_for(stub, cid)
    missing = [f["title"] for f in rep["findings"] if f["rule_id"] == "R-COMPLETE-TABLE" and f["severity"] == "review"]
    assert any("faktura" in t for t in missing) and any("pojištění" in t for t in missing)
    assert not any("objedn" in t.lower() or "ručení" in t for t in missing)       # objednávka je v sadě, ručení nesjednáno
    assert not any(f["title"].startswith("Seznam požadovaných podkladů") for f in rep["findings"])
    assert any(f["rule_id"] == "R-COMPLETE-TABLE" and f["severity"] == "ok" for f in rep["findings"])


def test_table_variant_is_skipped_when_list_exists(stub):
    cid = clean_case(stub)
    rep = rep_for(stub, cid)
    assert not any(f["rule_id"] == "R-COMPLETE-TABLE" for f in rep["findings"])
