"""Fixturové API pro testy a ukázku reportu: odpovědi se vygenerují z pravdy a vloží se do nich chyby.

Není to měření. Slouží k tomu, aby šlo bez AWS ověřit, že evaluace chyby zachytí, a ukázat celý report.
Deterministické pro dané `seed`. Latence jsou simulované (`Result.simulated = True`).
"""
import hashlib
import random
import re

from e2e_transport import Result, Transport

IMAGE_ONLY_TYPES = {"image_only", "mixed"}


def _id(case, fn):
    return "d-" + hashlib.sha256(f"{case}/{fn}".encode()).hexdigest()[:12]


class FixtureTransport(Transport):
    mode = "fixture"
    host = None
    simulated = True

    def __init__(self, truth, seed=7, label_error=0.06, ocr_error=0.15, sig_miss=0.07, sig_miss_scan=0.25,
                 spurious=0.05, server_error=0.01, verified_every=7, merge=0.08, role_error=0.15,
                 vec_miss=0.03):
        super().__init__(retries=0)
        self.truth = truth
        self.rng = random.Random(seed)
        self.p = dict(label_error=label_error, ocr_error=ocr_error, sig_miss=sig_miss,
                      sig_miss_scan=sig_miss_scan, spurious=spurious, server_error=server_error,
                      merge=merge, role_error=role_error, vec_miss=vec_miss)
        self.labels = sorted(truth["meta"]["taxonomy_labels"])
        self.docs = {}      # (case, doc_id) -> dict
        self._build(verified_every)

    # ---- stavba dat ----
    def _build(self, verified_every):
        rng = self.rng
        n = 0
        for ck, c in self.truth["cases"].items():
            for fn, d in c["documents"].items():
                n += 1
                did = _id(ck, fn)
                scan = d["text_layer"] in IMAGE_ONLY_TYPES
                status = "completed"
                if d["quality"] in ("fax", "faded") and rng.random() < 0.25:
                    status = "partial"
                if c["group"] == "original" and fn.startswith("11_Podklady") and ck == "solom-rec":
                    status = "processing"
                pc = d["page_count"]
                failed = [pc] if status == "partial" and pc > 1 else []
                if status == "partial" and pc == 1:
                    status = "completed"
                verified = (n % verified_every == 0)
                tl = d.get("label")
                if tl is None:
                    label = "jine"
                    correct = None
                elif rng.random() < self.p["label_error"] * (2.5 if scan else 1):
                    label = rng.choice([x for x in self.labels if x not in set(d.get("accept") or [tl])])
                    correct = False
                else:
                    label = rng.choice(d.get("accept") or [tl]) if rng.random() < 0.15 else tl
                    correct = True
                if verified and tl:
                    label, conf, lstatus = tl, 1.0, "verified"
                else:
                    lstatus = "predicted"
                    conf = round(rng.uniform(0.8, 0.99), 2) if correct is not False else round(rng.uniform(0.55, 0.9), 2)
                    if c["group"] == "original" and rng.random() < 0.2:
                        conf = None
                text = self._make_text(d, pc, failed, scan)
                self.docs[(ck, did)] = dict(
                    case=ck, doc_id=did, file=fn, truth=d, status=status, page_count=pc, pages_failed=failed,
                    label=label, label_status=lstatus, confidence=conf, text=text, scan=scan,
                    verified=verified and bool(tl))

    def _make_text(self, d, pc, failed, scan):
        rng = self.rng
        pages = [f"Strana {i + 1} dokumentu typu {d['kind']}." for i in range(pc)]
        vals = []
        for f in d.get("fields") or []:
            v = f["value"]
            if scan and rng.random() < self.p["ocr_error"]:
                v = v[:-2] + "??" if len(v) > 4 else "?"
            vals.append(v)
        for i, v in enumerate(vals):
            pages[i % pc] += " " + v + "."
        for p in failed:
            pages[p - 1] = ""
        return "\f".join(pages)

    # ---- mapping pro demo ----
    def mapping(self):
        out = []
        for ck, c in self.truth["cases"].items():
            docs = [{"document_id": dd["doc_id"], "filename": dd["file"], "group": c["group"]}
                    for (k, _), dd in self.docs.items() if k == ck]
            out.append({"case_id": ck, "source_case": ck, "scenario": c["scenario"], "group": c["group"],
                        "documents": docs})
        return out

    # ---- obsluha požadavků ----
    def _ms(self):
        return round(self.rng.lognormvariate(4.2, 0.5), 1)

    def _once(self, path, query):
        rng = self.rng
        ms = self._ms()
        if rng.random() < self.p["server_error"]:
            return Result(502, {"error": "Interní chyba (simulace)"}, ms, simulated=True)
        m = re.match(r"^/cases/([^/]+)/documents(?:/([^/]+)(?:/(vectors|signatures))?)?$", path)
        if not m:
            return Result(404, {"error": "Neznámá cesta"}, ms, simulated=True)
        case, did, sub = m.groups()
        if did is None:
            rows = [dd for (k, _), dd in sorted(self.docs.items(), key=lambda kv: kv[0][1]) if k == case]
            if not rows:
                return Result(404, {"error": "Case neexistuje"}, ms, simulated=True)
            return Result(200, {"case_id": case, "next_token": None, "documents": [
                {"document_id": r["doc_id"], "title": r["file"], "label": r["label"],
                 "label_status": r["label_status"], "processing_status": r["status"],
                 "page_count": r["page_count"] if r["status"] in ("completed", "partial") else None}
                for r in rows]}, ms, simulated=True)
        dd = self.docs.get((case, did))
        if not dd:
            return Result(404, {"error": "Dokument neexistuje"}, ms, simulated=True)
        ready = dd["status"] in ("completed", "partial")
        if sub is None:
            if not ready:
                return Result(409, {"error": "OCR ještě nedoběhlo", "processing_status": dd["status"]}, ms, simulated=True)
            body = {"case_id": case, "document_id": did, "title": dd["file"], "label": dd["label"],
                    "label_status": dd["label_status"], "description": f"Fixture: {dd['truth']['kind']}",
                    "text": dd["text"], "confidence": dd["confidence"], "page_count": dd["page_count"],
                    "processing_status": dd["status"]}
            if dd["status"] == "partial":
                body["pages_failed"] = dd["pages_failed"]
            return Result(200, body, ms, simulated=True)
        if sub == "vectors":
            return Result(200, self._vectors(dd, query, ready), ms, simulated=True)
        return Result(200, self._signatures(dd, ready), ms, simulated=True)

    def _vectors(self, dd, query, ready):
        rng = self.rng
        body = {"case_id": dd["case"], "document_id": dd["doc_id"], "text_vectors": [], "image_vectors": []}
        if ready:
            pc = dd["page_count"]
            i = 0
            for a in range(1, pc + 1, 2):
                b = min(a + 1, pc)
                if not dd["text"].split("\f")[a - 1].strip() and a == b:
                    continue
                body["text_vectors"].append({"chunk_id": f"c{i}", "page_from": a, "page_to": b,
                                             "model": "amazon.titan-embed-text-v2:0", "model_version": "v2",
                                             "dimension": 1024})
                i += 1
            for p in range(1, pc + 1):
                if rng.random() < self.p["vec_miss"]:
                    continue  # chybějící strana
                body["image_vectors"].append({"page": p, "model": "amazon.titan-embed-image-v1",
                                              "model_version": "v1", "dimension": 1024})
            if str(query.get("include_values")) == "true":
                for v in body["text_vectors"] + body["image_vectors"]:
                    x = [rng.gauss(0, 1) for _ in range(1024)]
                    nrm = sum(t * t for t in x) ** 0.5
                    v["values"] = [t / nrm for t in x]
        n = int(query.get("similar_to_verified") or 0)
        if n:
            pool = [o for o in self.docs.values() if o["verified"] and o["doc_id"] != dd["doc_id"]]
            true_label = dd["truth"].get("label")
            same = [o for o in pool if o["label"] == true_label]
            other = [o for o in pool if o["label"] != true_label]
            rng.shuffle(same)
            rng.shuffle(other)
            picks = (same[:n] + other)[:n] if ready else []
            sc = sorted((round(rng.uniform(0.55, 0.95), 4) for _ in picks), reverse=True)
            body["neighbors"] = [{"document_id": o["doc_id"], "label": o["label"], "score": s}
                                 for o, s in zip(picks, sc)]
        return body

    def _signatures(self, dd, ready):
        rng = self.rng
        body = {"case_id": dd["case"], "document_id": dd["doc_id"], "signatures": []}
        if not ready:
            return body
        t = dd["truth"]
        sigs = []
        st = t["signatures"]
        items = st["items"] if st["status"] != "unknown" else None
        miss = self.p["sig_miss_scan"] if dd["scan"] else self.p["sig_miss"]
        if items is None:
            pc = dd["page_count"]
            for k in range(rng.choice([0, 1, 2, 2, 3])):
                x0 = rng.uniform(0.08, 0.5)
                sigs.append((pc, [x0, 0.6, x0 + 0.2, 0.66], rng.choice(["borrower", "provider", "unknown"]), None))
        else:
            prev = None
            k_on_page = {}
            for s in items:
                if rng.random() < miss:
                    continue
                base = s.get("bbox") or [0.1 + 0.25 * k_on_page.get(s["page"], 0), 0.6,
                                         0.3 + 0.25 * k_on_page.get(s["page"], 0), 0.66]
                k_on_page[s["page"]] = k_on_page.get(s["page"], 0) + 1
                bb = [max(0, min(1, v + rng.uniform(-0.01, 0.01))) for v in base]
                if prev and prev[0] == s["page"] and rng.random() < self.p["merge"] and prev[1][2] < bb[0] + 0.3:
                    # sloučený box přes dva sousední podpisy
                    sigs[-1] = (s["page"], [sigs[-1][1][0], min(sigs[-1][1][1], bb[1]), bb[2], max(sigs[-1][1][3], bb[3])],
                                sigs[-1][2], sigs[-1][3])
                else:
                    role = s["role"] if rng.random() >= self.p["role_error"] else rng.choice(["borrower", "provider", "unknown"])
                    sigs.append((s["page"], bb, role, s))
                prev = (s["page"], bb)
            if rng.random() < self.p["spurious"] * (3 if dd["scan"] else 1):
                sigs.append((rng.randint(1, dd["page_count"]), [0.7, 0.05, 0.9, 0.1], "unknown", None))
        for i, (page, bb, role, src) in enumerate(sigs, 1):
            same = (src or {}).get("same_signer_in_other_docs")
            level = "suspected" if same and rng.random() < 0.5 else "none"
            body["signatures"].append({
                "signature_id": f"sig_{i:02d}", "page": page, "bbox": [round(v, 4) for v in bb],
                "detector": rng.choice(["textract", "textract", "page_images"]),
                "detection_score": round(rng.uniform(12, 66), 1), "role": role, "role_source": "nearest_text",
                "role_evidence": "fixture", "crop_url": "https://example.invalid/crop.png",
                "phash": hashlib.sha256(f"{dd['doc_id']}{i}".encode()).hexdigest()[:16],
                "copy_suspicion": {"level": level, "matches": []}})
        return body
