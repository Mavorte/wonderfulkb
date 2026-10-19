#!/usr/bin/env python3
"""Evaluace end-to-end toku zpracování dokumentů pro validační agent (tři čtecí volání + seznam).

Vstup: mapping.json (případy a jejich dokumenty), truth.yaml (pravda) a zdroj dat = agent API:

    python3 evaluate_e2e.py --mapping ../dataset/mapping.json --base-url https://HOST/v1      # AGENT_API_KEY v prostředí
    python3 evaluate_e2e.py --mapping ... --local-handler                                       # core.handle nad AWS
    python3 evaluate_e2e.py --mapping ... --mock                                                # mock v procesu
    python3 evaluate_e2e.py --mapping ... --fixture                                             # demo, NE měření

Výstup: report v markdownu a JSON (`--out-dir`). Podpisy se vždy vyhodnocují zvlášť pro skupinu `generic`
a `original`, nikdy jako jedno číslo. Co nelze změřit, je v sekci „Co nelze změřit“.
Přihlašovací údaje se nevypisují a nejsou v reportu; výřezy (`crop_url`) se do reportu nedostávají.
"""
import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:  # funguje i s `python -I`
    sys.path.insert(0, HERE)

import e2e_metrics as M  # noqa: E402
from e2e_transport import HttpTransport, LocalTransport, MockServer  # noqa: E402

DEFAULT_MAPPING = os.path.join(HERE, "..", "dataset", "mapping.json")
DEFAULT_TRUTH = os.path.join(HERE, "truth.yaml")
DEFAULT_OUT = os.path.join(HERE, "reports")
READY = ("completed", "partial")
GROUPS = ("generic", "original")
SCENARIO_ALIASES = {
    "1": "happy_path", "happy": "happy_path", "happy_path": "happy_path", "happy path": "happy_path",
    "2": "chybi_dokument", "chybi_dokument": "chybi_dokument", "missing_document": "chybi_dokument",
    "3": "spatny_dokument", "spatny_dokument": "spatny_dokument", "wrong_document": "spatny_dokument",
    "4": "spatne_udaje", "spatne_udaje": "spatne_udaje", "wrong_data": "spatne_udaje",
    "5": "chybi_podpis", "chybi_podpis": "chybi_podpis", "missing_signature": "chybi_podpis",
    "6": "nevytezi_se", "nevytezi_se": "nevytezi_se", "unreadable": "nevytezi_se",
}


# ---- vstupy ----------------------------------------------------------------

def load_truth(path):
    """truth.yaml (PyYAML), jinak vedlejší truth.json se stejným obsahem."""
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        alt = os.path.splitext(path)[0] + ".json"
        with open(alt, encoding="utf-8") as f:
            return json.load(f)


def load_mapping(path):
    if not os.path.exists(path):
        raise SystemExit(f"Mapping {path} neexistuje (mapping.json vytváří session v-dataset; ukázka tvaru je "
                         f"{os.path.relpath(os.path.join(HERE, 'mapping_example.json'))}).")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list):
        raise SystemExit("mapping.json: očekávám seznam případů (nebo {\"cases\": [...]})")
    return cases


SCENARIOS_KNOWN = set(SCENARIO_ALIASES.values())


def normalize_scenario(s):
    if s is None:
        return None
    k = str(s).strip().lower().replace("-", "_")
    return SCENARIO_ALIASES.get(k, SCENARIO_ALIASES.get(k.split(":")[0].strip(), k))


class TruthIndex:
    """Přiřazení položek mappingu k pravdě: explicitně, podle SHA-256, podle ID v názvu, podle shody souborů."""

    CASE_RX = re.compile(r"SYN-[ABC]\d{2}", re.I)

    def __init__(self, truth):
        self.truth = truth
        self.cases = truth["cases"]
        self.by_sha = {}
        self.files = {}
        for ck, c in self.cases.items():
            self.files[ck] = {M.norm_name(fn): fn for fn in c["documents"]}
            for fn, d in c["documents"].items():
                if d.get("sha256"):
                    self.by_sha[d["sha256"]] = (ck, fn)

    def resolve_case(self, mcase):
        for k in ("truth_case", "source_case", "synthetic_id"):
            v = mcase.get(k)
            if v and v in self.cases:
                return v, k
        shas = Counter(self.by_sha[d["sha256"]][0] for d in mcase.get("documents", [])
                       if d.get("sha256") in self.by_sha)
        if shas:
            return shas.most_common(1)[0][0], "sha256"
        for k in ("case_id", "scenario", "title", "name", "label"):
            v = mcase.get(k)
            if isinstance(v, str):
                m = self.CASE_RX.search(v)
                if m and m.group(0).upper() in self.cases:
                    return m.group(0).upper(), k
                if v in self.cases:
                    return v, k
        names = {M.norm_name(os.path.basename(str(d.get("filename") or d.get("title") or "")))
                 for d in mcase.get("documents", [])}
        names.discard("")
        score = {ck: len(names & set(files)) for ck, files in self.files.items()}
        ranked = sorted(score.items(), key=lambda kv: -kv[1])
        if ranked and ranked[0][1] >= 2 and (len(ranked) < 2 or ranked[0][1] > ranked[1][1]):
            return ranked[0][0], "filenames"
        return None, None

    def resolve_doc(self, case_key, mdoc):
        if mdoc.get("sha256") in self.by_sha:
            ck, fn = self.by_sha[mdoc["sha256"]]
            if case_key in (None, ck):
                return ck, fn
        if case_key:
            name = M.norm_name(os.path.basename(str(mdoc.get("filename") or mdoc.get("title") or "")))
            fn = self.files[case_key].get(name)
            if fn:
                return case_key, fn
        return None, None


