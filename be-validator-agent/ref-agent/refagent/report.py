"""Text a JSON reportu. Všechny řetězce procházejí redakcí tajemství (API klíče z prostředí se nikdy nevypíšou)."""
import json

LIMITS = [
    "Pravost podpisů se neověřuje; nález detektoru (Textract) je jen přítomnost, role a podezření na kopii. Prázdný nález není důkaz, že podpis chybí.",
    "Vyčtení hodnot z textu je heuristika nad textovým výpisem; „nevyčteno“ není nesoulad a shoda nepotvrzuje pravost dokumentu.",
    "Doporučení určuje kód podle ukázkových pravidel (rules.yaml). LLM jen vysvětluje; agent nic nezamítá, jen schvaluje nebo posílá člověku.",
]
SEV = {"review": "KE KONTROLE", "info": "poznámka", "ok": "ověřeno"}


def redact(obj, secrets):
    secrets = [s for s in secrets if s and len(s) >= 4]
    if isinstance(obj, str):
        for s in secrets:
            obj = obj.replace(s, "***")
        return obj
    if isinstance(obj, list):
        return [redact(x, secrets) for x in obj]
    if isinstance(obj, dict):
        return {k: redact(v, secrets) for k, v in obj.items()}
    return obj


def strip_signed_query(rep):
    """Předpodepsané adresy výřezů nesou dočasné přihlašovací údaje v query; ve výstupu zůstane jen cesta."""
    for f in rep.get("findings", []):
        for e in f.get("evidence", []):
            for k in ("crop_url", "preview_url"):
                u = e.get(k)
                if u and "?" in u:
                    e[k] = u.split("?", 1)[0] + "?…"
                    e[k + "_note"] = "podepsaná adresa vynechána; získáte ji novým voláním get_document_signatures (platí 300 s), nebo --full-crop-urls"
    return rep


def _ev_line(e):
    head = e.get("document") or e.get("document_id") or "?"
    if e.get("document_id") and e.get("document"):
        head += f" [{e['document_id'][:8]}…]"
    page = f", s. {e['page']}" if e.get("page") else ""
    extra = []
    if e.get("signature_id"):
        extra.append(f"{e['signature_id']}, role {e.get('role') or '—'}")
    if e.get("detection_score") is not None:
        extra.append(f"skóre detektoru {e['detection_score']} (orientační)")
    if e.get("crop_url"):
        extra.append(f"výřez: {e['crop_url']} (platí 300 s)")
    if e.get("preview_url"):
        extra.append(f"náhled (zkreslený): {e['preview_url']} (platí 300 s)")
    if e.get("reveal_path"):
        extra.append(f"čitelný výřez: GET {e['reveal_path']} (s API klíčem, zapisuje se do auditu)")
    if e.get("note"):
        extra.append(e["note"])
    q = f" „{e['quote']}“" if e.get("quote") else ""
    return f"{head}{page}:{q}" + (f" ({'; '.join(extra)})" if extra else "")


def render_text(rep):
    L = []
    rec = rep["recommendation"]
    review = [f for f in rep["findings"] if f["severity"] == "review"]
    L += [f"VALIDACE PŘÍPADU {rep['case_id']}", "=" * 60,
          f"Doporučení: {rec.upper()}" + (f"  ({len(review)} nálezů ke kontrole)" if review else "  (žádný nález ke kontrole)"), ""]
    llm = rep["llm"]
    if llm.get("summary"):
        L += ["Shrnutí (LLM, jen vysvětlení): " + llm["summary"], ""]
    L.append(f"Dokumenty ({len(rep['documents'])}):")
    for d in rep["documents"]:
        conf = "—" if d.get("confidence") is None else f"{d['confidence']:.2f}"
        L.append(f"  - {d.get('title') or d.get('filename')} [{d['document_id'][:8]}…] typ: {d.get('label') or 'neurčen'}"
                 f" ({d.get('label_status') or '—'}), jistota typu: {conf}, stav: {d.get('processing_status')}, stran: {d.get('page_count') or '?'}")
    for title, sev in (("Nálezy ke kontrole člověkem", "review"), ("Poznámky", "info"), ("Ověřeno bez nálezu", "ok")):
        items = [f for f in rep["findings"] if f["severity"] == sev]
        if not items:
            continue
        L += ["", f"{title} ({len(items)}):"]
        for f in items:
            L.append(f"  [{f['id']}] {f['rule_id']}: {f['title']}")
            if f.get("detail"):
                L.append(f"      {f['detail']}")
            if f.get("explanation"):
                L.append(f"      Vysvětlení (LLM): {f['explanation']}")
            if f["severity"] == "review":
                for e in f.get("evidence", []):
                    L.append(f"      • {_ev_line(e)}")
    L += ["", "Omezení:"] + [f"  - {x}" for x in LIMITS]
    st = rep["stats"]
    mode = f"LLM {llm['model']}, volání {llm['calls']}" if llm["used"] else ("LLM nebylo potřeba (žádný nález ke kontrole)" if llm.get("model") else "bez LLM (--no-llm)")
    L += ["", f"Běh: {mode}; volání agent API {st['agent_api_calls']} (vektory {st['vectors_calls']}, podpisy {st['signatures_calls']})"]
    if llm.get("error"):
        L.append(f"Pozor: vysvětlení od LLM chybí ({llm['error']}); nálezy z pravidel platí.")
    return "\n".join(L)


def render_json(rep):
    return json.dumps(rep, ensure_ascii=False, indent=2)
