"""Measure Textract signature detection against the annotated synthetic set.

    PYTHONPATH=src python scripts/eval_signatures.py ROOT --out DIR [--dry-run] [--limit N]

ROOT is the extracted `synteticke_dokumenty_20_pripadu` folder; it is read as
untrusted data. Ground truth is each annotation's `marks[].signature_bbox`
(PDF points, origin top left). Every page is cut into a one-page PDF and sent as
bytes to AnalyzeDocument(SIGNATURES) in eu-central-1, so nothing is written to AWS.
Raw Textract blocks are cached in DIR/cache: a re-run costs nothing.
`--dry-run` only counts pages and prints the estimated cost.

Writes DIR/documents.csv, DIR/groups.csv, DIR/missed.csv, DIR/summary.json.
"""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf

from document_processing.signatures import TEXTRACT_REGION, build_signatures

# Reference price, to be checked against the AWS pricing page; only used for the estimate.
USD_PER_1000_PAGES = 3.5
BASES = ("synteticke_dokumenty", "synteticke_dokumenty_rozsireni")

ROLE_MAP = {
    "Poskytovatel financování": "provider", "Poskytovatel – první podpis": "provider",
    "Poskytovatel – druhý podpis": "provider", "Věřitel – první zmocněnec": "provider",
    "Věřitel – druhý zmocněnec": "provider", "Druhý zmocněnec věřitele": "provider",
    "Příjemce financování": "borrower", "Zákazník": "borrower", "Pojistník": "borrower",
    "Objednatel": "buyer", "Kupující": "buyer",
    "Dodavatel": "supplier", "Prodávající": "supplier", "Servis dodavatele": "supplier",
    "Pojistitel": "insurer", "Ručitel": "guarantor",
    # "Předávající" and "Přebírající" have no unambiguous counterpart: not scored.
}


def expected_role(raw):
    return raw if raw in ("provider", "borrower", "buyer", "supplier", "guarantor", "insurer") else ROLE_MAP.get(raw)


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def center_inside(box, outer, margin=0.1):
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    mx, my = (outer[2] - outer[0]) * margin, (outer[3] - outer[1]) * margin
    return outer[0] - mx <= cx <= outer[2] + mx and outer[1] - my <= cy <= outer[3] + my


def match(truth, found):
    """Greedy one-to-one matching of truth boxes to detections (IoU first, centre-in-box as fallback)."""
    pairs = []
    for ti, t in enumerate(truth):
        for fi, f in enumerate(found):
            overlap = iou(t["bbox"], f.bbox)
            if overlap >= 0.2 or center_inside(f.bbox, t["bbox"]):
                pairs.append((overlap, ti, fi))
    pairs.sort(reverse=True)
    taken_t, taken_f, result = set(), set(), {}
    for _, ti, fi in pairs:
        if ti not in taken_t and fi not in taken_f:
            taken_t.add(ti), taken_f.add(fi)
            result[ti] = fi
    return result


def load_documents(root):
    documents = []
    for base in BASES:
        for annotation in sorted((root / base / "anotace").glob("*/*.json")):
            data = json.loads(annotation.read_text())
            pdf = (root / base / data["document"]).resolve()
            if not pdf.is_relative_to(root.resolve()) or not pdf.exists():
                sys.exit(f"annotation points outside the data set or to a missing file: {annotation}")
            documents.append({"path": f"{base}/{data['document']}", "pdf": pdf, "case": data["case_id"],
                              "quality": data.get("quality") or "primary_AB", "marks": data.get("marks", [])})
    return documents