# ---- sběr volání ------------------------------------------------------------

def _paged_list(tr, case_id, calls):
    entries, token, results = {}, None, []
    for _ in range(50):
        res = tr.get(f"/cases/{case_id}/documents", {"limit": 100, "next_token": token})
        results.append(res)
        calls.append(("list", res))
        if res.status != 200 or not isinstance(res.body, dict):
            break
        for e in res.body.get("documents") or []:
            if isinstance(e, dict) and "document_id" in e:
                entries[e["document_id"]] = e
        token = res.body.get("next_token")
        if not token:
            break
    return entries, results


def collect_case(tr, mcase, opts):
    cid = mcase["case_id"]
    calls = []
    entries, list_results = _paged_list(tr, cid, calls)
    docs = []
    for md in mcase.get("documents", []):
        did = md["document_id"]
        rec = {"document_id": did, "mdoc": md, "list_entry": entries.get(did), "detail": None,
               "vectors": None, "signatures": None, "values": None}
        res = tr.get(f"/cases/{cid}/documents/{did}")
        calls.append(("detail", res))
        rec["detail"] = res
        if res.status == 200 or opts.get("call_all"):
            q = {"include_values": False}
            if opts["neighbors"]:
                q["similar_to_verified"] = opts["neighbors"]
            rec["vectors"] = tr.get(f"/cases/{cid}/documents/{did}/vectors", q)
            calls.append(("vectors", rec["vectors"]))
            rec["signatures"] = tr.get(f"/cases/{cid}/documents/{did}/signatures", {"include_vectors": False})
            calls.append(("signatures", rec["signatures"]))
        docs.append(rec)
        if opts.get("sleep"):
            time.sleep(opts["sleep"])
    return {"mcase": mcase, "entries": entries, "list_results": list_results, "docs": docs, "calls": calls}


def collect(tr, mapping, opts):
    out = []
    if opts.get("workers", 1) > 1:
        with ThreadPoolExecutor(opts["workers"]) as ex:
            out = list(ex.map(lambda mc: collect_case(tr, mc, opts), mapping))
    else:
        out = [collect_case(tr, mc, opts) for mc in mapping]
    # ukázka vektorových hodnot (rozměr, normalizace) na prvních dokumentech
    k = opts.get("sample_values", 0)
    for c in out:
        for rec in c["docs"]:
            if k <= 0:
                break
            if rec["detail"] is not None and rec["detail"].status == 200:
                res = tr.get(f"/cases/{c['mcase']['case_id']}/documents/{rec['document_id']}/vectors",
                             {"include_values": True})
                rec["values"] = res
                k -= 1
    return out


# ---- vyhodnocení jednoho dokumentu --------------------------------------------

def _pages_of(text):
    return text.split("\f") if text else []


def check_detail_shape(body):
    req = ("case_id", "document_id", "title", "label", "label_status", "description", "text", "confidence",
           "processing_status")
    errs = [f"chybí {k}" for k in req if k not in body]
    if isinstance(body.get("confidence"), (int, float)) and not 0 <= body["confidence"] <= 1:
        errs.append("confidence mimo 0 až 1")
    return errs


def check_vectors_shape(body):
    errs = [f"chybí {k}" for k in ("case_id", "document_id", "text_vectors", "image_vectors") if k not in body]
    for k in ("text_vectors", "image_vectors"):
        if k in body and not isinstance(body[k], list):
            errs.append(f"{k} není pole")
    return errs


def check_signatures_shape(body):
    errs = [f"chybí {k}" for k in ("case_id", "document_id", "signatures") if k not in body]
    if isinstance(body.get("signatures"), list):
        for s in body["signatures"]:
            for k in ("signature_id", "page", "detector"):
                if k not in s:
                    errs.append(f"podpis bez {k}")
                    break
    elif "signatures" in body:
        errs.append("signatures není pole")
    return errs


