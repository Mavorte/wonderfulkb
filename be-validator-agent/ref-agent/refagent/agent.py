"""Orchestrace: seznam dokumentů -> detail každého dokumentu -> pravidla -> (volitelně) jedno volání LLM -> report."""
import os
import re
from dataclasses import asdict

import yaml

from . import checks, llm
from .api import AgentApi, ApiError
from .model import CaseContext, Doc, Finding

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RULES = os.path.join(HERE, "..", "rules.yaml")

REC_APPROVE = "schválit"
REC_REVIEW = "ke kontrole člověkem"


def load_rules(path=DEFAULT_RULES):
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    rules = cfg.get("rules") or []
    ids = [r.get("id") for r in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("Pravidla mají duplicitní id")
    for r in rules:
        if r.get("type") not in checks.REGISTRY:
            raise ValueError(f"Pravidlo {r.get('id')}: neznámý typ {r.get('type')!r} (známé: {', '.join(sorted(checks.REGISTRY))})")
    return cfg


def fetch_documents(api, listed, agent_listing):
    """Sestaví Doc pro každý dokument ze seznamu; volání 1 se dělá vždy. 409 / chyba = dokument nečitelný, ne vyřazený."""
    meta = {d["document_id"]: d for d in agent_listing}
    docs = []
    for item in listed:
        did = item["document_id"]
        m = meta.get(did, {})
        d = Doc(document_id=did, filename=item.get("filename") or item.get("title") or "", title=m.get("title") or "",
                label=m.get("label"), label_status=m.get("label_status"), processing_status=m.get("processing_status"),
                page_count=m.get("page_count"))
        try:
            full = api.get_document(did)
            d.title = full.get("title") or d.title
            d.label, d.label_status = full.get("label"), full.get("label_status")
            d.confidence, d.description = full.get("confidence"), full.get("description")
            d.text, d.page_count = full.get("text") or "", full.get("page_count")
            d.processing_status = full.get("processing_status")
            d.pages_failed = full.get("pages_failed") or []
        except ApiError as e:
            d.error = str(e)
            if e.status == 409:
                d.processing_status = e.body.get("processing_status") or d.processing_status or "processing"
            elif not d.processing_status:
                d.processing_status = "unknown"
        docs.append(d)
    return docs


def run_checks(cfg, ctx):
    findings = []
    for rule in cfg["rules"]:
        findings.extend(checks.run_rule(rule, ctx))
    used = ctx.state.get("table_used")       # byla použita přílohová tabulka: hlášení „výčet nenalezen“ je zbytečné
    if used:
        findings = [f for f in findings if not (f.rule_id == used and f.title.startswith("Seznam požadovaných podkladů"))]
    for i, f in enumerate(findings, 1):
        f.id = f"F-{i}"
    return findings


def _norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def dealias(text, by_alias, quotes):
    """Model vidí dokumenty jako D1.. a citace jako Q1..; čtenáři reportu se vrací názvy a citace."""
    if not text:
        return text
    text = re.sub(r"\s*\((?:Q\d+(?:\s*[,–-]\s*Q?\d+)*)\)", "", text)
    text = re.sub(r"\bD\d+\b", lambda m: by_alias[m.group(0)].name if m.group(0) in by_alias else m.group(0), text)
    return re.sub(r"\bQ\d+\b", lambda m: f"„{quotes[m.group(0)]}“" if m.group(0) in quotes else m.group(0), text)


def apply_assessment(result, findings, docs):
    """Přenese výstup LLM do nálezů. Nezmění závažnost žádného nálezu, jen přidá vysvětlení a ověřené další nálezy."""
    by_id = {f.id: f for f in findings}
    by_alias = {result["alias"][d.document_id]: d for d in docs if d.document_id in result["alias"]}
    quotes = result.get("quotes", {})
    for e in result["explanations"]:
        e["text"] = dealias(e["text"], by_alias, quotes)
        f = by_id.get(e["finding_id"])
        if f is None:
            continue
        if overclaims(e["text"]):
            f.explanation = "(vysvětlení LLM vynecháno: tvrdí o podpisech víc, než data dovolují)"
            continue
        f.explanation = e["text"] + (f" [odhad LLM: {_ASSESS[e['assessment']]}]" if e.get("assessment") else "")
    added = []
    for c in result["extra_concerns"]:
        d = by_alias.get(c["document"])
        if d is None or not d.text:
            continue
        pos = _norm_ws(d.text).find(_norm_ws(c["quote"])) if c["quote"].strip() else -1
        if pos < 0:     # citace musí být v textu dokumentu, jinak další nález zahodíme
            continue
        page = None
        for i, pg in enumerate(d.text.split("\f"), 1):
            if _norm_ws(c["quote"]) in _norm_ws(pg):
                page = i
                break
        f = Finding("LLM", "review", c["title"], c["text"] + " (nález navrhl LLM, ověřena jen citace)",
                    [{"document_id": d.document_id, "document": d.name, "label": d.label, "page": page or c["page"], "quote": c["quote"][:160]}],
                    source="llm", uncertain=True)
        added.append(f)
    for f in added:
        f.id = f"F-{len(findings) + 1}"
        findings.append(f)
    return len(added)


OVERCLAIM = re.compile(r"podpis\w*\s+(?:\w+\s+){0,2}chybí|chybí\s+(?:\w+\s+){0,2}podpis|nepodepsan|bez\s+podpisu|padělan|falešn|nepravý|nepravá|nepravé|podvrh", re.I)
NEGATION = re.compile(r"neznamená|nelze\s+(?:tvrdit|říci|usuzovat)|není\s+důkaz|nechybí|nemusí", re.I)


def overclaims(text):
    """Vysvětlení LLM, které z nálezu detektoru dělá tvrzení o chybějícím nebo padělaném podpisu."""
    return bool(OVERCLAIM.search(text)) and not NEGATION.search(text)


_ASSESS = {"likely_real": "spíš skutečný problém", "likely_benign": "spíš neškodná odchylka", "unclear": "nejasné"}


def recommendation(findings):
    return REC_REVIEW if any(f.severity == "review" for f in findings) else REC_APPROVE


def validate_case(case_id, agent_http, listed, rules_cfg, backend=None, max_llm_calls=3, nonce=None, llm_tools=False):
    api = AgentApi(agent_http, case_id)
    from .api import list_all_documents
    try:
        agent_listing = list_all_documents(lambda tok: api.list_case_documents(next_token=tok))
    except ApiError:
        agent_listing = []      # štítky a stav si agent vezme z detailu každého dokumentu
    docs = fetch_documents(api, listed, agent_listing)
    rules_by_id = {r["id"]: r for r in rules_cfg["rules"]}
    ctx = CaseContext(case_id, docs, api, rules_cfg.get("settings"), rules_by_id)
    findings = run_checks(rules_cfg, ctx)
    llm_info = {"used": False, "calls": 0, "model": None, "error": None, "summary": None, "tokens": None, "extra_findings": 0}
    if backend is not None and any(f.severity == "review" for f in findings):
        runner = llm.ToolRunner(api, [d.document_id for d in docs])
        review = [f for f in findings if f.severity == "review"]      # ok a info nálezy se modelu neposílají
        res = llm.run_assessment(backend, case_id, review, docs, runner, max_llm_calls, nonce, allow_tools=llm_tools)
        by_alias = {res["alias"][d.document_id]: d for d in docs if d.document_id in res["alias"]}
        llm_info.update(used=True, calls=backend.calls, model=backend.model_id, error=res["error"], summary=dealias(res["summary"], by_alias, res["quotes"]),
                        tokens=dict(backend.usage), tool_calls=runner.calls)
        llm_info["extra_findings"] = apply_assessment(res, findings, docs)
    elif backend is not None:
        llm_info.update(model=backend.model_id)      # bez nálezů není co vysvětlovat: 0 volání
    return {
        "case_id": case_id,
        "recommendation": recommendation(findings),
        "documents": [{k: v for k, v in asdict(d).items() if k not in ("text",)} for d in docs],
        "findings": [asdict(f) for f in findings],
        "llm": llm_info,
        "stats": {"agent_api_calls": agent_http.calls, "vectors_calls": ctx.calls["vectors"], "signatures_calls": ctx.calls["signatures"]},
    }
