"""Deterministické kontroly (typy pravidel z rules.yaml). Bez LLM, bez náhody.

Každá kontrola vrací seznam Finding. Pravidla jsou rozhodnutí o tom, co poslat člověku; kontrola nikdy nic nezamítá.
Zásady viz hlavička rules.yaml: chybějící hodnota není nesoulad, prázdný nález podpisů není důkaz absence podpisu.
"""
import re
from collections import Counter
from decimal import Decimal

from .extract import page_of, quote_at, run_extractors
from .model import Finding, evidence

REGISTRY = {}


def check(name):
    def deco(fn):
        REGISTRY[name] = fn
        return fn
    return deco


def run_rule(rule, ctx):
    fn = REGISTRY.get(rule["type"])
    if fn is None:
        raise ValueError(f"Neznámý typ pravidla {rule['type']!r} ({rule.get('id')})")
    out = fn(rule, ctx)
    for f in out:
        f.rule_id = rule["id"]
    return out


def _q(ctx):
    return int(ctx.settings.get("quote_chars", 160))


# --------------------------------------------------------------------------- zpracování dokumentů

@check("documents_ready")
def documents_ready(rule, ctx):
    out = []
    if not ctx.docs:
        return [Finding("", "review", "Případ nemá žádné dokumenty", "Seznam dokumentů je prázdný, nelze nic posoudit.")]
    for d in ctx.docs:
        if not d.ready:
            why = d.error or f"stav zpracování: {d.processing_status}"
            out.append(Finding("", "review", f"Dokument není zpracovaný: {d.name}",
                               f"Text zatím není k dispozici ({why}). Dokument se neposuzoval, počkejte na dokončení OCR nebo ho zkontrolujte ručně.",
                               [evidence(d)], uncertain=True))
        elif d.processing_status == "partial":
            out.append(Finding("", "review", f"Dokument je přečtený jen částečně: {d.name}",
                               f"Nepodařilo se přečíst strany {', '.join(map(str, d.pages_failed)) or '?'} z {d.page_count}. "
                               "Z chybějícího textu na těchto stranách nelze usuzovat, že tam informace (např. podpis, číslo) není; "
                               "kontroly nad tímto dokumentem jsou neúplné.",
                               [evidence(d)], uncertain=True))
    if not out:
        out.append(Finding("", "ok", "Všechny dokumenty jsou zpracované", f"{len(ctx.docs)} dokumentů ve stavu completed."))
    return out


# --------------------------------------------------------------------------- úplnost podkladů

def _contract_items(text, rule):
    """Položky a) až h) za větou o podkladech. Zkouší všechny výskyty věty, bere první, který má položky."""
    rx = re.compile(rule["item_regex"], re.I)
    for m in re.finditer(rule["section_start"], text, re.I | re.S):
        items, cur, skipped = [], None, 0
        for line in text[m.end():].split("\n"):
            im = rx.match(line)
            if im:
                cur = {"letter": im.group(1), "text": im.group(2).strip()}
                items.append(cur)
            elif not items:
                skipped += 1
                if skipped > 4 and line.strip():
                    break
            elif not line.strip() or "\f" in line:
                break           # položky tvoří souvislý blok, prázdný řádek ho ukončuje
            else:
                cur["text"] += " " + line.strip()
        if items:
            for it in items:
                pos = text.find(it["text"][:30], m.end())
                it["page"] = page_of(text, pos if pos >= 0 else m.end())
            return items
    return None


def _tag(it):
    return f"{it['letter']}) " if it.get("letter") else ""


def _table_items(text, rule):
    """Varianta bez výčtu a) až h): řádky přílohové tabulky smlouvy, které odpovídají table_items."""
    out = []
    for spec in rule["table_items"]:
        m = re.search(spec["match"], text, re.I | re.M)
        if m:
            out.append({"letter": "", "text": re.sub(r"\s+", " ", m.group(0)).strip(), "page": page_of(text, m.start()), "spec": spec})
    return out


