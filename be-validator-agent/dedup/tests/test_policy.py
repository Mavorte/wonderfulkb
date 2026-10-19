import json
from pathlib import Path

import pytest

from dedup import policy

VA = Path(__file__).resolve().parents[2]


def match(case, doc="d", label=None):
    return {"case_id": case, "document_id": doc, "label": label}


def test_every_label_has_an_explicit_policy_and_only_vop_is_ignored():
    tax = policy.load_taxonomy()
    for label, spec in tax["labels"].items():
        assert spec.get("duplicate_policy") in ("flag", "ignore"), label
    assert {k for k, v in policy.policies().items() if v == "ignore"} == {"vop"}
    assert policy.policy_for("jine") == "flag" and policy.policy_for(None) == "flag" and policy.policy_for("nezname") == "flag"
    assert policy.template_threshold() == 3


def test_classify_still_loads_taxonomy_with_new_keys():
    import classify.rules as rules
    tax = rules.load_taxonomy()
    assert tax["settings"]["duplicate_template_threshold"] == 3 and tax["labels"]["vop"]["duplicate_policy"] == "ignore"


def test_same_content_in_two_cases_individual_document_is_relevant():
    result = policy.evaluate("c1", "faktura", [match("c1", "d1", "faktura"), match("c2", "d2", "faktura")])
    assert result == {"duplicate_of": [{"case_id": "c2", "document_id": "d2", "label": "faktura"}], "duplicate_relevant": True}


def test_template_vop_in_four_cases_is_not_relevant_but_listed():
    matches = [match(f"c{n}", f"d{n}", "vop") for n in range(4)]
    result = policy.evaluate("c0", "vop", matches)
    assert len(result["duplicate_of"]) == 3 and result["duplicate_relevant"] is False


def test_vop_in_two_cases_is_ignored_by_policy_not_by_threshold():
    assert policy.evaluate("c1", "vop", [match("c1"), match("c2")])["duplicate_relevant"] is False


def test_threshold_counts_distinct_cases_including_own_even_if_unregistered():
    assert policy.evaluate("c1", "faktura", [match("c2")])["duplicate_relevant"] is True          # c1 ještě není v indexu
    assert policy.evaluate("c1", "faktura", [match("c2"), match("c3")])["duplicate_relevant"] is False  # 3 případy = šablona
    assert policy.evaluate("c1", "faktura", [match("c2", "d2"), match("c2", "d3")])["duplicate_relevant"] is True  # 2 případy


def test_nothing_elsewhere_is_not_relevant():
    assert policy.evaluate("c1", "faktura", []) == {"duplicate_of": [], "duplicate_relevant": False}
    assert policy.evaluate("c1", "faktura", [match("c1")]) == {"duplicate_of": [], "duplicate_relevant": False}


def test_threshold_override_from_environment(monkeypatch):
    monkeypatch.setenv("DEDUP_TEMPLATE_THRESHOLD", "5")
    matches = [match(f"c{n}") for n in range(2, 5)]
    assert policy.evaluate("c1", "faktura", matches)["duplicate_relevant"] is True
    monkeypatch.setenv("DEDUP_TEMPLATE_THRESHOLD", "2")
    assert policy.evaluate("c1", "faktura", matches[:1])["duplicate_relevant"] is False


def test_invalid_policy_value_is_rejected():
    tax = {"labels": {"x": {"duplicate_policy": "maybe"}}}
    with pytest.raises(ValueError):
        policy.policies(tax)


def test_api_snapshot_matches_taxonomy():
    """api/duplicate_policy.json se balí do Lambdy; po změně taxonomie ho obnov:
    python -I -m dedup.policy --write api/duplicate_policy.json (v adresáři infra/validator-agent)."""
    snapshot = json.loads((VA / "api" / "duplicate_policy.json").read_text(encoding="utf-8"))
    assert snapshot == policy.snapshot()


def test_api_logic_agrees_with_library_for_all_labels_and_counts(monkeypatch):
    """API má vlastní kopii vyhodnocení (Lambda se balí bez dedup/); obě musí dát totéž."""
    import sys
    sys.path.insert(0, str(VA / "api"))
    import core

    class Repo:
        def __init__(self, matches):
            self.matches = matches

        def document_sha256(self, case, doc):
            return "a" * 64

        def hash_matches(self, sha):
            return self.matches

    for label in list(policy.policies()) + [None, "neznamy"]:
        for others in range(0, 5):
            matches = [match("own", "d0", label)] + [match(f"o{n}", f"d{n}", label) for n in range(others)]
            api = core.Api.__new__(core.Api)
            api.cfg = core.Config({})
            api.repo = Repo(matches)
            assert api._duplicates("own", "d0", label) == policy.evaluate("own", label, matches), (label, others)