def eval_vectors(rec, detail, tdoc, known_status, taxonomy_ids, self_id, neighbors_n, truth_label):
    res = rec["vectors"]
    out = {"called": res is not None, "status": res.status if res else None}
    if res is None or res.status != 200 or not isinstance(res.body, dict):
        return out
    b = res.body
    out["shape_errors"] = check_vectors_shape(b)
    tv, iv = b.get("text_vectors") or [], b.get("image_vectors") or []
    pc = detail.get("page_count") if detail else None
    out["text_vectors"], out["image_vectors"] = len(tv), len(iv)
    out["exists"] = bool(tv or iv)
    dims = {v.get("dimension") for v in tv + iv}
    models = {(v.get("model"), v.get("model_version")) for v in tv + iv}
    out["dimension_ok"] = dims <= {1024} if (tv or iv) else None
    out["models"] = sorted(f"{m}:{v}" for m, v in models if m)
    if pc:
        pages = sorted(v.get("page") for v in iv)
        out["image_pages_ok"] = pages == list(range(1, pc + 1))
        out["image_pages_missing"] = sorted(set(range(1, pc + 1)) - set(pages))
        text = detail.get("text") or ""
        nonempty = {i + 1 for i, t in enumerate(_pages_of(text)) if t.strip()}
        ranges_ok = all(isinstance(v.get("page_from"), int) and isinstance(v.get("page_to"), int)
                        and 1 <= v["page_from"] <= v["page_to"] <= pc for v in tv)
        covered = set()
        for v in tv:
            if isinstance(v.get("page_from"), int) and isinstance(v.get("page_to"), int):
                covered |= set(range(v["page_from"], v["page_to"] + 1))
        out["text_ranges_ok"] = ranges_ok
        out["text_pages_covered"] = len(nonempty & covered)
        out["text_pages_with_text"] = len(nonempty)
        out["text_chunk_ids_unique"] = len({v.get("chunk_id") for v in tv}) == len(tv)
        out["text_ok"] = (bool(tv) == bool(nonempty)) and ranges_ok and nonempty <= covered if nonempty or tv else None
    nb = b.get("neighbors")
    out["neighbors_requested"] = bool(neighbors_n)
    if neighbors_n:
        out["neighbors_present"] = isinstance(nb, list)
        nb = nb if isinstance(nb, list) else []
        out["neighbors_n"] = len(nb)
        viol = []
        unknown = 0
        for n in nb:
            if n.get("document_id") == self_id:
                viol.append("sám sebe")
            if not n.get("label"):
                viol.append("bez štítku")
            elif taxonomy_ids and n["label"] not in taxonomy_ids:
                viol.append("štítek mimo taxonomii")
            s = n.get("score")
            if not isinstance(s, (int, float)) or not -1.0001 <= s <= 1.0001:
                viol.append("score mimo -1 až 1")
            st = known_status.get(n.get("document_id"))
            if st is None:
                unknown += 1
            elif st != "verified":
                viol.append("soused není verified")
        scores = [n.get("score") for n in nb if isinstance(n.get("score"), (int, float))]
        if scores != sorted(scores, reverse=True):
            viol.append("neseřazeno")
        if len(nb) > neighbors_n:
            viol.append("víc sousedů než N")
        out["neighbors_violations"] = viol
        out["neighbors_unverifiable"] = unknown
        if nb and truth_label:
            out["neighbor_top1_correct"] = nb[0].get("label") == truth_label
            votes = Counter(n.get("label") for n in nb)
            out["neighbor_majority_correct"] = votes.most_common(1)[0][0] == truth_label
    vals = rec.get("values")
    if vals is not None and vals.status == 200 and isinstance(vals.body, dict):
        import math
        checks = []
        for v in (vals.body.get("text_vectors") or []) + (vals.body.get("image_vectors") or []):
            x = v.get("values")
            if not isinstance(x, list):
                checks.append("values chybí")
                continue
            if len(x) != v.get("dimension"):
                checks.append("délka != dimension")
            if not all(isinstance(t, (int, float)) and math.isfinite(t) for t in x):
                checks.append("nečíselné nebo nekonečné")
            else:
                nrm = math.sqrt(sum(t * t for t in x))
                if not 0.9 <= nrm <= 1.1:
                    checks.append("norma mimo 0,9 až 1,1")
        out["values_sample"] = {"ok": not checks, "problems": sorted(set(checks))}
    return out


def eval_signatures(rec, tdoc, removed):
    res = rec["signatures"]
    out = {"called": res is not None, "status": res.status if res else None}
    if res is None or res.status != 200 or not isinstance(res.body, dict):
        return out
    b = res.body
    out["shape_errors"] = check_signatures_shape(b)
    found = [s for s in (b.get("signatures") or []) if isinstance(s, dict)]
    out["found"] = len(found)
    out["detectors"] = dict(Counter(s.get("detector") for s in found))
    out["has_crop_url"] = sum(1 for s in found if s.get("crop_url"))
    out["has_phash"] = sum(1 for s in found if s.get("phash"))
    out["bbox_valid"] = sum(1 for s in found if M.valid_bbox(s.get("bbox")))
    out["role_unknown"] = sum(1 for s in found if s.get("role") in (None, "unknown"))
    out["copy_suspected"] = sum(1 for s in found if (s.get("copy_suspicion") or {}).get("level") == "suspected")
    status = (tdoc or {}).get("signatures", {}).get("status", "unknown") if tdoc else "unknown"
    gran = (tdoc or {}).get("signatures", {}).get("granularity", "bbox") if tdoc else "bbox"
    out["truth_status"] = "unknown" if status == "unknown" else ("known" if status == "known" else f"reviewed_{gran}")
    if status == "unknown":
        return out
    items = tdoc["signatures"]["items"]
    exp, gone = M.apply_removed(items, removed)
    m = M.match_signatures(exp, found)
    if gone:   # varianta záměrně odebrala podpis: obchodní nález „podpis chybí“ se měří proti základní pravdě
        mb = M.match_signatures(items, found)
        out["base_missed"] = [{"page": items[i]["page"], "role": items[i].get("role")} for i in mb["missed"]]
    out["expected"] = len(exp)
    out["removed_in_variant"] = len(gone)
    out["matched"] = len(m["pairs"])
    out["covered"] = len(m["covered"])
    out["missed"] = [{"page": exp[i]["page"], "role": exp[i].get("role")} for i in m["missed"]]
    out["spurious"] = [{"page": found[i].get("page"), "detector": found[i].get("detector")} for i in m["spurious"]]
    out["duplicate_or_merged"] = len(m["duplicate_or_merged"])
    roles = Counter()
    copy_exp = Counter()
    for ti, fi, v in m["pairs"]:
        if v is None:   # párování jen podle strany a počtu: pořadí uvnitř strany je libovolné
            continue
        roles[M.role_match(exp[ti].get("role"), found[fi].get("role"))] += 1
        same = exp[ti].get("same_signer_in_other_docs")
        if same is not None:
            copy_exp[("same_signer" if same else "unique_signer",
                      (found[fi].get("copy_suspicion") or {}).get("level") or "chybí")] += 1
    out["roles"] = dict(roles)
    out["copy_by_signer"] = {f"{a}|{b_}": v for (a, b_), v in copy_exp.items()}
    out["exact_count"] = len(found) == len(exp)
    return out


