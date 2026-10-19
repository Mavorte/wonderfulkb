"""Copy suspicion across the documents of one case, written into the existing signatures.json files.

`detect_signatures` works on one document and cannot see the others, so a document processed alone gets
`copy_suspicion.level = not_checked`. This step compares the signatures of all documents of the case that
have a signatures.json: the findings stay as they are (even those from detectors this pipeline does not have),
only the `copy_suspicion` field is replaced. The ink masks that the comparison needs are rebuilt from the PDF
with the stored boxes (no Textract call, no crop is written anywhere).

  none         compared with every other document of the case, no match
  suspected    an almost identical signature in another document (`matches`)
  not_checked  the comparison could not cover the whole case (a document without signatures.json or PDF,
               or the signature has no usable ink)
"""
import collections
import hashlib
import json
import logging

from . import adapters
from .run import Options, analysis_prefix, derive_document_id

log = logging.getLogger("pipeline")

def not_checked():
    return {"level": "not_checked", "matches": []}


def _expected_documents(aws, case_id):
    """Every document id the case is known to have: ingest table, analysis rows, analysis prefixes in S3."""
    ids = {item["document_id"] for item in aws.list_documents(case_id)}
    from boto3.dynamodb.conditions import Key
    ids |= {i["document_id"] for i in aws.analysis.query(KeyConditionExpression=Key("case_id").eq(case_id))["Items"]}
    prefix = f"cases/{case_id}/analysis/"
    for page in aws.s3.get_paginator("list_objects_v2").paginate(Bucket=aws.settings.bucket, Prefix=prefix, Delimiter="/"):
        ids |= {p["Prefix"][len(prefix):].strip("/") for p in page.get("CommonPrefixes", [])}
    return ids


def _find_pdfs(aws, case_id, wanted):
    """{document_id: pdf bytes}: by ingest key first, the rest by hashing the PDFs lying under the case prefixes."""
    found, missing = {}, set(wanted)
    docs = {i["document_id"]: i for i in aws.list_documents(case_id)}
    for document_id in sorted(missing):
        for key in (docs.get(document_id, {}).get("s3_key"), f"cases/{case_id}/original/{document_id}.pdf"):
            # a masked copy has the signatures blacked out: its ink masks would be empty and say `none` wrongly
            data = aws.get_bytes_or_none(key) if key and "/redacted/" not in key else None
            if data is not None:
                found[document_id] = data
                break
    missing -= set(found)
    if missing:  # samples outside the ingest flow: file names differ from the ids, which come from the SHA-256
        for prefix in (f"cases/{case_id}/original/", f"cases/{case_id}/"):
            for page in aws.s3.get_paginator("list_objects_v2").paginate(Bucket=aws.settings.bucket, Prefix=prefix, Delimiter="/"):
                for obj in page.get("Contents", []):
                    if obj["Key"].lower().endswith(".pdf"):
                        data = aws.get_bytes(obj["Key"])
                        document_id = derive_document_id(case_id, data)
                        if document_id in missing:
                            found[document_id] = data
                            missing.discard(document_id)
    return found


def _load_signatures_json(aws, case_id, document_id):
    key = analysis_prefix(case_id, document_id) + "signatures.json"
    raw = aws.get_bytes_or_none(key)
    return key, (json.loads(raw) if raw is not None else None)


def copy_case(case_id, options=None, dry_run=False):
    """Recompute `copy_suspicion` for the whole case. Idempotent. `dry_run` only reports. Returns a summary dict."""
    options = options or Options()
    aws = options.get_aws()
    process_pdf, precomputed, mark_copies, iou = adapters.signature_tools()
    expected = _expected_documents(aws, case_id)
    files = {}
    for document_id in sorted(expected):
        key, body = _load_signatures_json(aws, case_id, document_id)
        if body is not None:
            files[document_id] = (key, body)
    pdfs = _find_pdfs(aws, case_id, files)

    computed = {}  # document_id -> [(existing entry, Signature with mask or None)]
    for document_id, (key, body) in files.items():
        entries = body.get("signatures", [])
        if document_id not in pdfs:
            log.warning("%s/%s: PDF not found, signatures not compared", case_id, document_id)
            continue
        found = process_pdf(pdfs[document_id], precomputed(entries), case_id, document_id, None) if entries else []
        pairs = []
        for entry in entries:
            best = max(found, key=lambda s: iou(s.bbox, entry["bbox"]) if s.page == entry["page"] else -1, default=None)
            usable = best is not None and best.page == entry["page"] and iou(best.bbox, entry["bbox"]) >= 0.5
            pairs.append((entry, best if usable else None))
        computed[document_id] = pairs
    mark_copies({d: [s for _, s in pairs if s is not None] for d, pairs in computed.items()})

    complete = set(computed) == expected  # every document of the case was compared
    transitions, changed_documents, relinked = collections.Counter(), 0, 0
    for document_id, pairs in computed.items():
        key, body = files[document_id]
        changed = False
        for entry, signature in pairs:
            if signature is not None and signature.copy_suspicion["matches"]:
                new = {"level": "suspected", "matches": signature.copy_suspicion["matches"]}
            elif signature is not None and signature.phash and signature.mask is not None and complete:
                new = {"level": "none", "matches": []}
            else:
                new = not_checked()
            old = entry.get("copy_suspicion") or {}
            if old != new:
                transitions[f"{old.get('level', 'missing')}->{new['level']}"] += 1
                entry["copy_suspicion"], changed = new, True
        if changed and not dry_run:
            aws.s3.put_object(Bucket=aws.settings.bucket, Key=key, Body=json.dumps(body, ensure_ascii=False).encode(),
                              ContentType="application/json", Metadata={"project": "wonderfulkb"})
        if changed:
            changed_documents += 1
    for document_id in ([] if dry_run else files):  # the table row points to the file (only rows that exist already)
        try:
            aws.analysis.update_item(Key={"case_id": case_id, "document_id": document_id},
                                     ConditionExpression="attribute_exists(case_id) AND attribute_not_exists(signatures_s3_key)",
                                     UpdateExpression="SET signatures_s3_key = :k",
                                     ExpressionAttributeValues={":k": files[document_id][0]})
            relinked += 1
        except aws.analysis.meta.client.exceptions.ConditionalCheckFailedException:
            pass
    return {"case_id": case_id, "documents_expected": len(expected), "with_signatures_json": len(files),
            "compared": len(computed), "complete": complete, "documents_changed": changed_documents,
            "transitions": dict(transitions), "rows_relinked": relinked, "dry_run": dry_run,
            "not_compared": sorted(set(files) - set(computed))}
