"""Testy evaluace proti fixturám a mocku (bez AWS)."""
import copy
import json
import os

import pytest

import e2e_metrics as M
import evaluate_e2e as E
from e2e_report import render_markdown
from e2e_transport import MockServer, Result, Transport
from fixture_api import FixtureTransport

EVAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PERFECT = dict(label_error=0, ocr_error=0, sig_miss=0, sig_miss_scan=0, spurious=0, server_error=0, merge=0,
               role_error=0, vec_miss=0)


@pytest.fixture(scope="module")
def truth():
    return E.load_truth(os.path.join(EVAL, "truth.yaml"))


def run(tr, mapping, truth, neighbors=3, sample=1, known=None):
    ti = E.TruthIndex(truth)
    opts = {"neighbors": neighbors, "workers": 1, "sleep": 0, "call_all": False, "sample_values": sample,
            "known_status_extra": known or {}}
    data = E.collect(tr, mapping, opts)
    meta = {"generated_at": "t", "source": {"mode": tr.mode, "host": None, "simulated": getattr(tr, "simulated", False)},
            "mapping": {"path": None, "cases": len(mapping), "documents": sum(len(c["documents"]) for c in mapping)},
            "truth": {"path": "truth.yaml", "generated_at": None, "zip_sha256": None},
            "options": {"neighbors": neighbors, "retries": 0, "timeout": 1, "workers": 1, "sample_values": sample}}
    return E.evaluate(data, ti, opts, meta)


# ---- perfektní fixtura: metriky musí vyjít přesně ----------------------------------

@pytest.fixture(scope="module")
def perfect(truth):
    tr = FixtureTransport(truth, seed=3, **PERFECT)
    return run(tr, tr.mapping(), truth), tr


def test_perfect_generic_is_complete_and_clean(perfect):
    res, _ = perfect
    g = res["per_group"]["generic"]
    assert g["cases"] == 20 and g["documents"] == 165
    assert g["availability"]["available"]["k"] == 165
    s = g["signatures"]
    assert s["expected"] == 323 and s["completeness_at_place"]["k"] == 323
    assert s["false_findings"] == 0 and s["duplicate_or_merged"] == 0
    assert s["roles"]["accuracy_exact"]["value"] == 1.0
    assert g["labels"]["accuracy"]["value"] == 1.0 and g["labels"]["wrong"] == 0
    assert g["vectors"]["image_pages_equal_page_count"]["value"] == 1.0
    assert g["vectors"]["text_vectors_ok"]["value"] == 1.0
    assert g["availability"]["field_recall"]["value"] == 1.0


def test_groups_are_never_mixed(perfect):
    res, _ = perfect
    assert set(res["per_group"]) == {"generic", "original"}
    o = res["per_group"]["original"]["signatures"]
    assert o["truth_kinds"] == {"reviewed_page": 15}       # 16 dokumentů, solom 11_ je ve stavu processing (409)
    # počty originálů se do generických nesčítají
    assert res["per_group"]["generic"]["signatures"]["expected"] == 323
    md = render_markdown(res, E.load_truth(os.path.join(EVAL, "truth.yaml")))
    assert "### generic" in md and "### original" in md


def test_unmapped_kinds_excluded_from_label_accuracy(perfect):
    res, _ = perfect
    lb = res["per_group"]["generic"]["labels"]
    assert lb["unmapped_documents"] == 15            # 10 cerpani + 5 splatky, viz truth
    assert lb["eligible"] == 150


def test_not_ready_document_is_409_and_not_available(perfect):
    res, _ = perfect
    docs = [d for d in res["documents"] if d["group"] == "original" and d.get("processing_status") == "processing"]
    assert len(docs) == 1 and docs[0]["available"] is False and docs[0]["detail_status"] == 409
    assert res["latency"]["detail"]["not_ready_409"] == 1
    assert res["latency"]["detail"]["error_rate"]["k"] == 0     # 409 není chyba