def eval_doc(case_ctx, rec, tindex, taxonomy_ids, known_status, opts):
    mcase, mdoc = case_ctx["mcase"], rec["mdoc"]
    group = mdoc.get("group") or mcase.get("group") or (
        tindex.cases[case_ctx["truth_case"]]["group"] if case_ctx["truth_case"] else "other")
    tcase, tfile = tindex.resolve_doc(case_ctx["truth_case"], mdoc)
    tdoc = tindex.cases[tcase]["documents"][tfile] if tcase else None
    d = rec["detail"]
    body = d.body if d is not None and d.status == 200 and isinstance(d.body, dict) else None
    out = {"case_id": mcase["case_id"], "document_id": rec["document_id"],
           "filename": mdoc.get("filename") or (body or {}).get("title"), "group": group,
           "truth_case": tcase, "truth_file": tfile, "resolved": tdoc is not None,
           "kind": ((tdoc or {}).get("label") if group == "original" else (tdoc or {}).get("kind")),
           "quality": (tdoc or {}).get("quality"),
           "text_layer": (tdoc or {}).get("text_layer"),
           "detail_status": d.status if d is not None else None,
           "list_status": (rec["list_entry"] or {}).get("processing_status")}
    out["in_list"] = rec["list_entry"] is not None
    if d is not None and d.status == 409 and isinstance(d.body, dict):
        out["processing_status"] = d.body.get("processing_status")
    if body is None:
        out["available"] = False
        out["vectors"] = {"called": False}
        out["signatures"] = eval_signatures(rec, tdoc, (mdoc.get("variant") or {}).get("removed_signatures"))
        return out
    out["shape_errors"] = check_detail_shape(body)
    out["processing_status"] = body.get("processing_status")
    text = body.get("text") or ""
    out["text_len"] = len(text.strip())
    out["available"] = body.get("processing_status") in READY and bool(text.strip())
    out["pages_failed"] = body.get("pages_failed") or []
    pc = body.get("page_count")
    out["page_count"] = pc
    if tdoc:
        out["page_count_truth"] = tdoc["page_count"]
        out["page_count_ok"] = pc == tdoc["page_count"]
    tp = _pages_of(text)
    out["text_pages"] = len(tp)
    out["text_pages_match_page_count"] = (len(tp) == pc) if (pc and text) else None
    # štítek a jistota
    out["label"], out["label_status"], out["confidence"] = body.get("label"), body.get("label_status"), \
        body.get("confidence")
    if tdoc and tdoc.get("label") and tdoc.get("label_certainty") in ("certain", "probable"):
        out["label_truth"] = tdoc["label"]
        out["label_certainty"] = tdoc["label_certainty"]
        if body.get("label") is None:
            out["label_outcome"] = "missing"
        elif body["label"] in set(tdoc.get("accept") or [tdoc["label"]]):
            out["label_outcome"] = "correct"
        else:
            out["label_outcome"] = "wrong"
    elif tdoc and tdoc.get("label_certainty") == "unmapped":
        out["label_outcome"] = "unmapped"
    # pole z anotací v textu
    if tdoc and tdoc.get("fields"):
        tn = M.norm_text(text)
        hit = [M.field_found(f["value"], tn) for f in tdoc["fields"]]
        out["fields_total"], out["fields_found"] = len(hit), sum(hit)
    out["vectors"] = eval_vectors(rec, body, tdoc, known_status, taxonomy_ids, rec["document_id"],
                                  opts["neighbors"], out.get("label_truth"))
    out["signatures"] = eval_signatures(rec, tdoc, (mdoc.get("variant") or {}).get("removed_signatures"))
    return out


# ---- agregace -------------------------------------------------------------------

def agg_availability(docs):
    n = len(docs)
    ok = [d for d in docs if d["available"]]
    st = Counter(d.get("processing_status") or f"HTTP {d['detail_status']}" for d in docs)
    byq = defaultdict(lambda: [0, 0])
    for d in docs:
        q = d.get("quality") or "?"
        byq[q][1] += 1
        byq[q][0] += d["available"]
    with_pc = [d for d in docs if "page_count_ok" in d]
    tp = [d for d in docs if d.get("text_pages_match_page_count") is not None]
    ft = sum(d.get("fields_total", 0) for d in docs if d["available"])
    ff = sum(d.get("fields_found", 0) for d in docs if d["available"])
    fields_by = defaultdict(lambda: [0, 0])
    for d in docs:
        if d["available"] and d.get("fields_total"):
            k = d.get("text_layer") or "?"
            fields_by[k][0] += d["fields_found"]
            fields_by[k][1] += d["fields_total"]
    return {
        "documents": n, "available": M.ratio(len(ok), n), "status": dict(st),
        "by_quality": {q: M.ratio(a, b) for q, (a, b) in sorted(byq.items())},
        "partial": sum(1 for d in docs if d.get("processing_status") == "partial"),
        "page_count_matches_truth": M.ratio(sum(d["page_count_ok"] for d in with_pc), len(with_pc)),
        "text_pages_match_page_count": M.ratio(sum(d["text_pages_match_page_count"] for d in tp), len(tp)),
        "field_recall": M.ratio(ff, ft),
        "field_recall_by_text_layer": {k: M.ratio(a, b) for k, (a, b) in sorted(fields_by.items())},
        "shape_errors": sum(len(d.get("shape_errors") or []) for d in docs),
    }


