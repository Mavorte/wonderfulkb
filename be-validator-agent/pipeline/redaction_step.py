"""Redaction step of `run_document` (be-validator-agent/docs/validator-agent-privacy.md, part 3): the readable original never feeds
the rest of the pipeline.

Order, all on the ORIGINAL held in memory:

  detect signatures (or reuse the stored signatures.json)  ->  conservative regions  ->  redact_pdf
  ->  verify_redacted (fails => RedactionError, nothing is written)  ->  crops cut from the original
  ->  phash, crop kept in memory for the embedding  ->  encrypt_image + distorted_preview (S3CropStore)
  ->  cases/<case>/redacted/<document_id>.pdf  ->  analysis/<doc>/signatures.json

Nothing readable is written: no `signatures/<sig>.png`, no `crop_url`, no `/tmp` file. The caller continues with
`RedactionResult.redacted` (text, pages/<n>.png, embeddings, visual transcription all read the masked copy) and
embeds the crops from `RedactionResult.crops` before dropping them.

Every failure is a `RedactionError(code)`; the caller ends the document as `failed` with that code and the
original stays where it was. A readable copy is never written as a fallback.
"""
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field

from . import adapters

log = logging.getLogger("pipeline")

TAGGING = "project=wonderfulkb"


class RedactionError(RuntimeError):
    """The document must stop: `code` goes to the analysis row's run.json (`failed`). Messages carry no data."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass
class RedactionResult:
    redacted: bytes                  # the masked PDF: all further steps read this
    redacted_key: str
    original_sha256: str             # hash of the readable original (dedup keeps working on it)
    signatures: list = None          # entries of signatures.json as written; None = file left alone
    signatures_key: str = None
    crops: list = field(default_factory=list, repr=False)  # [(page, readable png)] for the embedding, memory only
    info: dict = field(default_factory=dict)               # goes to run.json

    def drop_crops(self):
        self.crops = []

    def apply_to_row(self, row):
        row["original_sha256"] = self.original_sha256
        row["redacted_s3_key"] = self.redacted_key
        if self.signatures_key:
            row["signatures_s3_key"] = self.signatures_key


def redacted_key(case_id, document_id):
    return f"cases/{case_id}/redacted/{document_id}.pdf"


def is_redacted_key(key):
    return "/redacted/" in (key or "")


def _prefix(case_id, document_id):
    from .run import analysis_prefix  # run imports this module
    return analysis_prefix(case_id, document_id)


def _privacy():
    try:
        return adapters.privacy()
    except adapters.StepUnavailable as error:
        raise RedactionError("REDACTION_UNAVAILABLE") from error


def adopt_redacted(aws, key, data):
    """Input that already is a masked copy (`redacted/…`, e.g. after a migration switched `s3_key`): no detection,
    no crops (the signatures are blacked out, a crop would encrypt a black box over the good one), no write.
    The hash of the real original stays in the object's metadata."""
    meta = aws.head_metadata(key) or {}
    sha = meta.get("original-sha256") or meta.get("original_sha256")  # headers: some stacks turn _ into -
    if not sha:
        raise RedactionError("REDACTED_INPUT_WITHOUT_ORIGINAL_SHA256")
    return RedactionResult(data, key, sha, info={"status": "already_redacted", "source_key": key})


