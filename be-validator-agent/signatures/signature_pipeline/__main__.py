"""CLI: python -m signature_pipeline CASE_ID file.pdf [file.pdf ...] [--out out.json] [--crops dir] [--cache dir]"""
import argparse
import json
from pathlib import Path

from .detect import TextractDetector, default_detector
from .pipeline import LocalCropStore, process_case


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("case_id")
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--out", help="JSON output file (default: stdout)")
    ap.add_argument("--crops", default="crops")
    ap.add_argument("--cache", default=".textract-cache", help="cache of Textract responses")
    ap.add_argument("--region", default="eu-central-1")
    ap.add_argument("--only-textract", action="store_true",
                    help="no fallback detectors (default: Textract + page_images + label_anchored)")
    ap.add_argument("--vector", action="store_true",
                    help="also vector_strokes: finds signatures drawn as curves, but adds false findings (stamp parts)")
    args = ap.parse_args()
    textract = TextractDetector(region=args.region, cache_dir=args.cache)
    detector = textract if args.only_textract else default_detector(textract, vector=args.vector)
    docs = {Path(p).stem: p for p in args.pdfs}
    result = process_case(args.case_id, docs, detector, LocalCropStore(args.crops))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    Path(args.out).write_text(text) if args.out else print(text)
    print(f"Textract calls: {textract.calls}", file=__import__("sys").stderr)


if __name__ == "__main__":
    main()
