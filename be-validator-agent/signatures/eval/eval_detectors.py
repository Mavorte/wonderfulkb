"""Measure signature detectors against the annotations of the 20-case package (group A).

    python eval/eval_detectors.py PACK_ROOT --cache DIR [--quality documents.csv] [--out result.json]

PACK_ROOT is the unpacked `synteticke_dokumenty_20_pripadu`. Truth is `marks[].signature_bbox` (PDF points,
origin top left, page numbers from 1). Textract answers come from the cache (`TextractDetector(cache_dir=...)`),
a missing entry is fetched, so run it once with credentials and the cost is paid once.

Match of a finding with a truth box, one to one:
  loose  IoU >= 0.2, or the centre of the finding lies inside the truth box grown by 10 %
         (the rule of the OCR session's report, so the numbers compare);
  strict IoU >= 0.5.
Everything not matched is a false finding.
"""
import argparse
import csv
import glob
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pymupdf  # noqa: E402

from signature_pipeline.detect import (CombinedDetector, LabelAnchoredDetector, PageImageDetector,  # noqa: E402
                                       TextractDetector, VectorStrokeDetector, iou)
from signature_pipeline.models import Detection  # noqa: E402


def to_points(bbox, page):
    r = page.rect
    return [bbox[0] * r.width, bbox[1] * r.height, bbox[2] * r.width, bbox[3] * r.height]


def loose_match(det, truth):
    if iou(det, truth) >= 0.2:
        return True
    cx, cy = (det[0] + det[2]) / 2, (det[1] + det[3]) / 2
    w, h = truth[2] - truth[0], truth[3] - truth[1]
    return truth[0] - 0.1 * w <= cx <= truth[2] + 0.1 * w and truth[1] - 0.1 * h <= cy <= truth[3] + 0.1 * h


def strict_match(det, truth):
    return iou(det, truth) >= 0.5


def match(dets, truths, rule):
    """Greedy one-to-one: each truth takes the free finding with the highest IoU that satisfies the rule."""
    free, hit = list(range(len(dets))), 0
    for t in truths:
        best = max((i for i in free if rule(dets[i], t)), key=lambda i: iou(dets[i], t), default=None)
        if best is not None:
            free.remove(best)
            hit += 1
    return hit, len(free)


def documents(root):
    for sub in ("synteticke_dokumenty", "synteticke_dokumenty_rozsireni"):
        for ann in sorted(glob.glob(f"{root}/{sub}/anotace/*/*.json")):
            data = json.load(open(ann))
            pdf = f"{root}/{sub}/{data['document']}"
            if os.path.exists(pdf):
                yield sub, data["case_id"], pdf, data.get("marks", [])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root")
    ap.add_argument("--cache", required=True)
    ap.add_argument("--quality", help="documents.csv of the OCR session (quality class per document)")
    ap.add_argument("--out")
    ap.add_argument("--found-cache", help="directory for the findings of every base detector per document")
    args = ap.parse_args()

    quality = {}
    if args.quality:
        for row in csv.DictReader(open(args.quality)):
            quality[Path(row["document"]).parent.name + "/" + Path(row["document"]).name] = row["quality"]

    textract = TextractDetector(cache_dir=args.cache)
    images, label, vector = PageImageDetector(), LabelAnchoredDetector(ocr=textract), VectorStrokeDetector()
    class Fixed:
        def __init__(self, found):
            self.found = found

        def detect(self, doc):
            return self.found

    combos = {
        "textract": ("textract",),
        "page_images": ("page_images",),
        "label_anchored": ("label_anchored",),
        "textract+images": ("textract", "page_images"),
        "textract+label": ("textract", "label_anchored"),
        "textract+images+label": ("textract", "page_images", "label_anchored"),
        "vector_strokes": ("vector_strokes",),
        "textract+vector": ("textract", "vector_strokes"),
        "textract+images+label+vector": ("textract", "page_images", "label_anchored", "vector_strokes"),
    }
    base = {"textract": textract, "page_images": images, "label_anchored": label, "vector_strokes": vector}

    def run_base(name_, detector, doc, pdf):
        """Findings of one base detector for one document, kept on disk when --found-cache is given."""
        path = None
        if args.found_cache:
            Path(args.found_cache).mkdir(parents=True, exist_ok=True)
            path = Path(args.found_cache) / (name_ + "__" + pdf.replace("/", "_") + ".json")
            if path.exists():
                return [Detection(*row) for row in json.loads(path.read_text())]
        found = detector.detect(doc)
        if path:
            path.write_text(json.dumps([[d.page, d.bbox, d.detector, d.score] for d in found]))
        return found
    stats = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))   # group -> config -> counter
    complete = defaultdict(lambda: defaultdict(lambda: [0, 0]))          # group -> config -> [docs with all found, docs with truth]
    for sub, case, pdf, marks in documents(args.root):
        name = Path(pdf).parent.name + "/" + Path(pdf).name
        groups = ["ALL", quality.get(name) or ("A/B vektorova" if sub == "synteticke_dokumenty" else "C skeny")]
        doc = pymupdf.open(pdf)
        truth_by_page = defaultdict(list)
        for m in marks:
            if m.get("signature_bbox"):
                truth_by_page[m["page"]].append(m["signature_bbox"])
        parts = {name_: Fixed(run_base(name_, base[name_], doc, pdf)) for name_ in base}   # every base detector runs once
        configs = {c: (lambda d, c=c: CombinedDetector(*[parts[n] for n in combos[c]]).detect(d)) for c in combos}
        for cname, run in configs.items():
            found = run(doc)
            by_page = defaultdict(list)
            for d in found:
                by_page[d.page].append(to_points(d.bbox, doc[d.page - 1]))
            all_hit = True
            for rule_name, rule in (("loose", loose_match), ("strict", strict_match)):
                hits = fps = 0
                for page in set(by_page) | set(truth_by_page):
                    h, f = match(by_page.get(page, []), truth_by_page.get(page, []), rule)
                    hits, fps = hits + h, fps + f
                for g in groups:
                    s = stats[g][cname]
                    s[f"hit_{rule_name}"] += hits
                    s[f"fp_{rule_name}"] += fps
                if rule_name == "loose":
                    all_hit = hits == sum(len(v) for v in truth_by_page.values())
            for g in groups:
                stats[g][cname]["truth"] += sum(len(v) for v in truth_by_page.values())
                stats[g][cname]["docs"] += 1
                if truth_by_page:
                    complete[g][cname][1] += 1
                    complete[g][cname][0] += all_hit
    out = {}
    for g in sorted(stats):
        out[g] = {}
        for cname, s in stats[g].items():
            t = s["truth"] or 1
            out[g][cname] = {"truth": s["truth"], "docs": s["docs"],
                             "found_loose": s["hit_loose"], "recall_loose": round(s["hit_loose"] / t, 3),
                             "false_loose": s["fp_loose"],
                             "found_strict": s["hit_strict"], "recall_strict": round(s["hit_strict"] / t, 3),
                             "false_strict": s["fp_strict"],
                             "docs_complete": f"{complete[g][cname][0]}/{complete[g][cname][1]}"}
    text = json.dumps(out, ensure_ascii=False, indent=1)
    if args.out:
        Path(args.out).write_text(text)
    print(text)
    print("Textract calls:", textract.calls, file=sys.stderr)


if __name__ == "__main__":
    main()
