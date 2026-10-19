import json
import os

import pytest

import e2e_metrics as M

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.join(HERE, "..")


@pytest.fixture(scope="module")
def truth():
    with open(os.path.join(EVAL, "truth.json"), encoding="utf-8") as f:
        return json.load(f)


def generic(truth):
    return {k: c for k, c in truth["cases"].items() if c["group"] == "generic"}


def test_counts_match_bundle_readme(truth):
    g = generic(truth)
    assert len(g) == 20
    assert sum(len(c["documents"]) for c in g.values()) == 165
    assert sum(d["page_count"] for c in g.values() for d in c["documents"].values()) == 489
    assert sum(len(d["signatures"]["items"]) for c in g.values() for d in c["documents"].values()) == 323
    assert set(truth["cases"]) - set(g) == {"solom-rec", "stavby-fiser"}


def test_every_document_has_sha_label_and_sources(truth):
    src = set(truth["sources"])
    for ck, c in truth["cases"].items():
        for fn, d in c["documents"].items():
            assert len(d["sha256"]) == 64, (ck, fn)
            assert d["label_certainty"] in ("certain", "probable", "unmapped")
            assert (d["label"] is None) == (d["label_certainty"] == "unmapped"), (ck, fn)
            s = d["sources"]
            for key in ("label", "page_count", "signatures"):
                v = s.get(key)
                if v is None:
                    continue
                for x in ([v] if isinstance(v, str) else v):
                    assert x in src, (ck, fn, key, x)
            if d["label"]:
                assert d["label"] in truth["meta"]["taxonomy_labels"]
                assert d["label"] in d["accept"]


def test_generic_signature_boxes_are_normalized_and_inside_page(truth):
    for ck, c in generic(truth).items():
        for fn, d in c["documents"].items():
            for s in d["signatures"]["items"]:
                assert M.valid_bbox(s["bbox"]), (ck, fn, s)
                assert 1 <= s["page"] <= d["page_count"], (ck, fn, s)
                assert s["role"] in ("provider", "borrower", "buyer", "supplier", "guarantor", "insurer")


def test_label_mapping_spot_checks(truth):
    a = truth["cases"]["SYN-A01"]["documents"]
    assert a["01_VOP.pdf"]["label"] == "vop"                       # prefix 01 = VOP v sadě A
    assert a["00_Smlouva_o_uveru.pdf"]["label"] == "smlouva_o_uveru"
    c = truth["cases"]["SYN-C02"]["documents"]
    assert c["01_faktura.pdf"]["label"] == "faktura"               # prefix 01 = faktura v sadě C: prefix nestačí
    assert c["03_cerpani.pdf"]["label_certainty"] == "unmapped" and c["03_cerpani.pdf"]["label"] is None
    assert c["10_splatky.pdf"]["label_certainty"] == "unmapped"
    assert truth["cases"]["SYN-B01"]["documents"]["11_Potvrzeni_o_prevodu_vlastnictvi.pdf"]["label"] == "predavaci_protokol"
    assert truth["cases"]["SYN-B01"]["documents"]["14_Potvrzeni_o_uhrade.pdf"]["label"] == "uhrada_kupni_ceny"


def test_signature_truth_spot_checks(truth):
    d = truth["cases"]["SYN-A01"]["documents"]
    sigs = d["00_Smlouva_o_uveru.pdf"]["signatures"]["items"]
    assert len(sigs) == 5 and sorted(s["page"] for s in sigs) == [3, 3, 4, 4, 4]
    assert d["99_Kontrola_smlouvy.pdf"]["signatures"]["items"] == []
    assert d["99_Kontrola_smlouvy.pdf"]["signatures"]["status"] == "known"


def test_scan_quality_recorded(truth):
    d = truth["cases"]["SYN-C02"]["documents"]["02_predani.pdf"]
    assert d["quality"] == "low_dpi" and d["text_layer"] == "image_only"
    assert truth["cases"]["SYN-A01"]["documents"]["01_VOP.pdf"]["text_layer"] == "digital"


def test_originals_use_manual_review_and_are_not_mixed_with_generic(truth):
    o = {k: c for k, c in truth["cases"].items() if c["group"] == "original"}
    n = 0
    for ck, c in o.items():
        for fn, d in c["documents"].items():
            assert d["signatures"]["status"] == "reviewed" and d["signatures"]["granularity"] == "page"
            assert d["sources"]["signatures"] == "S_REVIEW"
            n += len(d["signatures"]["items"])
    assert n == 37
    assert o["solom-rec"]["documents"]["99_KK_systAPI.pdf"]["signatures"]["items"] == []
    assert o["solom-rec"]["documents"]["01_Form_VOP.pdf"]["signatures"]["items"][0]["page"] == 19


def test_scenarios_cover_all_six(truth):
    sc = truth["scenarios"]
    assert {v["number"] for v in sc.values()} == {1, 2, 3, 4, 5, 6}
    assert all(c["scenario"] == "happy_path" for c in generic(truth).values())


def test_yaml_and_json_are_identical():
    yaml = pytest.importorskip("yaml")
    with open(os.path.join(EVAL, "truth.yaml"), encoding="utf-8") as f:
        y = yaml.safe_load(f)
    with open(os.path.join(EVAL, "truth.json"), encoding="utf-8") as f:
        j = json.load(f)
    assert y == j


def test_labels_exist_in_current_taxonomy(truth):
    yaml = pytest.importorskip("yaml")
    tax = yaml.safe_load(open(os.path.join(EVAL, "..", "classify", "taxonomy.yaml"), encoding="utf-8"))
    for c in truth["cases"].values():
        for d in c["documents"].values():
            if d["label"]:
                assert d["label"] in tax["labels"], d["label"]