@check("required_documents")
def required_documents(rule, ctx):
    if rule.get("only_if_missing") and ctx.state.get(rule["only_if_missing"]) != "list_not_found":
        return []
    contracts = ctx.with_label([rule["contract_label"]])
    if not contracts:
        return [Finding("", "review", "Nelze určit požadované podklady",
                        f"V sadě není (zpracovaná) smlouva o úvěru (štítek {rule['contract_label']}), ze které se čte seznam podkladů.",
                        uncertain=True)]
    contract = sorted(contracts, key=lambda d: (d.label_status != "verified", d.document_id))[0]
    items = _table_items(contract.text, rule) if rule.get("table_items") else _contract_items(contract.text, rule)
    if not items and not rule.get("only_if_missing"):
        ctx.state[rule["id"]] = "list_not_found"
    if not items and rule.get("only_if_missing"):
        return []
    if rule.get("only_if_missing"):
        ctx.state["table_used"] = rule["only_if_missing"]
    if not items:
        return [Finding("", "review", "Seznam požadovaných podkladů se ve smlouvě nepodařilo najít",
                        "Pravidlo čte položky a) až h) za větou o podkladech před čerpáním úvěru; v textu smlouvy ji nenašlo "
                        "(jiná formulace, nebo je strana mezi nečitelnými). Úplnost zkontrolujte ručně.",
                        [evidence(contract)], uncertain=True)]
    out, satisfied = [], []
    unlabeled = sum(1 for d in ctx.docs if d.label is None)
    for it in items:
        spec = it.get("spec") or next((s for s in rule["items"] if re.search(s["match"], it["text"], re.I)), None)
        ev = [evidence(contract, it["page"], (it["text"] if it.get("spec") else f'{it["letter"]}) {it["text"]}')[:_q(ctx)])]
        if spec is None:
            out.append(Finding("", "review", f"Položku {_tag(it)}smlouvy nelze automaticky přiřadit k typu dokumentu",
                               "Pravidlo pro tuto položku nezná odpovídající typ dokumentu; zkontrolujte ručně, zda je podklad v sadě.",
                               ev, uncertain=True))
            continue
        have = ctx.with_label(spec["labels"], ready_only=False)
        if have:
            satisfied.append((it, spec, have))
        else:
            out.append(Finding("", "review", f"Podklad {_tag(it)}nenalezen v sadě: {spec['name']}",
                               f"Smlouva ho vyžaduje, ale mezi {len(ctx.docs)} dokumenty případu není žádný se štítkem "
                               f"{' / '.join(spec['labels'])}. Může být nenahraný, nebo součástí jiného souboru; ověřte u klienta."
                               + (f" Pozor: {unlabeled} dokumentů ještě nemá typ (zpracování neskončilo), podklad může být mezi nimi." if unlabeled else ""),
                               ev, uncertain=True))
    if satisfied:
        names = "; ".join(f'{_tag(it)}{spec["name"]} → {have[0].name}'
                          + (" (štítek jen odhadnutý)" if have[0].label_status != "verified" else "")
                          for it, spec, have in satisfied)
        out.append(Finding("", "ok", f"Pokryté podklady: {len(satisfied)} z {len(items)}", names))
    return out


# --------------------------------------------------------------------------- shoda polí

def _doc_values(doc, rule, ctx):
    return run_extractors(doc.text, rule["extractors"], rule.get("value_type", "id"), _q(ctx))


def _reference(rule, ctx, rules_values):
    """Referenční hodnota: první štítek v pořadí, který má dokument s právě jednou hodnotou."""
    for label in rule.get("reference_labels", []):
        for d in sorted(ctx.with_label([label]), key=lambda d: (d.label_status != "verified", d.document_id)):
            vals = {v["value"] for v in rules_values.get(d.document_id, [])}
            if len(vals) == 1:
                return d, next(iter(vals))
    return None, None


