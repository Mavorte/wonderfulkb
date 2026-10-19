"""Datový model případu: dokumenty, nálezy, lazy načítání vektorů a podpisů přes agent API."""
from dataclasses import dataclass, field

from .api import ApiError

READY = ("completed", "partial")


@dataclass
class Doc:
    document_id: str
    filename: str = ""
    title: str = ""
    label: str = None
    label_status: str = None
    confidence: float = None
    description: str = None
    text: str = ""
    page_count: int = None
    processing_status: str = None
    pages_failed: list = field(default_factory=list)
    error: str = None          # proč detail nejde číst (409, 5xx, ...)

    @property
    def ready(self):
        return self.processing_status in READY and not self.error

    @property
    def name(self):
        return self.title or self.filename or self.document_id


@dataclass
class Finding:
    rule_id: str
    severity: str              # review = ke kontrole člověkem | info = poznámka | ok = ověřeno bez nálezu
    title: str
    detail: str = ""
    evidence: list = field(default_factory=list)
    id: str = ""
    explanation: str = None    # srozumitelné vysvětlení od LLM (jen text, nemění závažnost)
    source: str = "rule"       # rule | llm
    uncertain: bool = False    # nález stojí na absenci / heuristice, ne na doložené neshodě


def evidence(doc, page=None, quote=None, **extra):
    ev = {"document_id": doc.document_id, "document": doc.name, "label": doc.label}
    if page is not None:
        ev["page"] = page
    if quote:
        ev["quote"] = quote
    ev.update({k: v for k, v in extra.items() if v is not None})
    return ev


class CaseContext:
    """Vše, co kontroly potřebují: dokumenty, nastavení a lazy volání 2 a 3 (s cache a počítadly)."""

    def __init__(self, case_id, docs, api, settings=None, rules_by_id=None):
        self.case_id, self.docs, self.api = case_id, docs, api
        self.settings = settings or {}
        self.rules_by_id = rules_by_id or {}
        self._vec, self._sig = {}, {}
        self.state = {}      # sdílený stav mezi pravidly (např. která varianta seznamu podkladů platila)
        self.calls = {"vectors": 0, "signatures": 0}

    @property
    def ready_docs(self):
        return [d for d in self.docs if d.ready]

    def with_label(self, labels, ready_only=True):
        pool = self.ready_docs if ready_only else self.docs
        return [d for d in pool if d.label in labels]

    def vectors(self, doc, n):
        """(`ok`, odpověď) nebo (`error`, text chyby). Chyba není totéž co prázdná odpověď."""
        if doc.document_id not in self._vec:
            self.calls["vectors"] += 1
            self._vec[doc.document_id] = _guard(lambda: self.api.get_document_vectors(doc.document_id, similar_to_verified=n))
        return self._vec[doc.document_id]

    def signatures(self, doc):
        if doc.document_id not in self._sig:
            self.calls["signatures"] += 1
            self._sig[doc.document_id] = _guard(lambda: self.api.get_document_signatures(doc.document_id, match_client=True))
        return self._sig[doc.document_id]


def _guard(fn):
    try:
        return "ok", fn()
    except ApiError as e:
        return "error", str(e)