def run(options, case_id, document_id, key, data):
    """Masked copy of `data` (the original PDF bytes), encrypted crops and signatures.json. Raises RedactionError."""
    settings, aws = options.settings, options.get_aws()
    if is_redacted_key(key):
        return adopt_redacted(aws, key, data)
    if not data.startswith(b"%PDF-"):
        raise RedactionError("NOT_A_PDF")
    started = time.monotonic()
    privacy = _privacy()
    prefix = _prefix(case_id, document_id)
    sig_key = prefix + "signatures.json"
    crop_signatures = "signatures" not in settings.skip
    provider = None
    if crop_signatures:  # fail before any Textract call when there is no way to encrypt
        try:
            provider = options.key_provider or privacy.default_provider()
        except Exception as error:  # noqa: BLE001
            log.error("%s/%s: no key provider: %s", case_id, document_id, type(error).__name__)
            raise RedactionError("ENCRYPTION_UNAVAILABLE") from None

    items, source = _findings(options, aws, data, sig_key, crop_signatures, case_id, document_id)

    # conservative regions -> redact -> verify. No data leaves memory before verify_redacted passes.
    try:
        regions = privacy.conservative_regions(data, [{"page": i["page"], "bbox": i["bbox"]} for i in items])
        masked = privacy.redact_pdf(data, regions)
    except Exception as error:  # noqa: BLE001
        log.error("%s/%s: redaction failed: %s", case_id, document_id, type(error).__name__)
        raise RedactionError("INVALID_OR_ENCRYPTED_PDF" if _unreadable(data) else "REDACTION_FAILED") from None
    try:
        problems = privacy.verify_redacted(data, masked, regions)
    except Exception as error:  # noqa: BLE001
        log.error("%s/%s: redaction check crashed: %s", case_id, document_id, type(error).__name__)
        raise RedactionError("REDACTION_VERIFY_ERROR") from None
    if problems:
        log.error("%s/%s: redaction check found %d problem(s): %s", case_id, document_id, len(problems), problems[:5])
        raise RedactionError("REDACTION_VERIFY_FAILED")

    original_sha256 = hashlib.sha256(data).hexdigest()
    entries, crops = None, []
    if crop_signatures:
        entries, crops = _encrypted_crops(options, aws, provider, data, items, source == "stored",
                                          sig_key, case_id, document_id)
    try:  # the masked copy goes after the encrypted crops: never a masked copy whose signatures cannot be shown
        aws.put_bytes(redacted_key(case_id, document_id), masked, "application/pdf",
                      metadata={"project": "wonderfulkb", "original-sha256": original_sha256,
                                "original-size": str(len(data))}, tagging=TAGGING)
        if entries is not None:
            body = {"case_id": case_id, "document_id": document_id, "signatures": entries}
            aws.put_bytes(sig_key, json.dumps(body, ensure_ascii=False).encode(), "application/json")
    except Exception as error:  # noqa: BLE001
        log.error("%s/%s: writing the masked copy failed: %s", case_id, document_id, type(error).__name__)
        raise RedactionError("REDACTED_WRITE_FAILED") from None

    counts = {mode: sum(1 for r in regions if r.mode == mode) for mode in ("full", "graphics")}
    info = {"status": "ok", "detection": source, "signatures": len(items), "regions": counts,
            "original_sha256": original_sha256, "original_bytes": len(data), "redacted_bytes": len(masked),
            "redacted_s3_key": redacted_key(case_id, document_id), "encrypted_crops": len(crops),
            "seconds": round(time.monotonic() - started, 2)}
    return RedactionResult(masked, redacted_key(case_id, document_id), original_sha256, entries,
                           sig_key if entries is not None or source == "stored" else None, crops, info)


def _unreadable(data):
    try:
        import pymupdf
        pymupdf.open(stream=data, filetype="pdf").close()
        return False
    except Exception:  # noqa: BLE001
        return True


def _findings(options, aws, data, sig_key, crop_signatures, case_id, document_id):
    """(items, source): the stored signatures.json wins (findings made elsewhere are never replaced and a rerun
    keeps the same ids); otherwise the detector chain runs on the original. Skipped signatures + nothing stored
    = no findings, only the label zones are masked."""
    raw = aws.get_bytes_or_none(sig_key)
    if raw is not None:
        try:
            stored = json.loads(raw)["signatures"]
            return [dict(s) for s in stored], "stored"
        except Exception:  # noqa: BLE001
            raise RedactionError("STORED_SIGNATURES_UNREADABLE") from None
    if not crop_signatures:
        return [], "skipped"
    try:
        return adapters.detect_boxes(data, options.signature_detector), "detected"
    except adapters.StepUnavailable as error:
        log.error("%s/%s: signature detection unavailable: %s", case_id, document_id, error)
        raise RedactionError("SIGNATURE_DETECTION_UNAVAILABLE") from None
    except Exception as error:  # noqa: BLE001 - without findings the masking would silently be weaker
        log.error("%s/%s: signature detection failed: %s", case_id, document_id, type(error).__name__)
        raise RedactionError("SIGNATURE_DETECTION_FAILED") from None