@check("field_consistency")
def field_consistency(rule, ctx):
    only, skip = rule.get("only_labels"), set(rule.get("skip_labels", []))
    vt = rule.get("value_type", "id")
    docs = [d for d in ctx.ready_docs if d.label not in skip and (not only or d.label in only or d.label in rule.get("reference_labels", []))]
    values = {d.document_id: _doc_values(d, rule, ctx) for d in docs}
    ref_doc, ref_val = _reference(rule, ctx, values)
    out = []
    if ref_doc is None:
        # Bez referenčního dokumentu: stačí, aby se hodnoty mezi dokumenty lišily.
        allv = {v["value"] for vs in values.values() for v in vs}
        if len(allv) > 1:
            ev = [evidence(d, v["page"], v["quote"]) for d in docs for v in values[d.document_id]]
            out.append(Finding("", "review", f"{rule['title']}: v dokumentech jsou různé hodnoty",
                               f"Nalezeno {len(allv)} různých hodnot ({', '.join(sorted(allv))}) a žádný dokument nemá jednoznačnou referenční hodnotu. "
                               "Zjistěte, která platí.", ev))
        elif allv:
            out.append(Finding("", "ok", rule["title"], f"Hodnota {next(iter(allv))} (bez referenčního dokumentu)."))
        else:
            out.append(Finding("", "info", f"{rule['title']}: hodnotu se nepodařilo vyčíst", "V žádném dokumentu se hodnotu nepodařilo z textu najít."))
        return out
    agree, nodata = [], []
    for d in docs:
        vs = values[d.document_id]
        if not vs:
            nodata.append(d)
            continue
        distinct = {v["value"] for v in vs}
        bad = [v for v in vs if v["value"] != ref_val]
        if bad:
            ev = [evidence(ref_doc, **_first(values[ref_doc.document_id]))] if d is not ref_doc else []
            ev += [evidence(d, v["page"], v["quote"]) for v in vs]
            what = "uvnitř dokumentu se hodnoty liší" if d is ref_doc or len(distinct) > 1 and ref_val in distinct else "hodnota se liší od reference"
            out.append(Finding("", "review", f"{rule['title']}: nesoulad v {d.name}",
                               f"Referenční hodnota {_show(ref_val, vt)} ({ref_doc.name}); v {d.name} {what}: "
                               f"{', '.join(_show(x, vt) for x in sorted(distinct - {ref_val}) or sorted(distinct))}. "
                               "Může jít o překlep, jinou smlouvu, nebo chybu vyčtení; rozhodne člověk.", ev))
        else:
            agree.append(d)
    if agree:
        out.append(Finding("", "ok", f"{rule['title']}: shoda (dokumentů: {len(agree)})",
                           f"{_show(ref_val, vt)} ({', '.join(d.name for d in agree)})."))
    if nodata:
        out.append(Finding("", "info", f"{rule['title']}: hodnota nevyčtena (dokumentů: {len(nodata)})",
                           ", ".join(d.name for d in nodata) + ". Nevyčtená hodnota není nesoulad (formulář může být prázdný, nebo má jiné rozložení textu)."))
    return out


def _first(vs):
    v = vs[0]
    return {"page": v["page"], "quote": v["quote"]}


def _show(v, vt):
    return f"{v} CZK" if vt == "amount" else v


@check("vat_check")
def vat_check(rule, ctx):
    price_rule = ctx.rules_by_id.get(rule["price_rule"])
    if not price_rule:
        raise ValueError(f"{rule['id']}: neznámé price_rule {rule['price_rule']}")
    refs = [d for lab in rule["reference_labels"] for d in ctx.with_label([lab])]
    base = None
    for d in refs:
        vs = run_extractors(d.text, price_rule["extractors"], "amount", _q(ctx))
        if vs:
            base, base_doc = Decimal(vs[0]["value"]), d
            break
    out = []
    if base is None:
        return [Finding("", "info", f"{rule['title']}: základ ceny nenalezen", "Ve smlouvě se nepodařilo vyčíst kupní cenu bez DPH, DPH se nepočítalo.")]
    for d in ctx.ready_docs:
        for v in run_extractors(d.text, rule["extractors"], "amount", _q(ctx)):
            expected = (base * Decimal(str(rule["rate"]))).quantize(Decimal("0.01"))
            if abs(Decimal(v["value"]) - expected) > Decimal(str(rule["tolerance"])):
                out.append(Finding("", "review", f"{rule['title']}: nesedí v {d.name}",
                                   f"DPH {v['value']} CZK, ale {rule['rate']*100:.0f} % z ceny {base} CZK ({base_doc.name}) je {expected} CZK.",
                                   [evidence(d, v["page"], v["quote"])]))
            else:
                out.append(Finding("", "ok", f"{rule['title']}: sedí v {d.name}", f"DPH {v['value']} CZK = {rule['rate']*100:.0f} % z {base} CZK."))
    return out


# --------------------------------------------------------------------------- podpisy

# Toto je jediné místo, které mluví o podpisech. Nesmí tvrdit, že podpis chybí, nebo že je pravý / nepravý.
SIG_NOT_PROOF = ("Nález detektoru není důkaz: Textract nachází jen asi 92 % generických a asi 59 % rukopisných podpisů, "
                 "takže prázdný nález neznamená, že podpis chybí. Zkontrolujte stranu očima.")


