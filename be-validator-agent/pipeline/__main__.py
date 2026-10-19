"""CLI: python -I -m pipeline run_case <case_id> | run_document <case_id> <document_id> | run_s3 <case_id> <s3_key>"""
import argparse
import dataclasses
import json
import logging
import sys

from .config import STEPS, Settings
from .copies import copy_case
from .run import DocumentNotFound, Options, Source, run_case, run_document, run_prefix


def parse_args(argv):
    ap = argparse.ArgumentParser(prog="pipeline", description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    case = sub.add_parser("run_case", help="process every document of an ingested case")
    case.add_argument("case_id")
    doc = sub.add_parser("run_document", help="process one ingested document")
    doc.add_argument("case_id")
    doc.add_argument("document_id")
    direct = sub.add_parser("run_s3", help="process a sample PDF by its S3 key, with your own case_id/document_id")
    direct.add_argument("case_id")
    direct.add_argument("s3_key")
    direct.add_argument("--document-id", help="default: uuid5 of case_id and SHA-256, as the ingest does")
    direct.add_argument("--title", help="default: file name from the key")
    prefix = sub.add_parser("run_prefix", help="process every PDF directly under an S3 prefix as one case (samples)")
    prefix.add_argument("case_id")
    prefix.add_argument("s3_prefix")
    for p in (case, doc, direct, prefix):
        p.add_argument("--skip", default="", help=f"comma separated steps to skip: {','.join(STEPS)}")
        p.add_argument("--no-vision", action="store_true", help="do not call Bedrock; scanned pages become pages_failed")
        p.add_argument("--force-vision", action="store_true", help="transcribe every page visually")
        p.add_argument("--json", action="store_true", help="print rows as JSON")
        p.add_argument("--resume", action="store_true", help="skip documents already completed by this pipeline version")
        p.add_argument("--report", metavar="FILE", help="write per-document time, status and call counts (JSON), updated after every document")
    copy = sub.add_parser("copy_case", help="recompute copy_suspicion across the documents of a case (signatures.json)")
    copy.add_argument("case_id")
    copy.add_argument("--dry-run", action="store_true", help="compute and report, write nothing")
    report = sub.add_parser("report", help="table of analysed documents of the given cases (reads rows and run.json)")
    report.add_argument("case_ids", nargs="+")
    return ap.parse_args(argv)


def summary(row):
    failed = sorted(row.get("pages_failed", []))
    return (f"{row['processing_status']:<10} {row['document_id']} pages={row['page_count']}"
            f"{' failed=' + str([int(p) for p in failed]) if failed else ''} label={row.get('label', '-')} {row['title']}")


def report_table(case_ids):
    """One line per document: pages by origin (text layer / visual transcription / blank / failed) and status."""
    from .aws import Aws
    from .run import analysis_prefix
    aws = Aws(Settings())
    lines = [f"{'dokument':<46} {'stran':>5} {'textová vrstva':>14} {'vizuální':>8} {'prázdná':>7} {'selhala':>7}  stav"]
    for case_id in case_ids:
        items = aws.analysis.query(KeyConditionExpression=__import__("boto3").dynamodb.conditions.Key("case_id").eq(case_id))["Items"]
        for row in sorted(items, key=lambda r: r["title"]):
            raw = aws.get_bytes_or_none(analysis_prefix(case_id, row["document_id"]) + "run.json")
            methods = [p["method"] for p in json.loads(raw)["pages"]] if raw and "pages" in json.loads(raw) else []
            count = methods.count
            lines.append(f"{row['title'][:46]:<46} {int(row['page_count']):>5} {count('text_layer'):>14} {count('vision'):>8} "
                         f"{count('blank'):>7} {count('failed'):>7}  {row['processing_status']}")
    print("\n".join(lines))


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.command == "copy_case":
        print(json.dumps(copy_case(args.case_id, dry_run=args.dry_run), ensure_ascii=False, indent=1))
        return 0
    if args.command == "report":
        return report_table(args.case_ids) or 0
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    unknown = skip - set(STEPS)
    if unknown:
        sys.exit(f"unknown step(s): {', '.join(sorted(unknown))}")
    settings = Settings()
    settings = dataclasses.replace(settings, skip=frozenset(settings.skip | skip))
    options = Options(settings=settings, no_vision=args.no_vision, force_vision=args.force_vision, resume=args.resume)
    meter = None
    if args.report:
        from .measure import Meter
        meter = Meter(args.report)
        meter.install()
    try:
        if args.command == "run_case":
            rows = run_case(args.case_id, options)
        elif args.command == "run_prefix":
            rows = run_prefix(args.case_id, args.s3_prefix, options)
        elif args.command == "run_document":
            rows = [run_document(args.case_id, args.document_id, options=options)]
        else:
            rows = [run_document(args.case_id, args.document_id, source=Source(args.s3_key, args.title), options=options)]
    except DocumentNotFound as error:
        sys.exit(f"{error} (samples outside the ingest flow: use run_s3 with the S3 key)")
    if meter:
        meter.save(args.report)
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, default=lambda v: sorted(v) if isinstance(v, set) else str(v))
              if args.json else summary(row))
    return 0 if all(r["processing_status"] in ("completed", "partial") for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