def _encrypted_crops(options, aws, provider, data, items, stored, sig_key, case_id, document_id):
    """Crops cut from the original in memory, encrypted with a preview written by the module's S3CropStore
    (encrypt=True, the readable PNG is never written). Returns (signatures.json entries, [(page, png)])."""
    if not items:
        return [], []
    plain = {}
    store = adapters.crop_store(aws.s3, aws.settings.bucket, provider,
                                lambda case, doc, sig, png: plain.__setitem__(sig, png))
    try:
        found = adapters.sign_crops(data, items, case_id, document_id, store)
    except Exception as error:  # noqa: BLE001 - KMS, S3 or rendering: nothing readable was written either way
        log.error("%s/%s: encrypting the signature crops failed: %s", case_id, document_id, type(error).__name__)
        raise RedactionError("CROP_ENCRYPTION_FAILED") from None
    if stored and ([(s["signature_id"], s["page"]) for s in found]
                   != [(i.get("signature_id"), i["page"]) for i in items]):
        raise RedactionError("STORED_SIGNATURES_MISMATCH")  # the ids would not match the findings made elsewhere
    entries = []
    for number, sig in enumerate(found):
        if not (sig.get("crop_encrypted") is True and str(sig.get("crop_s3_key", "")).endswith(".png.enc")):
            raise RedactionError("CROP_NOT_ENCRYPTED")
        base = {k: v for k, v in (items[number] if stored else {}).items() if k not in ("crop_url", "crop_source")}
        entry = {**sig, **base} if stored else dict(sig)
        entry.update(crop_s3_key=sig["crop_s3_key"], crop_encrypted=True,
                     preview_s3_key=sig["crop_s3_key"][:-len(".png.enc")] + ".preview.png",
                     phash=base.get("phash") or sig.get("phash"))
        entry["copy_suspicion"] = (base.get("copy_suspicion") if stored and base.get("copy_suspicion") else
                                   {"level": "not_checked", "matches": []})
        entry.pop("crop_url", None)
        entries.append(entry)
    crops = [(sig["page"], plain[sig["signature_id"]]) for sig in found]
    return entries, crops


# --- helpers for a document that reuses the analysis of an identical one (v-dedup) ---------------------------

def reuse_signature_entries(entries, source_case_id, source_document_id):
    """signatures.json entries for a document whose analysis is reused from another one: `crop_s3_key` and
    `preview_s3_key` keep pointing to the SOURCE document's encrypted crop, and `crop_source` names the context
    the crop is bound to (the encryption is tied to case/document/signature of the source), so that the reveal
    decrypts with that context. A source entry that already has `crop_source` keeps it (chains stay one hop)."""
    out = []
    for entry in entries:
        entry = {k: v for k, v in entry.items() if k != "crop_url"}
        crop = entry.get("crop_s3_key")
        if crop:
            if not (entry.get("crop_encrypted") is True and crop.endswith(".png.enc")):
                raise ValueError("SOURCE_CROP_NOT_ENCRYPTED")  # a readable crop is never shared with another document
            entry.setdefault("preview_s3_key", crop[:-len(".png.enc")] + ".preview.png")
            entry.setdefault("crop_source", {"case_id": source_case_id, "document_id": source_document_id,
                                             "signature_id": entry["signature_id"]})
        out.append(entry)
    return out


def finish_reuse(aws, row, origin, original_sha256):
    """After `dedup.reuse.reuse_analysis` copied the analysis of `origin` (its analysis row) into `row`: the
    document gets its own masked copy, `original_sha256` and `redacted_s3_key`, and the copied signatures.json
    entries get `crop_source` / `preview_s3_key` (see `reuse_signature_entries`). Entries of a signatures.json that
    was already there (kept, made elsewhere) are left alone. Raises on anything unexpected: the caller then
    processes the document normally."""
    case_id, document_id = row["case_id"], row["document_id"]
    source_case, source_doc = origin["case_id"], origin["document_id"]
    row["redacted_s3_key"] = copy_redacted(aws, source_case, source_doc, case_id, document_id)
    row["original_sha256"] = original_sha256
    key = row.get("signatures_s3_key")
    if not key:
        return
    raw = aws.get_bytes_or_none(key)
    body = json.loads(raw) if raw is not None else None
    source_prefix = _prefix(source_case, source_doc) + "signatures/"
    if not body or not any(str(s.get("crop_s3_key", "")).startswith(source_prefix) for s in body.get("signatures", [])):
        return
    body["signatures"] = reuse_signature_entries(body["signatures"], source_case, source_doc)
    aws.put_bytes(key, json.dumps(body, ensure_ascii=False).encode(), "application/json")


def copy_redacted(aws, source_case_id, source_document_id, case_id, document_id):
    """Server-side copy of the masked PDF of the source document to this document (metadata `original-sha256`,
    `original_size` stay), so that a duplicate has its own `redacted/<document_id>.pdf`. Returns the new key."""
    source, target = redacted_key(source_case_id, source_document_id), redacted_key(case_id, document_id)
    aws.s3.copy_object(Bucket=aws.settings.bucket, Key=target, CopySource={"Bucket": aws.settings.bucket, "Key": source},
                       MetadataDirective="COPY", TaggingDirective="COPY")
    return target
