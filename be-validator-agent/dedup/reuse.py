"""Znovupoužití hotové analýzy téhož obsahu z jiného případu místo nových volání Bedrocku a Textractu.

Volá ho pipeline (`pipeline/run.py`) po stažení PDF. `aws` je objekt `pipeline.aws.Aws` (S3, tabulky, nastavení).
Nic se nezapíše, dokud nejsou přečteny všechny zdroje (text, vektory, `signatures.json`); selže-li to, vrátí se
`None` a dokument se zpracuje normálně."""
from __future__ import annotations

import json
import logging

from . import hashindex, vectors

log = logging.getLogger("dedup")

COPIED_ROW_FIELDS = ("label", "description", "confidence")


class NotReusable(RuntimeError):
    """Původní analýza se nedá znovu použít (chybí objekt, neúplné vektory …). Zpracuje se normálně."""


def find_source(aws, sha256, case_id, *, lookup=None):
    """Nejlepší hotová analýza téhož obsahu v JINÉM případu, nebo `None`.

    Bere jen `processing_status = completed` s textem. Přednost má řádek s ověřeným štítkem, pak novější."""
    lookup = lookup or hashindex.lookup
    candidates = []
    for match in lookup(sha256, exclude_case_id=case_id):
        row = aws.analysis.get_item(Key={"case_id": match["case_id"], "document_id": match["document_id"]},
                                    ConsistentRead=True).get("Item")
        if row and row.get("processing_status") == "completed" and row.get("text_s3_key"):
            candidates.append(row)
    candidates.sort(key=lambda r: (r.get("label_status") == "verified", r.get("updated_at", ""),
                                   r["case_id"], r["document_id"]), reverse=True)
    return candidates[0] if candidates else None


def _prefix(case_id, document_id):
    return f"cases/{case_id}/analysis/{document_id}/"


def _signatures_body(raw, src_case, src_doc, case_id, document_id):
    """`signatures.json` pro nový dokument: nová id, výřezy zůstávají původními objekty (`crop_s3_key`),
    `copy_suspicion` se vrací na `not_checked` (porovnání s ostatními dokumenty nového případu ještě neproběhlo)."""
    body = json.loads(raw.decode("utf-8"))
    if not isinstance(body, dict) or body.get("status") == "failed" or body.get("error"):
        raise NotReusable("signatures.json původního dokumentu je poškozený nebo chybový")
    signatures = body.get("signatures")
    if signatures is None:
        signatures = []
    if not isinstance(signatures, list):
        raise NotReusable("signatures.json původního dokumentu má špatný tvar")
    out = []
    for sig in signatures:
        if not isinstance(sig, dict) or not isinstance(sig.get("signature_id"), str):
            raise NotReusable("signatures.json původního dokumentu má špatný tvar")
        sig = {k: v for k, v in sig.items() if k not in ("crop_url", "similar_signatures")}
        sig.setdefault("crop_s3_key", f"{_prefix(src_case, src_doc)}signatures/{sig['signature_id']}.png")
        sig["copy_suspicion"] = {"level": "not_checked", "matches": []}
        out.append(sig)
    body.update(case_id=case_id, document_id=document_id, signatures=out)
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


def reuse_analysis(aws, source, case_id, document_id, title, *, skip=frozenset(), previous=None, pipeline_version,
                   now, s3v=None) -> tuple:
    """Zkopíruje analýzu dokumentu `source` (řádek tabulky analýzy) pod `case_id` / `document_id`.
    Vrací `(řádek, report)`; řádek je zapsaný v tabulce jako poslední (komplet, nebo nic). Vyvolá `NotReusable`."""
    src_case, src_doc = source["case_id"], source["document_id"]
    src_prefix, prefix = _prefix(src_case, src_doc), _prefix(case_id, document_id)
    page_count = int(source.get("page_count") or 0)

    # 1) štítek, popis a jistota; ověřený štítek nového dokumentu (rerun) se nepřepisuje, ze zdroje se `verified` nedědí
    label_fields, label_status = {}, "predicted"
    if "classify" not in skip:
        if previous and previous.get("label_status") == "verified":
            label_fields = {k: previous[k] for k in COPIED_ROW_FIELDS if k in previous}
            label_status = "verified"
        else:
            label_fields = {k: source[k] for k in COPIED_ROW_FIELDS if source.get(k) is not None}
    label = label_fields.get("label")

    # 2) vše přečíst, nic nezapisovat
    try:
        text = aws.get_bytes(source["text_s3_key"])
    except Exception as error:  # noqa: BLE001
        raise NotReusable(f"text původního dokumentu nejde přečíst ({type(error).__name__})") from error
    moved = None
    if "embed" not in skip:
        try:
            moved = vectors.rekey(
                vectors.read_document_vectors(src_doc, page_count, with_signatures="signatures" not in skip, s3v=s3v),
                src_doc, case_id, document_id, label)
        except vectors.VectorsUnavailable as error:
            raise NotReusable(str(error)) from error
    signatures_raw, keep_signatures = None, False
    if "signatures" not in skip and aws.get_bytes_or_none(prefix + "signatures.json") is not None:
        keep_signatures = True  # nálezy z jiného zdroje (CLI podpisů) se nepřepisují, stejně jako ve zpracování
    elif "signatures" not in skip:
        raw = aws.get_bytes_or_none(source.get("signatures_s3_key") or src_prefix + "signatures.json")
        if raw is not None:
            try:
                signatures_raw = _signatures_body(raw, src_case, src_doc, case_id, document_id)
            except (ValueError, UnicodeDecodeError) as error:
                raise NotReusable("signatures.json původního dokumentu není platný JSON") from error

    # 3) zápis: S3 objekty, vektory, nakonec řádek
    aws.put_bytes(prefix + "text.txt", text, "text/plain; charset=utf-8")
    copied_pages = 0
    for number in range(1, page_count + 1):
        try:
            aws.s3.copy_object(Bucket=aws.settings.bucket, Key=f"{prefix}pages/{number}.png",
                               CopySource={"Bucket": aws.settings.bucket, "Key": f"{src_prefix}pages/{number}.png"})
            copied_pages += 1
        except aws.s3.exceptions.ClientError as error:
            log.warning("%s/%s: strana %s původního dokumentu se nezkopírovala (%s)", case_id, document_id, number,
                        error.response.get("Error", {}).get("Code"))
    written = {}
    if moved is not None:
        vectors.write_vectors(moved, s3v=s3v)
        written = {index: len(items) for index, items in moved.items()}
    row = {"case_id": case_id, "document_id": document_id, "title": title, "page_count": page_count,
           "text_s3_key": prefix + "text.txt", "label_status": label_status, "pipeline_version": pipeline_version,
           "processing_status": "completed", "reused_from": {"case_id": src_case, "document_id": src_doc},
           "description": label_fields.pop("description", None) or "(dokument bez čitelného textu)"}
    row.update(label_fields)
    if signatures_raw is not None:
        aws.put_bytes(prefix + "signatures.json", signatures_raw, "application/json")
    if signatures_raw is not None or keep_signatures:
        row["signatures_s3_key"] = prefix + "signatures.json"
    row["updated_at"] = now()
    report = {"reused_from": row["reused_from"], "pages_copied": copied_pages, "vectors": written,
              "signatures_copied": signatures_raw is not None, "signatures_kept": keep_signatures}
    return row, report