def agg_labels(docs, taxonomy_ids):
    elig = [d for d in docs if d.get("label_outcome") in ("correct", "wrong", "missing")]
    c = Counter(d["label_outcome"] for d in elig)
    by = lambda key: {k: M.ratio(sum(1 for d in v if d["label_outcome"] == "correct"), len(v))  # noqa: E731
                      for k, v in sorted(_group(elig, key).items())}
    conf = Counter((d["label_truth"], d["label"]) for d in elig if d["label_outcome"] != "correct")
    unmapped = Counter(d.get("label") or "(bez štítku)" for d in docs if d.get("label_outcome") == "unmapped")
    cal_items = [(d["confidence"], d["label_outcome"] == "correct") for d in elig
                 if d.get("label_status") != "verified" and isinstance(d.get("confidence"), (int, float))]
    return {
        "eligible": len(elig), "accuracy": M.ratio(c["correct"], len(elig)),
        "missing_label": c["missing"], "wrong": c["wrong"],
        "by_certainty": by("label_certainty"), "by_quality": by("quality"), "by_truth_label": by("label_truth"),
        "top_confusions": [{"truth": a, "predicted": b, "n": n} for (a, b), n in conf.most_common(10)],
        "label_status": dict(Counter(d.get("label_status") or "null" for d in elig)),
        "confidence_null": sum(1 for d in elig if d.get("confidence") is None),
        "calibration": M.calibration(cal_items) if cal_items else None,
        "unmapped_predicted": dict(unmapped),
        "unmapped_documents": sum(unmapped.values()),
    }


def _group(items, key):
    out = defaultdict(list)
    for d in items:
        out[d.get(key) or "?"].append(d)
    return out


def agg_vectors(docs):
    v = [d["vectors"] for d in docs if d["vectors"].get("status") == 200]
    called = [d for d in docs if d["vectors"].get("called")]
    img = [x for x in v if "image_pages_ok" in x]
    txt = [x for x in v if x.get("text_ok") is not None]
    nbr = [x for x in v if x.get("neighbors_requested")]
    nb_nonempty = [x for x in nbr if x.get("neighbors_n")]
    return {
        "documents_called": len(called),
        "vectors_exist": M.ratio(sum(1 for x in v if x.get("exists")), len(called)),
        "image_pages_equal_page_count": M.ratio(sum(1 for x in img if x["image_pages_ok"]), len(img)),
        "text_vectors_ok": M.ratio(sum(1 for x in txt if x["text_ok"]), len(txt)),
        "dimension_1024": M.ratio(sum(1 for x in v if x.get("dimension_ok")), sum(1 for x in v if x.get("dimension_ok") is not None)),
        "models": dict(Counter(m for x in v for m in x.get("models", []))),
        "neighbors": {
            "requested": len(nbr), "returned_nonempty": len(nb_nonempty),
            "empty": len(nbr) - len(nb_nonempty),
            "violations": dict(Counter(p for x in nbr for p in x.get("neighbors_violations", []))),
            "unverifiable_neighbors": sum(x.get("neighbors_unverifiable", 0) for x in nbr),
            "top1_label_correct": M.ratio(sum(1 for x in nbr if x.get("neighbor_top1_correct")),
                                          sum(1 for x in nbr if "neighbor_top1_correct" in x)),
            "majority_label_correct": M.ratio(sum(1 for x in nbr if x.get("neighbor_majority_correct")),
                                              sum(1 for x in nbr if "neighbor_majority_correct" in x)),
        },
        "values_sample": {"checked": sum(1 for x in v if "values_sample" in x),
                          "problems": sorted({p for x in v for p in x.get("values_sample", {}).get("problems", [])})},
        "shape_errors": sum(len(x.get("shape_errors") or []) for x in v),
    }


