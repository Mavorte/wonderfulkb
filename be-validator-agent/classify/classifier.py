"""classify_document: jedno volání modelu vrací štítek, popis i jistotu; pravidla z hlavičky jen potvrzují štítek."""
import logging

from . import llm
from .prompt import parse_label_output
from .rules import decide, load_taxonomy, normalize, score_labels

log = logging.getLogger(__name__)

_state: dict = {}
RULE_DISAGREEMENT_CAP = 0.5  # model se s jistými pravidly rozešel: štítek zůstává modelu, jistota se omezí


def _limiter():
    if "limiter" not in _state:
        _state["limiter"] = llm.default_limiter()
    return _state["limiter"]


def _pages(page_count: int) -> str:
    n = int(page_count or 0)
    if n == 1:
        return "1 strana"
    return f"{n} strany" if 2 <= n <= 4 else f"{n} stran"


def classify_document_detailed(text: str, title: str | None = None, page_count: int = 0, *,
                               client=None, backend=None, model_id: str | None = None, sleep=None,
                               use_llm: bool = True, limiter=None) -> dict:
    """Jako classify_document, ale s klíči `method`, `rule_label`, `candidates`, `usage` a `error`.

    method: `llm` (štítek, popis a jistota z modelu), `rules` (jen pravidla: model vypnut nebo selhal),
    `none` (text bez textové vrstvy, nic se neurčuje). `title` (název souboru) se nepoužívá.
    `backend` je objekt s `complete(prompt)` (viz llm.ConverseBackend / MantleBackend), `client` mock Converse.
    """
    tax = load_taxonomy()
    out = {"label": None, "label_status": "predicted", "description": "", "confidence": None,
           "method": "none", "rule_label": None, "candidates": []}

    if len(normalize(text)) < tax["settings"]["min_text_chars"]:
        out["description"] = ("Dokument nemá použitelnou textovou vrstvu (sken); typ se určí až po "
                              "vizuálním přepisu.")
        return out

    rule_label, rule_conf, ranking = decide(score_labels(text, tax), tax)
    out.update(rule_label=rule_label, candidates=ranking[:3])

    def from_rules(reason: str):
        if rule_label:
            spec = tax["labels"][rule_label]
            out.update(label=rule_label, confidence=rule_conf, method="rules",
                       description=f"{spec['name']} ({_pages(page_count)}). {spec['description']}")
        else:
            out["description"] = reason
        return out

    if not use_llm:
        return from_rules("Typ dokumentu se z textu nepodařilo určit pravidly (model vypnut).")

    try:
        backend = backend or llm.make_backend(client, model_id)
        kwargs = {"limiter": limiter or _limiter()}
        if sleep:
            kwargs["sleep"] = sleep
        raw, usage = llm.classify_with_model(backend, tax, text, page_count, **kwargs)
    except Exception as exc:  # klasifikace nesmí shodit pipeline; chybu vrací v `error`
        log.error("Klasifikace modelem selhala: %s", exc)
        out["error"] = str(exc)
        return from_rules("Typ dokumentu se nepodařilo určit (chyba volání modelu).")

    res = parse_label_output(raw, tax)
    out.update(res, method="llm", usage=usage)
    if rule_label and res["label"] != rule_label and out["confidence"] is not None:
        out["confidence"] = min(out["confidence"], RULE_DISAGREEMENT_CAP)
    return out


def classify_document(text: str, title: str | None = None, page_count: int = 0, **kw) -> dict:
    """Rozhraní z be-validator-agent/docs/validator-agent-storage.md: {label, label_status, description, confidence}.

    Pro text, který nevznikl vizuálním LLM přepisem (ten vrací štítek ve stejném volání, viz prompt.py).
    """
    d = classify_document_detailed(text, title, page_count, **kw)
    return {k: d[k] for k in ("label", "label_status", "description", "confidence")}
