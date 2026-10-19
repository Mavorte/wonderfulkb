"""KROK 1: změří úplnost maskování na PDF z fetch.py. Nic nezapisuje do AWS, vše jen do lokální složky.

    python -I measure.py DATA_DIR OUT_DIR --scenario zones|findings --zones v1|v2

Scénáře nálezů:
- `zones`:    žádný nález detektoru, jen konzervativní zóny z popisků (nejhorší případ: detektor nenašel nic)
- `findings`: nálezy z existujícího analysis/<doc>/signatures.json (fetch.py), kde existují; jinak jen zóny
- `local`:    `findings` + lokální zálohy modulu podpisů (vložené obrázky, inkoust nad popiskem, vektorové tahy)
- `pipeline`: výchozí řetěz pipeline: Textract (volá se, cache v --cache) + obrázky + inkoust nad popiskem; `pipeline_vec`
              přidá vektorové tahy

Pro každé PDF: oblasti → `redact_pdf` → `verify_redacted` → `changed_outside`. Pro každý pravdivý podpis skupiny A
(truth.json, bbox z anotace balíku): pokrytí boxu (a) černou maskou, (b) maskou nebo zónou, (c) pixelová kontrola,
kolik tmavého inkoustu v boxu zbylo po redakci (vykreslení bez textové vrstvy, černé výplně se nepočítají jako zbytek).
Pro skupinu B (pravda jen počty podpisů na straně) uloží dvojice vykreslených stran pro ruční prohlídku.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pymupdf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))          # privacy/ (signature_privacy)
sys.path.insert(0, str(HERE))
from signature_privacy import changed_outside, conservative_regions, redact_pdf, verify_redacted  # noqa: E402
from signature_privacy.redact import PAD, _rect  # noqa: E402
import zones as zones_mod  # noqa: E402
from verify_tolerant import verify_tolerant  # noqa: E402

TRUTH = HERE.parents[1] / "eval" / "truth.json"
RENDER_DPI = 150
INK_MIN_PX = 30          # pod tento počet tmavých pixelů v boxu (150 dpi) se zbytek nepočítá jako čitelný
READABLE_FRAC = 0.10     # zbylo víc než 10 % původního inkoustu → „čitelné (kandidát)“


_TEXTRACT = {}


def local_findings(pdf, base, mode="local", cache=None):
    """Nálezy z modulu podpisů. `local`: uložené nálezy `base` + zálohy bez služby (vložené obrázky, inkoust nad
    popiskem „Podpis“, vektorové tahy); u skenů bez OCR zálohy `label_anchored` nic nenajdou. `pipeline`: výchozí
    řetěz pipeline (Textract → vložené obrázky → inkoust nad popiskem, OCR z Textractu); `pipeline_vec` k tomu
    přidá vektorové tahy. Odpovědi Textractu se cachují podle SHA-256 stránky (cache)."""
    sys.path.insert(0, str(HERE.parents[1] / "signatures"))
    from signature_pipeline.detect import (CombinedDetector, LabelAnchoredDetector, PageImageDetector,
                                           PrecomputedDetector, TextractDetector, VectorStrokeDetector)
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        if mode == "local":
            det = CombinedDetector(PrecomputedDetector(base), PageImageDetector(), LabelAnchoredDetector(ocr=None),
                                   VectorStrokeDetector())
        else:
            if "t" not in _TEXTRACT:
                import boto3
                from botocore.config import Config
                cl = boto3.client("textract", region_name="eu-central-1",
                                  config=Config(retries={"max_attempts": 10, "mode": "adaptive"}))
                _TEXTRACT["t"] = TextractDetector(client=cl, cache_dir=cache)
            t = _TEXTRACT["t"]
            extra = [PageImageDetector(), LabelAnchoredDetector(ocr=t)]
            if mode == "pipeline_vec":
                extra.append(VectorStrokeDetector())
            det = CombinedDetector(t, *extra)
        return [{"page": d.page, "bbox": list(d.bbox), "by": d.detector} for d in det.detect(doc)]
    finally:
        doc.close()


def regions_of(pdf, findings, variant, ocr=None):
    if variant == "v1":
        return conservative_regions(pdf, findings)
    return zones_mod.regions_v2(pdf, findings, ocr=ocr)      # v2 umí zóny i na skenech (OCR řádky Textractu)


def notext_gray(doc, pno, dpi=RENDER_DPI):
    """Strana (0-based) bez textové vrstvy jako šedotónové pole; zůstane rastr a kresba."""
    tmp = pymupdf.open()
    try:
        tmp.insert_pdf(doc, from_page=pno, to_page=pno)
        page = tmp[0]
        page.add_redact_annot(page.rect)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                              text=pymupdf.PDF_REDACT_TEXT_REMOVE)
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    finally:
        tmp.close()


def full_gray(doc, pno, dpi=RENDER_DPI):
    pix = doc[pno].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()


def ink_thr(a):
    bg = float(np.percentile(a, 95))
    return bg - 40.0                 # inkoust = o víc než 40 úrovní tmavší než pozadí strany (i vybledlé skeny)


def window(a, box, pad=0.0):
    h, w = a.shape
    x0, y0, x1, y1 = box
    return (slice(max(0, int((y0 - pad) * h)), min(h, int(np.ceil((y1 + pad) * h)))),
            slice(max(0, int((x0 - pad) * w)), min(w, int(np.ceil((x1 + pad) * w)))))


def coverage(box, rects, n=60):
    """Podíl plochy boxu (relativní souřadnice), který leží v některém z obdélníků."""
    xs = box[0] + (np.arange(n) + .5) / n * (box[2] - box[0])
    ys = box[1] + (np.arange(n) + .5) / n * (box[3] - box[1])
    X, Y = np.meshgrid(xs, ys)
    m = np.zeros_like(X, dtype=bool)
    for r in rects:
        m |= (X >= r[0]) & (X <= r[2]) & (Y >= r[1]) & (Y <= r[3])
    return float(m.mean())


def region_rel(page_rect, reg):
    """Relativní obdélník oblasti tak, jak ho redakce použije (s okrajem u `full`)."""
    pad = PAD if reg.mode == "full" else 0.0
    x0, y0, x1, y1 = reg.bbox
    return (max(0, x0 - pad), max(0, y0 - pad), min(1, x1 + pad), min(1, y1 + pad))


def page_area_share(regions_on_page):
    n = 200
    full = np.zeros((n, n), bool)
    anyr = np.zeros((n, n), bool)
    for r in regions_on_page:
        x0, y0, x1, y1 = region_rel(None, r)
        sl = (slice(int(y0 * n), int(np.ceil(y1 * n))), slice(int(x0 * n), int(np.ceil(x1 * n))))
        anyr[sl] = True
        if r.mode == "full":
            full[sl] = True
    return float(full.mean()), float(anyr.mean())


def measure_doc(pdf, regions, truth_items, group, render_dir=None, tag=None, want_pages=()):
    out = {"sigs": []}
    t0 = time.time()
    red = redact_pdf(pdf, regions)
    out["redact_s"] = round(time.time() - t0, 2)
    out["size_orig"], out["size_red"] = len(pdf), len(red)
    out["verify_problems"], out["verify_edge_ignored"] = verify_tolerant(pdf, red, regions)
    out["verify_raw_n"] = len(out["verify_problems"]) + out["verify_edge_ignored"]
    out["changed_outside"] = changed_outside(pdf, red, regions)
    a = pymupdf.open(stream=pdf, filetype="pdf")
    b = pymupdf.open(stream=red, filetype="pdf")
    try:
        out["pages"] = a.page_count
        shares = [page_area_share([r for r in regions if r.page == p + 1]) for p in range(a.page_count)]
        out["area_full"] = [s[0] for s in shares]
        out["area_any"] = [s[1] for s in shares]
        out["regions"] = [{"page": r.page, "bbox": [round(v, 4) for v in r.bbox], "mode": r.mode, "source": r.source}
                          for r in regions]
        cache = {}
        if group == "generic":
            for i, s in enumerate(truth_items):
                p = s["page"]
                if not 1 <= p <= a.page_count:
                    out["sigs"].append({"i": i, "page": p, "error": "strana mimo rozsah"})
                    continue
                if p not in cache:
                    cache[p] = (notext_gray(a, p - 1), notext_gray(b, p - 1))
                ga, gb = cache[p]
                box = s["bbox"]
                thr = ink_thr(ga)
                sl = window(ga, box)
                ink_o = ga[sl] < thr
                rects_full = [region_rel(None, r) for r in regions if r.page == p and r.mode == "full"]
                rects_all = [region_rel(None, r) for r in regions if r.page == p]
                # černé výplně z redakce nejsou zbytek: maskuj je v zamaskované straně
                keep = np.ones(gb.shape, bool)
                for r in rects_full:
                    sy, sx = window(gb, r)                  # + 3 px: okraj výplně (antialiasing) není zbylý inkoust
                    keep[max(0, sy.start - 3):sy.stop + 3, max(0, sx.start - 3):sx.stop + 3] = False
                ink_r = (gb[sl] < ink_thr(gb)) & keep[sl]
                n_o, n_r = int(ink_o.sum()), int(ink_r.sum())
                out["sigs"].append({
                    "i": i, "page": p, "bbox": box, "role": s.get("role"),
                    "cover_black": round(coverage(box, rects_full), 3), "cover_any": round(coverage(box, rects_all), 3),
                    "ink_orig": n_o, "ink_left": n_r,
                    "left_frac": round(n_r / n_o, 3) if n_o else None,
                    "no_ink": n_o < INK_MIN_PX,
                    "readable": (n_o >= INK_MIN_PX and n_r >= INK_MIN_PX and n_r / n_o > READABLE_FRAC),
                })
        if render_dir is not None and want_pages:
            for p in want_pages:
                if 1 <= p <= a.page_count:
                    za = a[p - 1].get_pixmap(dpi=90)
                    zb = b[p - 1].get_pixmap(dpi=90)
                    za.save(str(render_dir / f"{tag}__p{p}__a.png"))
                    zb.save(str(render_dir / f"{tag}__p{p}__b.png"))
    finally:
        a.close()
        b.close()
    out["redacted_pdf"] = red
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--scenario", choices=["zones", "findings", "local", "pipeline", "pipeline_vec"], required=True)
    ap.add_argument("--zones", choices=["v1", "v2"], default="v1")
    ap.add_argument("--only", help="podřetězec názvu souboru (ladění)")
    ap.add_argument("--keep-pdf", action="store_true", help="uloží zamaskované PDF do OUT_DIR/pdf")
    ap.add_argument("--textract-all", action="store_true",
                    help="scénáře pipeline*: Textract i pro digitální PDF (jinak jen pro skeny; digitální dostanou `local`)")
    ap.add_argument("--cache", help="složka cache odpovědí Textractu (scénáře pipeline*)")
    ap.add_argument("--shard", help="K/N: zpracuje každý N-tý soubor od K (souběžné běhy)")
    ap.add_argument("--render-b", action="store_true", help="skupina B: uloží dvojice stran s podpisy")
    args = ap.parse_args()
    data, out = Path(args.data_dir), Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "pdf").mkdir(exist_ok=True)
    (out / "pages").mkdir(exist_ok=True)
    truth = json.load(open(TRUTH))["cases"]
    man = json.load(open(data / "manifest.json"))
    results = []
    k_n = tuple(int(x) for x in args.shard.split("/")) if args.shard else (0, 1)
    seq = 0
    for group in ("generic", "original"):
        for m in man[group]:
            if args.only and args.only not in m["file"]:
                continue
            seq += 1
            if seq % k_n[1] != k_n[0]:
                continue
            tcase = truth.get(m["case_id"], {})
            tdoc = (tcase.get("documents") or {}).get(m["filename"]) or {}
            titems = (tdoc.get("signatures") or {}).get("items", [])
            quality = tdoc.get("quality") or m.get("quality") or "?"
            pdf = (data / group / m["file"]).read_bytes()
            findings, rec_ocr, detect_error = [], None, None
            sigf = data / "sigs" / f"{m['case_id']}__{m['document_id']}.json"
            has_findings = sigf.exists()
            if args.scenario in ("findings", "local") and has_findings:
                js = json.load(open(sigf))
                findings = [{"page": s["page"], "bbox": s["bbox"]} for s in js.get("signatures", []) if s.get("bbox")]
            if args.scenario not in ("zones", "findings"):
                mode = args.scenario
                if mode.startswith("pipeline") and quality == "digital" and not args.textract_all:
                    mode = "local"          # digitální PDF: zálohy bez služby, Textract by jen stál čas
                try:
                    findings = local_findings(pdf, findings if mode == "local" else [], mode, args.cache)
                except Exception as e:  # noqa: BLE001
                    findings, detect_error = [], f"{type(e).__name__}: {str(e)[:120]}"
                rec_ocr = _TEXTRACT.get("t") if mode.startswith("pipeline") else None
            rec = {"group": group, "file": m["file"], "case_id": m["case_id"], "filename": m["filename"],
                   "quality": quality, "has_findings": has_findings, "n_findings": len(findings),
                   "n_truth": len(titems), "detect_error": detect_error}
            try:
                regs = regions_of(pdf, findings, args.zones, rec_ocr)
                want = sorted({int(i["page"]) for i in titems}) if (group == "original" and args.render_b) else ()
                tag = m["file"].replace(" ", "_").replace(".pdf", "")[:70]
                r = measure_doc(pdf, regs, titems if group == "generic" else [], group, out / "pages", tag, want)
                if args.keep_pdf:
                    (out / "pdf" / m["file"]).write_bytes(r["redacted_pdf"])
                r.pop("redacted_pdf")
                rec.update(r)
                if group == "original":
                    rec["truth_pages"] = [int(i["page"]) for i in titems]
            except Exception as e:  # noqa: BLE001
                rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
            results.append(rec)
            print(group, m["file"][:60], "ERR" if "error" in rec else f"verify={len(rec['verify_problems'])}", flush=True)
    suffix = f".shard{k_n[0]}" if args.shard else ""
    json.dump(results, open(out / f"results_{args.scenario}_{args.zones}{suffix}.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