def test_happy_path_scenarios_have_no_findings_except_not_ready(perfect):
    res, _ = perfect
    gen = [s for s in res["scenarios"] if s["truth_case"] and s["truth_case"].startswith("SYN-")]
    assert len(gen) == 20 and all(s["verdict"] == "ok" for s in gen)


def test_neighbors_come_only_from_verified(perfect):
    res, _ = perfect
    nb = res["per_group"]["generic"]["vectors"]["neighbors"]
    assert nb["violations"] == {} and nb["requested"] == 165
    # sousedé jsou ve fixtuře v testované sadě, takže jejich verified jde ověřit
    assert nb["unverifiable_neighbors"] == 0


# ---- fixtura s chybami: metriky je musí zachytit -------------------------------------

def test_injected_errors_are_detected(truth):
    tr = FixtureTransport(truth, seed=11)
    res = run(tr, tr.mapping(), truth)
    g = res["per_group"]["generic"]
    s = g["signatures"]
    assert s["completeness_at_place"]["value"] < 0.97 and s["missed_total"] > 0
    assert s["false_findings"] > 0
    assert g["labels"]["wrong"] > 0
    cal = g["labels"]["calibration"]
    assert cal["mean_confidence_wrong"] < cal["mean_confidence_correct"]
    assert g["vectors"]["image_pages_equal_page_count"]["value"] < 1.0
    assert g["availability"]["field_recall_by_text_layer"]["digital"]["value"] == 1.0
    assert g["availability"]["field_recall_by_text_layer"]["image_only"]["value"] < 1.0
    assert res["latency"]["detail"]["server_errors"] >= 0


def test_fixture_is_deterministic(truth):
    def go():
        tr = FixtureTransport(truth, seed=5)
        r = run(tr, tr.mapping(), truth)
        r["meta"] = None
        return json.dumps(r, sort_keys=True, default=str)
    assert go() == go()


# ---- mock (skutečný server z infra/validator-agent-mock) -----------------------------

@pytest.fixture(scope="module")
def mock_run(truth):
    ms = MockServer()
    try:
        tr = ms.transport()
        idx = tr.get("/_mock/cases").body
        mapping, known = E.mapping_from_index(idx, E.TruthIndex(truth))
        yield run(tr, mapping, truth, known=known), ms
    finally:
        ms.close()


def test_mock_resolves_originals_and_skips_reference_corpus(mock_run):
    res, _ = mock_run
    assert set(res["per_group"]) == {"original"}
    assert res["per_group"]["original"]["cases"] == 2
    assert res["unresolved"]["cases"] == []


def test_mock_labels_and_availability(mock_run):
    res, _ = mock_run
    g = res["per_group"]["original"]
    assert g["labels"]["accuracy"]["k"] == g["labels"]["accuracy"]["n"] == 15
    assert g["availability"]["available"]["k"] == 15 and g["availability"]["available"]["n"] == 16
    assert g["availability"]["partial"] == 1
    assert g["vectors"]["image_pages_equal_page_count"]["value"] == 1.0
    assert g["vectors"]["neighbors"]["violations"] == {}
    assert g["vectors"]["neighbors"]["unverifiable_neighbors"] == 0   # sousedé jsou v indexu mocku označeni verified


def test_mock_signatures_not_good_but_measured_against_review(mock_run):
    res, _ = mock_run
    s = res["per_group"]["original"]["signatures"]
    assert s["truth_kinds"] == {"reviewed_page": 15} and s["expected"] == 33
    assert s["completeness_at_place"]["value"] < 0.5        # mock dává všechny podpisy na poslední stranu
    assert s["false_findings"] > 0


def test_report_renders_and_has_required_sections(mock_run, truth):
    res, _ = mock_run
    md = render_markdown(res, truth)
    for h in ("## Souhrn", "## 1. Volání 1", "## 2. Štítek a kalibrace", "## 3. Volání 2", "## 4. Volání 3",
              "## 5. Latence", "## 6. Scénáře", "## 7. Co nelze změřit"):
        assert h in md
    assert "Podpisy se vyhodnocují zvlášť" in md


