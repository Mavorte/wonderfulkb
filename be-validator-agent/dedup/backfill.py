"""Zpětné naplnění indexu hashů ze `wonderfulkb-uw-documents` (jen čte tabulky dokumentů a analýzy).

    AWS_PROFILE=hackathon python -I -m dedup.backfill            # nic nezapíše, vypíše, co by udělal (výchozí)
    AWS_PROFILE=hackathon python -I -m dedup.backfill --apply    # zapíše do wonderfulkb-uw-content-hashes

Štítek se doplní z `wonderfulkb-uw-document-analysis`, kde řádek existuje a štítek má. Idempotentní: opakované
spuštění nic nezdvojí a nepřepíše `registered_at`. Tabulka indexu musí existovat (viz template.yaml)."""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

from . import hashindex

DOCUMENTS = "wonderfulkb-uw-documents"
ANALYSIS = "wonderfulkb-uw-document-analysis"


def scan_documents(documents_table):
    """Všechny dokumenty s `sha256`: (case_id, document_id, sha256); položky bez hashe se počítají zvlášť."""
    kwargs = {"ProjectionExpression": "case_id, document_id, sha256"}
    while True:
        page = documents_table.scan(**kwargs)
        yield from page["Items"]
        if "LastEvaluatedKey" not in page:
            return
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def labels_for(analysis_table, items):
    """{(case_id, document_id): label} pro řádky analýzy, které štítek mají."""
    keys = [{"case_id": i["case_id"], "document_id": i["document_id"]} for i in items]
    ddb, name = analysis_table.meta.client, analysis_table.name
    out = {}
    for start in range(0, len(keys), 100):
        request = {name: {"Keys": keys[start:start + 100], "ProjectionExpression": "case_id, document_id, #l",
                          "ExpressionAttributeNames": {"#l": "label"}}}
        while request:
            reply = ddb.batch_get_item(RequestItems=request)
            for raw in reply["Responses"].get(name, []):
                label = raw.get("label")
                label = label.get("S") if isinstance(label, dict) else label
                if label:
                    case_id = raw["case_id"]["S"] if isinstance(raw["case_id"], dict) else raw["case_id"]
                    doc_id = raw["document_id"]["S"] if isinstance(raw["document_id"], dict) else raw["document_id"]
                    out[(case_id, doc_id)] = label
            request = reply.get("UnprocessedKeys") or None
    return out


def run(*, apply=False, documents_table=None, analysis_table=None, hashes_table=None, log=print) -> dict:
    import boto3
    ddb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION") or hashindex.REGION)
    documents_table = documents_table or ddb.Table(DOCUMENTS)
    analysis_table = analysis_table or ddb.Table(ANALYSIS)
    items = list(scan_documents(documents_table))
    with_hash = [i for i in items if isinstance(i.get("sha256"), str) and hashindex.SHA_RE.match(i["sha256"].lower())]
    labels = labels_for(analysis_table, with_hash)
    cases_by_hash = collections.defaultdict(set)
    for item in with_hash:
        cases_by_hash[item["sha256"].lower()].add(item["case_id"])
    shared = {sha: cases for sha, cases in cases_by_hash.items() if len(cases) > 1}
    registered = 0
    if apply:
        table = hashes_table or hashindex.table_name()
        for item in with_hash:
            hashindex.register(item["sha256"], item["case_id"], item["document_id"],
                               labels.get((item["case_id"], item["document_id"])), table=table)
            registered += 1
    summary = {"documents": len(items), "without_sha256": len(items) - len(with_hash), "distinct_hashes": len(cases_by_hash),
               "with_label": len(labels), "hashes_in_more_cases": len(shared), "applied": apply, "registered": registered}
    log(json.dumps(summary, ensure_ascii=False))
    if not apply:
        log("(bez --apply se nic nezapsalo)")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="zapsat do indexu (jinak jen výpis)")
    args = parser.parse_args(argv)
    run(apply=args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