def page_blocks(client, doc, index, cache):
    """Raw Textract blocks of one page, cached on disk by document path and page."""
    cache_file = cache / (doc["path"].replace("/", "__") + f".p{index + 1}.json")
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    with pymupdf.open(doc["pdf"]) as source, pymupdf.open() as single:
        single.insert_pdf(source, from_page=index, to_page=index)
        body = single.tobytes()
    blocks = client.analyze_document(Document={"Bytes": body}, FeatureTypes=["SIGNATURES"])["Blocks"]
    for block in blocks:
        block["Page"] = index + 1
    cache_file.write_text(json.dumps(blocks))
    return blocks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    documents = load_documents(args.root)[: args.limit]
    sizes = {}
    for doc in documents:
        with pymupdf.open(doc["pdf"]) as pdf:
            sizes[doc["path"]] = [(p.rect.width, p.rect.height) for p in pdf]
    pages = sum(len(v) for v in sizes.values())
    print(f"{len(documents)} documents, {pages} pages, about {pages * USD_PER_1000_PAGES / 1000:.2f} USD at {USD_PER_1000_PAGES} USD / 1000 pages")
    if args.dry_run:
        return

    import boto3
    from botocore.config import Config
    client = boto3.client("textract", region_name=TEXTRACT_REGION,
                          config=Config(retries={"max_attempts": 10, "mode": "adaptive"}))
    args.out.mkdir(parents=True, exist_ok=True)
    cache = args.out / "cache"
    cache.mkdir(exist_ok=True)

    jobs = [(doc, index) for doc in documents for index in range(len(sizes[doc["path"]]))]
    with ThreadPoolExecutor(args.workers) as pool:
        blocks = list(pool.map(lambda job: page_blocks(client, job[0], job[1], cache), jobs))
    by_document = defaultdict(list)
    for (doc, _), page in zip(jobs, blocks):
        by_document[doc["path"]].extend(page)

    rows, missed, groups = [], [], defaultdict(Counter)
    identities = defaultdict(Counter)
    for doc in documents:
        found = build_signatures(by_document[doc["path"]])
        truth = []
        for mark in doc["marks"]:
            width, height = sizes[doc["path"]][mark["page"] - 1]
            x0, y0, x1, y1 = mark["signature_bbox"]
            truth.append({**mark, "bbox": [x0 / width, y0 / height, x1 / width, y1 / height]})
        counts = Counter()
        for page in range(1, len(sizes[doc["path"]]) + 1):
            page_truth = [t for t in truth if t["page"] == page]
            page_found = [f for f in found if f.page == page]
            matched = match(page_truth, page_found)
            for ti, t in enumerate(page_truth):
                identities[t["signature_identity"]]["truth"] += 1
                if ti in matched:
                    detection = page_found[matched[ti]]
                    counts["found"] += 1
                    wanted = expected_role(t["role"])
                    if wanted:
                        counts["role_scored"] += 1
                        counts["role_determined"] += detection.role != "unknown"
                        counts["role_correct"] += detection.role == wanted
                        counts["role_wrong"] += detection.role not in ("unknown", wanted)
                else:
                    identities[t["signature_identity"]]["missed"] += 1
                    missed.append({"document": doc["path"], "page": page, "role": t["role"], "signer": t["signer"],
                                   "quality": doc["quality"], "signature_identity": t["signature_identity"][:12]})
            counts["truth"] += len(page_truth)
            counts["false_positive"] += len(page_found) - len(matched)
            counts["pages_with_truth"] += bool(page_truth)
            counts["pages_with_truth_hit"] += bool(page_truth) and bool(matched)
        counts["pages"] = len(sizes[doc["path"]])
        counts["detected"] = len(found)
        counts["document_complete"] = counts["truth"] > 0 and counts["found"] == counts["truth"]
        counts["documents_with_truth"] = counts["truth"] > 0
        rows.append({"document": doc["path"], "case": doc["case"], "quality": doc["quality"], **{
            k: counts[k] for k in ("pages", "truth", "detected", "found", "false_positive", "role_scored",
                                   "role_determined", "role_correct", "role_wrong")}})
        for key in ("pages", "truth", "detected", "found", "false_positive", "role_scored", "role_determined",
                    "role_correct", "role_wrong", "pages_with_truth", "pages_with_truth_hit", "document_complete",
                    "documents_with_truth"):
            groups[doc["quality"]][key] += counts[key]
            groups["ALL"][key] += counts[key]
        groups[doc["quality"]]["documents"] += 1
        groups["ALL"]["documents"] += 1

    def write(name, items):
        if items:
            with (args.out / name).open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(items[0]))
                writer.writeheader()
                writer.writerows(items)

    write("documents.csv", rows)
    write("missed.csv", missed)
    summary = []
    for name, c in sorted(groups.items(), key=lambda kv: (kv[0] != "ALL", kv[0])):
        summary.append({"group": name, **{k: c[k] for k in (
            "documents", "pages", "truth", "detected", "found", "false_positive", "role_scored", "role_determined",
            "role_correct", "role_wrong", "documents_with_truth", "document_complete")},
            "recall": round(c["found"] / c["truth"], 3) if c["truth"] else None,
            "precision": round(c["found"] / c["detected"], 3) if c["detected"] else None})
    write("groups.csv", summary)
    worst = sorted(((v["missed"], v["truth"], k[:12]) for k, v in identities.items() if v["missed"]), reverse=True)[:10]
    (args.out / "summary.json").write_text(json.dumps({"groups": summary, "most_missed_signature_identities": worst}, indent=1, ensure_ascii=False))
    total = summary[0]
    print(json.dumps(total, ensure_ascii=False))


if __name__ == "__main__":
    main()
