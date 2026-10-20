#!/usr/bin/env python3
"""Queue the documents of wonderfulkb-uw-documents that have no `completed` analysis row.

Uses the same enqueue step as the stream Lambda (row `queued` + one SQS message per document), so it is safe
to run repeatedly and while the trigger works: a completed row is never touched, a document a worker holds is
skipped, a duplicate message does no harm. Without --apply nothing is written (a dry run lists what would be queued).

  AWS_PROFILE=hackathon python3 backfill.py                      # dry run, all cases
  AWS_PROFILE=hackathon python3 backfill.py --apply              # queue everything, 30 messages a minute
  AWS_PROFILE=hackathon python3 backfill.py --apply --case SYN-A01 --rate 60
  AWS_PROFILE=hackathon python3 backfill.py --apply --statuses missing,failed,partial   # also retry failed/partial

--statuses: which documents count as "not done": missing (no row), queued, processing (only a stale claim, see
common.LEASE_SECONDS), failed, partial. Default: all of them. completed is never queued, --force is the only way
to rerun it (--force --case X, never without --case).
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # infra/validator-agent
from trigger import common  # noqa: E402

REGION = "eu-central-1"
QUEUE_NAME = "wonderfulkb-trigger-documents"
STATUSES = ("missing", "queued", "processing", "failed", "partial")


def scan(table, projection):
    items, kwargs = [], {"ProjectionExpression": projection}
    while True:
        page = table.scan(**kwargs)
        items += page["Items"]
        if "LastEvaluatedKey" not in page:
            return items
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def candidates(ctx, statuses, case=None, force=False):
    """[(case_id, document_id, filename, status)] of documents to queue, sorted by case so cases finish one by one.
    A `processing` row is listed too; enqueue_document skips it while its claim is fresh."""
    documents = scan(ctx.documents, "case_id, document_id, filename")
    rows = {(r["case_id"], r["document_id"]): r.get("processing_status")
            for r in scan(ctx.analysis, "case_id, document_id, processing_status")}
    out = []
    for d in sorted(documents, key=lambda d: (d["case_id"], d["document_id"])):
        if case and d["case_id"] != case:
            continue
        status = rows.get((d["case_id"], d["document_id"])) or "missing"
        if status == "completed" and not force:
            continue
        if status == "completed" or status in statuses:
            out.append((d["case_id"], d["document_id"], d.get("filename"), status))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="really queue (default: dry run)")
    ap.add_argument("--case", help="only this case_id")
    ap.add_argument("--statuses", default=",".join(STATUSES), help=f"comma separated subset of {','.join(STATUSES)}")
    ap.add_argument("--rate", type=float, default=30, help="messages per minute (default 30; the workers set the real pace)")
    ap.add_argument("--max", type=int, default=0, help="queue at most this many documents (0 = all)")
    ap.add_argument("--force", action="store_true", help="also rerun completed documents (needs --case)")
    ap.add_argument("--command-key", help="stable command identity; reuse on retry (required for --apply)")
    ap.add_argument("--queue-url", help="default: look up the queue wonderfulkb-trigger-documents")
    args = ap.parse_args(argv)
    statuses = {s.strip() for s in args.statuses.split(",") if s.strip()}
    if statuses - set(STATUSES):
        sys.exit(f"unknown status: {', '.join(sorted(statuses - set(STATUSES)))}")
    if args.force and not args.case:
        sys.exit("--force needs --case")
    if args.rate <= 0:
        sys.exit("--rate must be positive")
    if args.apply and not args.command_key:
        sys.exit("--apply needs --command-key (reuse the same key on retries)")

    ctx = common.Context()
    queue_url = args.queue_url
    if args.apply and not queue_url:
        queue_url = ctx.sqs.get_queue_url(QueueName=QUEUE_NAME)["QueueUrl"]
    ctx.queue_url = queue_url or ""
    todo = candidates(ctx, statuses, args.case, args.force)
    if args.max:
        todo = todo[:args.max]
    by_status = {}
    for _, _, _, status in todo:
        by_status[status] = by_status.get(status, 0) + 1
    cases = len({c for c, *_ in todo})
    print(f"{len(todo)} documents in {cases} cases to queue {by_status}" + ("" if args.apply else " (dry run, nothing written)"))
    if not args.apply:
        for case_id, document_id, filename, status in todo[:20]:
            print(f"  {case_id}  {document_id}  {status:<10} {filename}")
        if len(todo) > 20:
            print(f"  ... and {len(todo) - 20} more")
        return 0

    pause, result = 60.0 / args.rate, {"queued": 0, "completed": 0, "processing": 0, "failed": 0}
    for number, (case_id, document_id, filename, _) in enumerate(todo, start=1):
        try:
            outcome = common.enqueue_document(ctx, case_id, document_id, filename, force=args.force,
                                              request_key=f"backfill:{args.command_key}:{case_id}:{document_id}")
        except Exception as error:  # noqa: BLE001 - keep going, the failures are listed at the end
            outcome = "failed"
            print(f"  FAILED {case_id}/{document_id}: {type(error).__name__}: {error}", file=sys.stderr)
        result[outcome] += 1
        if number % 10 == 0 or number == len(todo):
            print(f"  {number}/{len(todo)} {result}", flush=True)
        if outcome == "queued" and number < len(todo):
            time.sleep(pause)
    print(f"done: {result} (completed/processing = skipped on purpose)")
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