# ---- chování při chybách -------------------------------------------------------------

class Always(Transport):
    mode = "always"

    def __init__(self, status, body=None):
        super().__init__()
        self.status, self.body = status, body or {"error": "x"}

    def _once(self, path, query):
        return Result(self.status, self.body, 1.0, None if self.status else "timeout")


@pytest.mark.parametrize("status", [500, 403, 404, None])
def test_all_calls_failing_still_produces_a_report(truth, status):
    tr = FixtureTransport(truth, seed=1)
    mapping = tr.mapping()[:3]
    res = run(Always(status), mapping, truth)
    n_docs = sum(len(c["documents"]) for c in mapping)
    g = list(res["per_group"].values())
    assert sum(x["availability"]["available"]["k"] for x in g) == 0
    assert res["latency"]["detail"]["n"] == n_docs
    bucket = "server_errors" if status in (500, None) else "client_errors"
    assert res["latency"]["detail"][bucket] == n_docs
    assert render_markdown(res, truth)


def test_empty_signature_list_is_valid_answer_not_error(truth):
    class Empty(FixtureTransport):
        def _signatures(self, dd, ready):
            return {"case_id": dd["case"], "document_id": dd["doc_id"], "signatures": []}
    tr = Empty(truth, seed=1, **PERFECT)
    res = run(tr, tr.mapping(), truth)
    s = res["per_group"]["generic"]["signatures"]
    assert s["found_in_known_docs"] == 0 and s["completeness_at_place"]["value"] == 0.0
    assert s["false_findings"] == 0 and res["latency"]["signatures"]["error_rate"]["k"] == 0


def test_shape_violations_are_counted(truth):
    class Broken(FixtureTransport):
        def _signatures(self, dd, ready):
            return {"case_id": dd["case"], "document_id": dd["doc_id"], "signatures": [{"page": 1}]}
    tr = Broken(truth, seed=1, **PERFECT)
    res = run(tr, tr.mapping()[:2], truth)
    assert res["per_group"]["generic"]["signatures"]["shape_errors"] > 0


# ---- přiřazení pravdy a varianty ------------------------------------------------------

def test_truth_resolution_modes(truth):
    ti = E.TruthIndex(truth)
    a01 = truth["cases"]["SYN-A01"]["documents"]
    # explicitně
    assert ti.resolve_case({"source_case": "SYN-B02", "documents": []}) == ("SYN-B02", "source_case")
    # podle ID v názvu případu
    assert ti.resolve_case({"case_id": "x", "scenario": "SYN-C04 happy", "documents": []})[0] == "SYN-C04"
    # podle SHA-256
    docs = [{"document_id": "1", "filename": "whatever.pdf", "sha256": a01["00_Smlouva_o_uveru.pdf"]["sha256"]}]
    assert ti.resolve_case({"case_id": "z", "documents": docs})[0] == "SYN-A01"
    assert ti.resolve_doc("SYN-A01", docs[0]) == ("SYN-A01", "00_Smlouva_o_uveru.pdf")
    # podle souborů: původní případ je určený jednoznačně
    solom = [{"document_id": str(i), "filename": f} for i, f in enumerate(truth["cases"]["solom-rec"]["documents"])]
    assert ti.resolve_case({"case_id": "u", "documents": solom})[0] == "solom-rec"
    # soubory A01 až A05 jsou shodné: bez označení případu nejde rozhodnout
    amb = [{"document_id": str(i), "filename": f} for i, f in enumerate(a01)]
    assert ti.resolve_case({"case_id": "u", "documents": amb}) == (None, None)