def agg_signatures(docs):
    s_all = [d["signatures"] for d in docs if d["signatures"].get("status") == 200]
    known = [s for s in s_all if s.get("truth_status") not in ("unknown", None)]
    unknown = [s for s in s_all if s.get("truth_status") == "unknown"]
    exp = sum(s["expected"] for s in known)
    mat = sum(s["matched"] for s in known)
    cov = sum(s["covered"] for s in known)
    found_known = sum(s["found"] for s in known)
    spur = sum(len(s["spurious"]) for s in known)
    dup = sum(s["duplicate_or_merged"] for s in known)
    roles = Counter()
    for s in known:
        roles.update(s["roles"])
    rn = sum(roles.values())
    docs_zero = [s for s in known if s["expected"] == 0]
    docs_pos = [s for s in known if s["expected"] > 0]
    copy = Counter()
    for s in known:
        copy.update(s.get("copy_by_signer", {}))
    by_kind = defaultdict(lambda: [0, 0, 0])
    by_q = defaultdict(lambda: [0, 0])
    for d in docs:
        s = d["signatures"]
        if s.get("status") == 200 and s.get("truth_status") not in ("unknown", None):
            k = by_kind[d.get("kind") or "?"]
            k[0] += s["expected"]
            k[1] += s["matched"]
            k[2] += len(s["spurious"])
            q = by_q[d.get("quality") or "?"]
            q[0] += s["expected"]
            q[1] += s["matched"]
    missed = [{"case": d["case_id"], "file": d.get("filename"), **m} for d in docs
              if d["signatures"].get("status") == 200 for m in d["signatures"].get("missed", [])]
    spurious = [{"case": d["case_id"], "file": d.get("filename"), **m} for d in docs
                if d["signatures"].get("status") == 200 for m in d["signatures"].get("spurious", [])]
    return {
        "documents_called": sum(1 for d in docs if d["signatures"].get("called")),
        "documents_ok": len(s_all),
        "documents_with_known_truth": len(known), "documents_with_unknown_truth": len(unknown),
        "truth_kinds": dict(Counter(s["truth_status"] for s in known)),
        "expected": exp, "found_in_known_docs": found_known,
        "completeness_at_place": M.ratio(mat, exp),
        "completeness_covered": M.ratio(cov, exp),
        "false_findings": spur, "false_findings_share_of_found": M.ratio(spur, found_known),
        "duplicate_or_merged": dup,
        "docs_without_signatures_in_truth": {"n": len(docs_zero), "with_false_findings": sum(1 for s in docs_zero if s["found"] > 0)},
        "docs_with_signatures_in_truth": {"n": len(docs_pos), "with_missing": sum(1 for s in docs_pos if s["missed"]),
                                          "exact_count": sum(1 for s in docs_pos if s["exact_count"])},
        "roles": {"matched_pairs": rn, "exact": roles["exact"], "lenient": roles["lenient"],
                  "unknown": roles["unknown"], "wrong": roles["wrong"],
                  "accuracy_exact": M.ratio(roles["exact"], rn),
                  "accuracy_lenient": M.ratio(roles["exact"] + roles["lenient"], rn)},
        "by_kind": {k: {"expected": a, "matched": b, "false_findings": c} for k, (a, b, c) in sorted(by_kind.items())},
        "by_quality": {k: M.ratio(b, a) for k, (a, b) in sorted(by_q.items())},
        "copy_suspicion_by_signer": dict(copy),
        "found_without_truth": {"documents": len(unknown), "signatures": sum(s["found"] for s in unknown),
                                "per_document": [s["found"] for s in unknown]},
        "detectors": dict(sum((Counter(s.get("detectors", {})) for s in s_all), Counter())),
        "has_crop_url": M.ratio(sum(s.get("has_crop_url", 0) for s in s_all), sum(s.get("found", 0) for s in s_all)),
        "has_phash": M.ratio(sum(s.get("has_phash", 0) for s in s_all), sum(s.get("found", 0) for s in s_all)),
        "bbox_valid": M.ratio(sum(s.get("bbox_valid", 0) for s in s_all), sum(s.get("found", 0) for s in s_all)),
        "role_unknown_share": M.ratio(sum(s.get("role_unknown", 0) for s in s_all), sum(s.get("found", 0) for s in s_all)),
        "copy_suspected_total": sum(s.get("copy_suspected", 0) for s in s_all),
        "shape_errors": sum(len(s.get("shape_errors") or []) for s in s_all),
        "missed_examples": missed[:40], "spurious_examples": spurious[:40],
        "missed_total": len(missed), "spurious_total": len(spurious),
    }


def agg_latency(calls):
    out = {}
    byk = defaultdict(list)
    for k, r in calls:
        byk[k].append(r)
    for k, rs in byk.items():
        ms = [r.ms for r in rs]
        st = Counter("síť/časový limit" if r.status is None else str(r.status) for r in rs)
        err5 = sum(1 for r in rs if r.status is None or r.status >= 500)
        notready = sum(1 for r in rs if r.status == 409)
        client = sum(1 for r in rs if r.status is not None and 400 <= r.status < 500 and r.status != 409)
        out[k] = {"n": len(rs), "p50_ms": M.percentile(ms, 50), "p95_ms": M.percentile(ms, 95),
                  "max_ms": max(ms), "mean_ms": M.mean(ms), "status": dict(st),
                  "server_errors": err5, "not_ready_409": notready, "client_errors": client,
                  "error_rate": M.ratio(err5 + client, len(rs)),
                  "retried": sum(1 for r in rs if r.attempts > 1), "simulated": any(r.simulated for r in rs)}
    return out


# ---- scénáře -----------------------------------------------------------------------

def eval_scenarios(ctxs, doc_results, tindex):
    out = []
    by_case = defaultdict(list)
    for d in doc_results:
        by_case[d["case_id"]].append(d)
    for c in ctxs:
        mc, tk = c["mcase"], c["truth_case"]
        sc = normalize_scenario(mc.get("scenario"))
        if sc not in SCENARIOS_KNOWN:   # mapping má popisný text (např. „demolition-shears …“): scénář je z pravdy
            sc = tindex.cases[tk].get("scenario") if tk else None
        docs = by_case[mc["case_id"]]
        findings, notes = [], []
        removed_docs = {M.norm_name(os.path.basename(x)) for x in mc.get("removed_documents") or []}
        missing_docs = set()
        if tk:
            present = {M.norm_name(d["truth_file"]) for d in docs if d["truth_file"]}
            api_titles = {M.norm_name(os.path.basename(str(e.get("title") or ""))) for e in c["entries"].values()}
            for fn in tindex.cases[tk]["documents"]:
                nf = M.norm_name(fn)
                if nf not in present and nf not in api_titles:
                    missing_docs.add(nf)
                    findings.append({"type": "dokument_chybi", "file": fn})
        for d in docs:
            if not d["available"]:
                findings.append({"type": "dokument_nedostupny", "file": d.get("filename"),
                                 "status": d.get("processing_status") or d.get("detail_status")})
            s = d["signatures"]
            if s.get("status") == 200:
                for m in s.get("base_missed", s.get("missed", [])):
                    findings.append({"type": "podpis_chybi", "file": d.get("filename"), **m})
                for m in s.get("spurious", []):
                    findings.append({"type": "podpis_navic", "file": d.get("filename"), **m})
        res = {"case_id": mc["case_id"], "truth_case": tk, "scenario": sc, "scenario_in_mapping": mc.get("scenario"),
               "findings_total": len(findings),
               "findings_by_type": dict(Counter(f["type"] for f in findings)), "findings": findings[:25]}
        by_type = res["findings_by_type"]
        declared_sig = sum(len((x.get("variant") or {}).get("removed_signatures") or []) for x in mc.get("documents", []))
        if sc == "happy_path":
            res["expected_findings"] = 0
            res["verdict"] = "ok" if not findings else "nálezy_navzdory_happy_path"
        elif sc == "chybi_dokument":
            res["expected_findings"] = len(removed_docs)
            if not removed_docs:
                res["verdict"] = "nelze_určit_očekávání"
                notes.append("mapping neuvádí removed_documents")
            else:
                res["verdict"] = "ok" if missing_docs == removed_docs else (
                    f"nalezeno_{len(missing_docs & removed_docs)}_z_{len(removed_docs)}_a_{len(missing_docs - removed_docs)}_navíc")
        elif sc == "chybi_podpis":
            res["expected_findings"] = declared_sig
            got = by_type.get("podpis_chybi", 0)
            if not declared_sig:
                res["verdict"] = "nelze_určit_očekávání"
                notes.append("mapping neuvádí variant.removed_signatures")
            else:
                res["verdict"] = "ok" if got == declared_sig else f"nalezeno_{got}_z_{declared_sig}"
        elif sc == "nevytezi_se":
            res["verdict"] = "pozorováno"
            res["observed"] = {"nedostupné": sum(1 for d in docs if not d["available"]),
                               "partial": sum(1 for d in docs if d.get("processing_status") == "partial")}
        elif sc in ("spatny_dokument", "spatne_udaje"):
            res["verdict"] = "neměřitelné"
            notes.append(tindex.truth["scenarios"][sc].get("unmeasurable_reason", ""))
        else:
            res["verdict"] = "scénář_neznámý"
        res["notes"] = notes
        out.append(res)
    return out


