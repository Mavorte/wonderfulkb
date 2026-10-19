"""Taxonomie a levné klasifikační pravidla nad hlavičkou a textem dokumentu."""
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import yaml

TAXONOMY_PATH = Path(__file__).with_name("taxonomy.yaml")
OTHER_LABEL = "jine"


@lru_cache(maxsize=1)
def load_taxonomy(path: str | None = None) -> dict:
    """Načte taxonomy.yaml a předkompiluje regulární výrazy pravidel."""
    with open(path or TAXONOMY_PATH, encoding="utf-8") as f:
        tax = yaml.safe_load(f)
    for label, spec in tax["labels"].items():
        spec["compiled"] = [
            (r["zone"], re.compile(r["re"]), float(r["w"])) for r in spec.get("rules", [])
        ]
    return tax


def normalize(text: str) -> str:
    """Malá písmena, bez diakritiky, bílé znaky (i \\f mezi stranami) sloučené do mezery."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", text).strip()


def score_labels(text: str, taxonomy: dict | None = None) -> dict[str, float]:
    """Skóre každého štítku: součet vah pravidel, která v dané zóně textu sedí (každé nejvýš jednou)."""
    tax = taxonomy or load_taxonomy()
    st = tax["settings"]
    norm = normalize(text)
    zones = {
        "title": norm[: st["title_chars"]],
        "head": norm[: st["head_chars"]],
        "any": norm,
    }
    scores = {}
    for label, spec in tax["labels"].items():
        total = sum(w for zone, rx, w in spec["compiled"] if rx.search(zones[zone]))
        if total:
            scores[label] = total
    return scores


def decide(scores: dict[str, float], taxonomy: dict | None = None):
    """Vrátí (label, confidence, ranking), nebo (None, None, ranking) při nízké shodě.

    Jistota z pravidel je heuristická (není kalibrovaná): roste se skóre a s náskokem před druhým štítkem.
    """
    st = (taxonomy or load_taxonomy())["settings"]
    ranking = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if not ranking:
        return None, None, ranking
    best, s1 = ranking[0]
    s2 = ranking[1][1] if len(ranking) > 1 else 0.0
    if s1 < st["accept_score"] or s1 - s2 < st["accept_margin"]:
        return None, None, ranking
    confidence = min(0.92, 0.60 + 0.01 * s1 + 0.01 * (s1 - s2))
    return best, round(confidence, 2), ranking