def test_filename_matching_ignores_diacritics_and_case(truth):
    ti = E.TruthIndex(truth)
    d = {"filename": "SYN-A01/02_zajistovaci_prevod.PDF"}
    assert ti.resolve_doc("SYN-A01", d) == ("SYN-A01", "02_Zajistovaci_prevod.pdf")


def test_unresolved_documents_are_listed_not_scored(truth):
    tr = FixtureTransport(truth, seed=1, **PERFECT)
    m = tr.mapping()
    case = copy.deepcopy(m[0])
    case["case_id"] = m[0]["case_id"]
    case["documents"][0]["filename"] = "neznamy_soubor.pdf"
    res = run(tr, [case], truth)
    assert len(res["unresolved"]["documents"]) == 1
    doc = next(d for d in res["documents"] if d["filename"] == "neznamy_soubor.pdf")
    assert doc["resolved"] is False and "label_outcome" not in doc


class DropSignature(FixtureTransport):
    """Fixtura, jejíž dokument „SYN-A01/00“ nemá podpis příjemce na straně 3 (jako varianta scénáře 5)."""

    def _signatures(self, dd, ready):
        body = super()._signatures(dd, ready)
        if dd["case"] == "SYN-A01" and dd["file"] == "00_Smlouva_o_uveru.pdf":
            for i, s in enumerate(body["signatures"]):
                if s["page"] == 3 and s["role"] == "borrower":
                    del body["signatures"][i]
                    break
        return body


def _variant_mapping(tr):
    m = [c for c in tr.mapping() if c["case_id"] == "SYN-A01"]
    m[0]["scenario"] = "chybi_podpis"
    for d in m[0]["documents"]:
        if d["filename"] == "00_Smlouva_o_uveru.pdf":
            d["variant"] = {"removed_signatures": [{"page": 3, "role": "borrower"}]}
    return m


def test_missing_signature_variant_is_a_finding_not_a_detector_miss(truth):
    tr = DropSignature(truth, seed=2, **PERFECT)
    res = run(tr, _variant_mapping(tr), truth)
    s = res["per_group"]["generic"]["signatures"]
    assert s["completeness_at_place"]["value"] == 1.0 and s["false_findings"] == 0   # detektor nechybuje
    sc = res["scenarios"][0]
    assert sc["scenario"] == "chybi_podpis" and sc["expected_findings"] == 1
    assert sc["findings_by_type"].get("podpis_chybi") == 1 and sc["verdict"] == "ok"


def test_missing_signature_variant_not_reported_when_still_present(truth):
    tr = FixtureTransport(truth, seed=2, **PERFECT)           # podpis ve fixtuře zůstal
    res = run(tr, _variant_mapping(tr), truth)
    sc = res["scenarios"][0]
    assert sc["verdict"] == "nalezeno_0_z_1"
    assert res["per_group"]["generic"]["signatures"]["false_findings"] == 1   # nález navíc proti upravené pravdě


def test_missing_document_scenario(truth):
    tr = FixtureTransport(truth, seed=2, **PERFECT)
    m = [c for c in tr.mapping() if c["case_id"] == "SYN-A02"]
    m[0]["scenario"] = "2"
    m[0]["documents"] = [d for d in m[0]["documents"] if d["filename"] != "04_Ruceni.pdf"]
    m[0]["removed_documents"] = ["04_Ruceni.pdf"]
    # fixtura by seznam stejně vrátila celý case; omez ho na dokumenty v mappingu
    keep = {d["document_id"] for d in m[0]["documents"]}
    orig = tr._once

    def once(path, query):
        r = orig(path, query)
        if path.endswith("/documents") and r.status == 200:
            r.body["documents"] = [x for x in r.body["documents"] if x["document_id"] in keep]
        return r
    tr._once = once
    res = run(tr, m, truth)
    sc = res["scenarios"][0]
    assert sc["scenario"] == "chybi_dokument" and sc["verdict"] == "ok" and sc["expected_findings"] == 1