# ---- hlavní vyhodnocení ----------------------------------------------------------------

def evaluate(data, tindex, opts, meta):
    taxonomy_ids = set(tindex.truth["meta"].get("taxonomy_labels") or [])
    ctxs = []
    for c in data:
        tk, how = tindex.resolve_case(c["mcase"])
        c["truth_case"], c["truth_how"] = tk, how
        ctxs.append(c)
    known_status = dict(opts.get("known_status_extra") or {})
    for c in ctxs:
        for did, e in c["entries"].items():
            known_status[did] = e.get("label_status")
    docs = []
    for c in ctxs:
        for rec in c["docs"]:
            docs.append(eval_doc(c, rec, tindex, taxonomy_ids, known_status, opts))
    calls = [x for c in ctxs for x in c["calls"]]
    per_group = {}
    for g in sorted({d["group"] for d in docs}):
        gd = [d for d in docs if d["group"] == g]
        per_group[g] = {
            "cases": len({d["case_id"] for d in gd}), "documents": len(gd),
            "availability": agg_availability(gd), "labels": agg_labels(gd, taxonomy_ids),
            "vectors": agg_vectors(gd), "signatures": agg_signatures(gd),
        }
    unresolved_cases = [{"case_id": c["mcase"]["case_id"], "scenario": c["mcase"].get("scenario")} for c in ctxs
                        if not c["truth_case"]]
    unresolved_docs = [{"case_id": d["case_id"], "file": d.get("filename")} for d in docs if not d["resolved"]]
    list_mismatch = []
    for c in ctxs:
        ids = {r["document_id"] for r in c["docs"]}
        extra = sorted(set(c["entries"]) - ids)
        missing = sorted(ids - set(c["entries"]))
        if extra or missing:
            list_mismatch.append({"case_id": c["mcase"]["case_id"], "in_api_not_in_mapping": len(extra),
                                  "in_mapping_not_in_api": len(missing)})
    return {
        "meta": meta, "per_group": per_group, "latency": agg_latency(calls),
        "scenarios": eval_scenarios(ctxs, docs, tindex),
        "unresolved": {"cases": unresolved_cases, "documents": unresolved_docs},
        "list_mismatch": list_mismatch,
        "documents": docs,
    }


def build_meta(args, tr, mapping, truth, ids_resolved):
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {"mode": tr.mode, "host": tr.host, "simulated": getattr(tr, "simulated", False)},
        "mapping": {"path": os.path.relpath(args.mapping) if args.mapping else None, "cases": len(mapping),
                    "documents": sum(len(c.get("documents", [])) for c in mapping)},
        "truth": {"path": os.path.relpath(args.truth), "generated_at": truth["meta"].get("generated_at"),
                  "zip_sha256": (truth["meta"].get("bundle") or {}).get("zip_sha256")},
        "options": {"neighbors": args.neighbors, "retries": args.retries, "timeout": args.timeout,
                    "workers": args.workers, "sample_values": args.sample_values},
    }


# ---- CLI ------------------------------------------------------------------------------------

