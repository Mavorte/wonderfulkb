"""Kdy je duplicita relevantní: politika podle štítku (`duplicate_policy` v classify/taxonomy.yaml) a prahová hodnota
šablony (`settings.duplicate_template_threshold`, přepsatelná `DEDUP_TEMPLATE_THRESHOLD`).

Duplicitu pro agenta Wonderful (pravidlo „stejný doklad použit ve dvou financováních“) označuje `duplicate_relevant`.
API se balí jako Lambda jen z adresáře `api/`, proto čte snapshot `api/duplicate_policy.json`, který z taxonomie
vyrobí `python -m dedup.policy --write ../api/duplicate_policy.json`; test hlídá, že odpovídá taxonomii.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

TAXONOMY = Path(__file__).resolve().parent.parent / "classify" / "taxonomy.yaml"
DEFAULT_POLICY = "flag"  # neznámý štítek, chybějící štítek i `jine`
POLICIES = ("flag", "ignore")
DEFAULT_THRESHOLD = 3

_cache: dict | None = None


def load_taxonomy(path=None) -> dict:
    global _cache
    if path is None and _cache is not None:
        return _cache
    import yaml
    with open(path or TAXONOMY, encoding="utf-8") as handle:
        tax = yaml.safe_load(handle)
    if path is None:
        _cache = tax
    return tax


def policies(taxonomy: dict | None = None) -> dict[str, str]:
    tax = taxonomy or load_taxonomy()
    out = {}
    for label, spec in tax["labels"].items():
        value = spec.get("duplicate_policy", DEFAULT_POLICY)
        if value not in POLICIES:
            raise ValueError(f"{label}: duplicate_policy musí být flag nebo ignore, ne {value!r}")
        out[label] = value
    return out


def template_threshold(taxonomy: dict | None = None) -> int:
    env = os.environ.get("DEDUP_TEMPLATE_THRESHOLD")
    if env:
        return int(env)
    tax = taxonomy or load_taxonomy()
    return int(tax.get("settings", {}).get("duplicate_template_threshold", DEFAULT_THRESHOLD))


def policy_for(label: str | None, taxonomy: dict | None = None) -> str:
    return policies(taxonomy).get(label or "", DEFAULT_POLICY)


def evaluate(own_case_id: str, own_label: str | None, matches, *, taxonomy: dict | None = None) -> dict:
    """`matches` = výstup `lookup(sha256)` (smí obsahovat i vlastní případ). Vrací
    `{"duplicate_of": [{case_id, document_id, label}], "duplicate_relevant": bool}`.

    Relevantní jen když: existuje jiný případ se stejným obsahem, politika štítku dokumentu je `flag` a obsah
    neleží ve `template_threshold` a více různých případech (vlastní případ se počítá)."""
    others = [m for m in matches if m["case_id"] != own_case_id]
    cases = {m["case_id"] for m in matches} | {own_case_id}
    relevant = (bool(others) and policy_for(own_label, taxonomy) == "flag"
                and len(cases) < template_threshold(taxonomy))
    return {"duplicate_of": [{"case_id": m["case_id"], "document_id": m["document_id"], "label": m.get("label")}
                             for m in others], "duplicate_relevant": relevant}


def snapshot(taxonomy: dict | None = None) -> dict:
    tax = taxonomy or load_taxonomy()
    return {"default": DEFAULT_POLICY,
            "template_threshold": int(tax.get("settings", {}).get("duplicate_template_threshold", DEFAULT_THRESHOLD)),
            "policies": dict(sorted(policies(taxonomy).items()))}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vypíše nebo zapíše snapshot politiky duplicit z taxonomy.yaml.")
    parser.add_argument("--write", metavar="SOUBOR", help="zapíše JSON (např. ../api/duplicate_policy.json)")
    args = parser.parse_args(argv)
    text = json.dumps(snapshot(), indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    if args.write:
        Path(args.write).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