def test_unmeasurable_scenarios_are_declared(truth):
    tr = FixtureTransport(truth, seed=2, **PERFECT)
    m = tr.mapping()[:1]
    m[0]["scenario"] = "4"
    res = run(tr, m, truth)
    assert res["scenarios"][0]["scenario"] == "spatne_udaje"
    m[0]["scenario"] = "spatne_udaje"
    res = run(tr, m, truth)
    assert res["scenarios"][0]["verdict"] == "neměřitelné"


# ---- bezpečnost -----------------------------------------------------------------------

def test_cli_over_http_never_leaks_key_or_crop_urls(tmp_path, capsys, monkeypatch, truth):
    ms = MockServer()
    try:
        monkeypatch.setenv("AGENT_API_KEY", ms.api_key)
        tr = ms.transport()
        idx = tr.get("/_mock/cases").body
        mapping, _ = E.mapping_from_index(idx, E.TruthIndex(truth))
        mp = tmp_path / "mapping.json"
        mp.write_text(json.dumps(mapping), encoding="utf-8")
        E.main(["--mapping", str(mp), "--base-url", ms.base_url, "--out-dir", str(tmp_path), "--name", "r"])
    finally:
        ms.close()
    out = capsys.readouterr()
    blob = out.out + out.err + (tmp_path / "r.md").read_text(encoding="utf-8") + (tmp_path / "r.json").read_text(encoding="utf-8")
    assert ms.api_key not in blob
    assert "_mock/crops" not in blob and "x-api-key" not in blob.lower()
    assert (tmp_path / "r.json").exists()


def test_missing_key_message_does_not_print_values(monkeypatch, tmp_path):
    monkeypatch.delenv("AGENT_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    mp = tmp_path / "m.json"
    mp.write_text("[]")
    with pytest.raises(SystemExit) as e:
        E.main(["--mapping", str(mp), "--base-url", "http://127.0.0.1:1/v1"])
    assert "AGENT_API_KEY" in str(e.value)


def test_missing_mapping_is_explained(monkeypatch):
    monkeypatch.setattr(E, "DEFAULT_MAPPING", "/nonexistent/mapping.json")
    with pytest.raises(SystemExit) as e:
        E.main(["--fixture", "--mapping", "/nonexistent/other.json"])
    assert e.type is SystemExit


# ---- reálný mapping od v-dataset ---------------------------------------------------------

REAL_MAPPING = os.path.join(EVAL, "..", "dataset", "mapping.json")


@pytest.mark.skipif(not os.path.exists(REAL_MAPPING), reason="mapping.json zatím neexistuje")
def test_real_mapping_resolves_all_documents_by_sha256(truth):
    ti = E.TruthIndex(truth)
    n = 0
    for c in E.load_mapping(REAL_MAPPING):
        ck, _ = ti.resolve_case(c)
        assert ck == c["case_id"]
        for d in c["documents"]:
            assert ti.resolve_doc(ck, d) == (ck, d["filename"]), d
            n += 1
    assert n == 165


def test_descriptive_scenario_text_falls_back_to_truth_scenario(truth):
    tr = FixtureTransport(truth, seed=2, **PERFECT)
    m = [c for c in tr.mapping() if c["case_id"] == "SYN-A01"]
    m[0]["scenario"] = "demolition-shears (varianta 1, předloha Solom Rec)"
    res = run(tr, m, truth)
    assert res["scenarios"][0]["scenario"] == "happy_path" and res["scenarios"][0]["verdict"] == "ok"


def test_auto_case_builds_mapping_from_api_list(truth, tmp_path):
    mp = tmp_path / "m.json"
    mp.write_text("[]")
    res = E.main(["--fixture", "--mapping", str(mp), "--auto-case", "solom-rec=solom-rec", "--out-dir", str(tmp_path),
                  "--name", "a", "--quiet", "--groups", "original"])
    g = res["per_group"]["original"]
    assert g["cases"] == 1 and g["documents"] == 9 and res["unresolved"]["documents"] == []