@check("signatures_expected")
def signatures_expected(rule, ctx):
    exp = rule["expected_roles"]
    out = []
    for d in ctx.ready_docs:
        roles = exp.get(d.label)
        if not roles:
            continue
        status, data = ctx.signatures(d)
        last_page = d.page_count or None
        if status == "error":
            out.append(Finding("", "review", f"Podpisy nešlo načíst: {d.name}",
                               f"Volání podpisů selhalo ({data}). Chyba není nález „bez podpisů“; dokument se musí zkontrolovat ručně.",
                               [evidence(d, last_page)], uncertain=True))
            continue
        sigs = data.get("signatures", [])
        got = {s.get("role") for s in sigs if s.get("role") not in (None, "unknown")}
        issues = []
        ev = []
        if not sigs:
            issues.append(f"Detektor v dokumentu nenašel žádný podpis (očekávané role: {', '.join(roles)}). {SIG_NOT_PROOF}")
            ev.append(evidence(d, last_page, "(podpisová část dokumentu)"))
        else:
            missing = [r for r in roles if r not in got]
            for s in sigs:
                ev.append(evidence(d, s.get("page"), f"popisek podpisu: {s['role_evidence']}" if s.get("role_evidence") else None, signature_id=s.get("signature_id"), role=s.get("role"),
                                   detection_score=s.get("detection_score"), crop_url=s.get("crop_url")))
            if any(s.get("role") in (None, "unknown") for s in sigs):
                issues.append("U některého nalezeného podpisu se nepodařilo určit roli (nejbližší text nestačil); roli neodhadujeme, ověřte ji.")
            if missing:
                issues.append(f"Detektor nenašel podpis s rolí {', '.join(missing)} (nalezeno: {', '.join(sorted(got)) or 'žádná jasná role'}). {SIG_NOT_PROOF}")
        susp = [s for s in sigs if (s.get("copy_suspicion") or {}).get("level") == "suspected"] if rule.get("flag_copy_suspicion") else []
        if susp:
            issues.append("Podezření na kopii: " + ", ".join(s["signature_id"] for s in susp) +
                          " je téměř shodný s podpisem v jiném dokumentu (může být vložený obrázek). Říká jen podobnost výřezu, nic o pravosti.")
            for s in susp:
                for m in s["copy_suspicion"].get("matches", [])[:2]:
                    other = next((x for x in ctx.docs if x.document_id == m.get("document_id")), None)
                    ev.append({"document_id": m.get("document_id"), "document": other.name if other else None,
                               "note": f"shodný výřez {m.get('signature_id')} s {s['signature_id']}"})
        if d.processing_status == "partial" and d.pages_failed:
            issues.append(f"Strany {', '.join(map(str, d.pages_failed))} nebyly přečtené, podpis mohl být tam.")
        if issues:
            out.append(Finding("", "review", f"Podpisy ke kontrole: {d.name}", " ".join(issues), ev, uncertain=True))
        else:
            out.append(Finding("", "ok", f"Podpisy nalezeny: {d.name}", f"Role {', '.join(sorted(got))} (jen nález detektoru, pravost se neověřuje)."))
    return out


# --------------------------------------------------------------------------- štítek typu dokumentu

@check("label_check")
def label_check(rule, ctx):
    thr = float(ctx.settings.get("low_label_confidence", 0.7))
    n = int(ctx.settings.get("neighbors", 3))
    out = []
    for d in ctx.ready_docs:
        ev = [evidence(d, 1, d.description[:_q(ctx)] if d.description else None)]
        if d.label is None:
            out.append(Finding("", "review", f"Dokument nemá typ: {d.name}", "Dokument ještě není klasifikovaný, typ nelze určit.", ev, uncertain=True))
            continue
        if d.label_status == "verified":
            continue
        reasons = []
        if d.confidence is None:
            reasons.append("jistota klasifikace není k dispozici (není to ani nula, ani vysoká jistota)")
        elif d.confidence < thr:
            reasons.append(f"jistota klasifikace {d.confidence:.2f} je pod {thr}")
        if rule.get("check_neighbors", True):
            status, data = ctx.vectors(d, n)
            nb = data.get("neighbors", []) if status == "ok" else []
            if status == "error":
                reasons.append(f"srovnání se sousedy nešlo načíst ({data})")
            elif nb:
                top = Counter(x.get("label") for x in nb).most_common(1)[0][0]
                if top != d.label:
                    reasons.append(f"nejbližší ověřené dokumenty mají štítek {top}, ne {d.label} (podobnost obsahu, ne důkaz chyby)")
            else:
                reasons.append("bez srovnání se sousedy (vektory ještě nejsou, nebo není ověřený soused)")
        if reasons and not all(r.startswith("bez srovnání") for r in reasons):
            out.append(Finding("", "review", f"Typ dokumentu je nejistý: {d.name}",
                               f"Štítek {d.label} je jen strojový odhad (predicted); " + "; ".join(reasons) + ".", ev, uncertain=True))
        else:
            out.append(Finding("", "info", f"Typ dokumentu odhadnut: {d.name}",
                               f"{d.label} (predicted, jistota {'—' if d.confidence is None else f'{d.confidence:.2f}'})" + ("; " + "; ".join(reasons) if reasons else "")))
    return out