def mapping_from_index(index, truth_index):
    """Mapping pro mock / lokální fixtury z jejich `/_mock/cases`.

    Berou se jen případy, které se podle shody souborů přiřadí k pravdě (referenční korpus mocku se nehodnotí).
    Vrací i `label_status` všech dokumentů indexu, aby šlo ověřit, že `neighbors` jsou opravdu ověřené.
    """
    out, known = [], {}
    for c in index.get("cases", []):
        docs = [{"document_id": d["document_id"], "filename": d["title"], "group": "original"}
                for d in c["documents"]]
        for d in c["documents"]:
            known[d["document_id"]] = "verified" if d.get("verified") else "predicted"
        mc = {"case_id": c["case_id"], "scenario": "unknown", "group": "original", "documents": docs}
        if truth_index.resolve_case(mc)[0]:
            out.append(mc)
    return out, known


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mapping", default=None, help=f"mapping.json (výchozí {os.path.relpath(DEFAULT_MAPPING)})")
    ap.add_argument("--truth", default=DEFAULT_TRUTH)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--base-url", help="URL API včetně /v1; klíč z prostředí (--api-key-env)")
    src.add_argument("--local-handler", action="store_true", help="core.handle z infra/validator-agent/api (AWS)")
    src.add_argument("--local-fixtures", action="store_true", help="totéž nad moto fixturami (bez AWS)")
    src.add_argument("--mock", action="store_true", help="mock z infra/validator-agent-mock spuštěný v procesu")
    src.add_argument("--fixture", action="store_true", help="demo: odpovědi vygenerované z pravdy s chybami (NE měření)")
    ap.add_argument("--api-key-env", default="AGENT_API_KEY", help="proměnná s klíčem (záloha: API_KEY)")
    ap.add_argument("--neighbors", type=int, default=3, help="similar_to_verified (0 = nevolat)")
    ap.add_argument("--sample-values", type=int, default=2, help="u kolika dokumentů ověřit hodnoty vektorů")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--retries", type=int, default=0, help="opakování při 5xx a chybách sítě")
    ap.add_argument("--workers", type=int, default=1, help="souběžné případy (latence jsou pak zatížené)")
    ap.add_argument("--sleep", type=float, default=0.0, help="pauza mezi dokumenty v sekundách")
    ap.add_argument("--auto-case", action="append", default=[], metavar="CASE_ID[=TRUTH_CASE]",
                    help="případ, který v mappingu není (např. pipeline-sample-solom-rec=solom-rec): dokumenty se "
                         "vezmou ze seznamu API (název souboru = title); lze opakovat")
    ap.add_argument("--groups", default="generic,original")
    ap.add_argument("--limit-cases", type=int, default=0)
    ap.add_argument("--call-all", action="store_true", help="volat vektory a podpisy i u nedostupných dokumentů")
    ap.add_argument("--out-dir", default=DEFAULT_OUT)
    ap.add_argument("--name", default=None)
    ap.add_argument("--quiet", action="store_true", help="nevypisovat report na stdout")
    ap.add_argument("--seed", type=int, default=7, help="jen --fixture")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    truth = load_truth(args.truth)
    tindex = TruthIndex(truth)
    cleanup = []
    mock_index = None
    known_extra = {}
    if args.base_url:
        key = os.environ.get(args.api_key_env) or os.environ.get("API_KEY")
        if not key:
            raise SystemExit(f"Chybí API klíč: nastav {args.api_key_env} v prostředí (hodnota se nevypisuje).")
        tr = HttpTransport(args.base_url, key, timeout=args.timeout, retries=args.retries)
    elif args.local_handler or args.local_fixtures:
        tr = LocalTransport(fixtures=args.local_fixtures, retries=args.retries)
        cleanup.append(tr.close)
        mock_index = tr.index
    elif args.mock:
        ms = MockServer()
        cleanup.append(ms.close)
        tr = ms.transport(timeout=args.timeout, retries=args.retries)
        r = tr.get("/_mock/cases")
        mock_index = r.body if r.status == 200 else None
    elif args.fixture:
        from fixture_api import FixtureTransport
        tr = FixtureTransport(truth, seed=args.seed)
        mock_index = None
    else:
        raise SystemExit("Zvol zdroj: --base-url, --local-handler, --local-fixtures, --mock nebo --fixture.")
    try:
        if args.mapping:
            mapping = load_mapping(args.mapping)
        elif args.fixture:
            mapping = tr.mapping()
        elif mock_index is not None:
            mapping, known_extra = mapping_from_index(mock_index, tindex)
        elif os.path.exists(DEFAULT_MAPPING):
            args.mapping = DEFAULT_MAPPING
            mapping = load_mapping(DEFAULT_MAPPING)
        else:
            raise SystemExit(f"Chybí mapping: {os.path.relpath(DEFAULT_MAPPING)} zatím neexistuje, použij --mapping.")
        for spec in args.auto_case:
            cid, _, tk = spec.partition("=")
            entries, _ = _paged_list(tr, cid, [])
            g = tindex.cases[tk]["group"] if tk in tindex.cases else None
            mapping.append({"case_id": cid, "source_case": tk or None, "scenario": "unknown", "group": g,
                            "documents": [{"document_id": e["document_id"], "filename": e.get("title"), "group": g}
                                          for e in entries.values()]})
        groups = set(args.groups.split(","))
        keep = []
        for mc in mapping:
            tk, _ = tindex.resolve_case(mc)
            g = mc.get("group") or (tindex.cases[tk]["group"] if tk else "other")
            if g in groups or "all" in groups:
                keep.append(mc)
        mapping = keep[:args.limit_cases] if args.limit_cases else keep
        opts = {"neighbors": args.neighbors, "workers": args.workers, "sleep": args.sleep,
                "call_all": args.call_all, "sample_values": args.sample_values,
                "known_status_extra": known_extra}
        data = collect(tr, mapping, opts)
        meta = build_meta(args, tr, mapping, truth, None)
        result = evaluate(data, tindex, opts, meta)
    finally:
        for fn in cleanup:
            fn()
    from e2e_report import render_markdown
    md = render_markdown(result, truth)
    os.makedirs(args.out_dir, exist_ok=True)
    name = args.name or f"e2e-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{tr.mode}"
    with open(os.path.join(args.out_dir, name + ".md"), "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(args.out_dir, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1, default=str)
    if not args.quiet:
        print(md)
    print(f"\nReport: {os.path.join(args.out_dir, name)}.md / .json", file=sys.stderr)
    return result


if __name__ == "__main__":
    main()
