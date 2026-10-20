"""run_document / run_case: PDF in S3 -> text, pages, classification, vectors, one row of analysis."""
import dataclasses
import hashlib
import json
import logging
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from . import adapters, pdf as pdfmod, redaction_step
from .aws import Aws
from .config import PIPELINE_VERSION, STEPS, Settings
from .vision import MantleVision, VisionError, split_label_reply
from document_processing.audit.audit_listener import ExecutionAudit, from_env

log = logging.getLogger("pipeline")
DOC_NAMESPACE = uuid.UUID("5d3f0a52-7c1e-4a8b-9b36-6f1c2e0d7a11")  # same as the ingest service


class DocumentNotFound(LookupError):
    pass


@dataclass
class Options:
    settings: Settings = field(default_factory=Settings)
    vision: object = None          # anything with transcribe(png) -> str; default MantleVision
    no_vision: bool = False        # scans are reported as failed pages instead of calling Bedrock
    force_vision: bool = False     # transcribe every page visually (comparison, bad text layers)
    defer_copy_check: bool = False  # batches run the copy check once per case instead of after each document
    resume: bool = False           # leave documents alone whose row is completed by this pipeline version
    reuse: bool = field(default_factory=lambda: os.environ.get("PIPELINE_NO_REUSE", "") not in ("1", "true"))
    # reuse: take the finished analysis of the same content (SHA-256) from another case instead of calling models again
    aws: Aws = None
    key_provider: object = None    # signature_privacy KeyProvider for the crops; default: PRIVACY_KMS_KEY_ID / WKB_LOCAL_MASTER_KEY
    signature_detector: object = None  # anything with detect(pymupdf doc) -> [Detection]; default: Textract chain
    audit_listener_factory: object = from_env  # dependency only; execution identity stays local to each call

    def get_aws(self):
        if self.aws is None:
            self.aws = Aws(self.settings)
        return self.aws

    def get_vision(self):
        if self.vision is None:
            self.vision = MantleVision(self.settings)
        return self.vision


@dataclass
class Source:
    """Direct S3 mode: a sample PDF outside the ingest flow."""
    key: str
    title: str = None


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def analysis_prefix(case_id, document_id):
    return f"cases/{case_id}/analysis/{document_id}/"


def derive_document_id(case_id, data):
    return str(uuid.uuid5(DOC_NAMESPACE, f"{case_id}:{hashlib.sha256(data).hexdigest()}"))


def _row(case_id, document_id, **attrs):
    row = {"case_id": case_id, "document_id": document_id, "pipeline_version": PIPELINE_VERSION, "updated_at": now()}
    row.update({k: v for k, v in attrs.items() if v is not None})
    return row


def _put_row(aws, row):
    aws.analysis.put_item(Item=row)  # whole-item overwrite: a rerun replaces the previous row


def _mark(aws, case_id, document_id, status, **new_row):
    """Move a row to `status`. An existing row keeps its other attributes (a verified label, the last good
    result) until the final put_item; a missing row is created with the attributes in `new_row`."""
    key = {"case_id": case_id, "document_id": document_id}
    try:
        aws.analysis.update_item(Key=key, ConditionExpression="attribute_exists(case_id)",
                                 UpdateExpression="SET processing_status = :s, updated_at = :t, pipeline_version = :v",
                                 ExpressionAttributeValues={":s": status, ":t": now(), ":v": PIPELINE_VERSION})
    except aws.analysis.meta.client.exceptions.ConditionalCheckFailedException:
        _put_row(aws, _row(case_id, document_id, page_count=0, processing_status=status, label_status="predicted",
                           description="", **new_row))


def fallback_description(text, limit=240):
    flat = " ".join(text.replace("\f", "\n").split())
    return flat[:limit] if flat else "(dokument bez čitelného textu)"


def is_done(row, settings=None):
    """Completed by this pipeline version; with redaction on (`settings.redact`) also only when the row has the
    masked copy: a document processed before the redaction step existed is not done."""
    done = bool(row) and row.get("processing_status") == "completed" and row.get("pipeline_version") == PIPELINE_VERSION
    return done and not (settings is not None and settings.redact and not row.get("redacted_s3_key"))


def _resolve(aws, case_id, document_id):
    """(s3_key, title) of the original from wonderfulkb-uw-documents."""
    item = aws.documents.get_item(Key={"case_id": case_id, "document_id": document_id}).get("Item")
    if not item:
        raise DocumentNotFound(f"{case_id}/{document_id} is not in {aws.settings.documents_table}")
    key = item.get("s3_key") or f"cases/{case_id}/original/{document_id}.pdf"
    return key, item.get("filename") or document_id


LABEL_CONTEXT_CHARS = 20000


def label_tools_for(options, pages, previous):
    """Prompt tools when the label can come out of the one visual call that reads the document: a single-page scan.
    Multi-page scans (one call per page saw a single page: a 4-page protocol got `jine`) and mixed documents get one
    classify_document call over the whole text after assembly, like documents with a text layer."""
    content = [p for p in pages if p.reason != "BLANK_PAGE"]
    if ("classify" in options.settings.skip or options.no_vision or (previous or {}).get("label_status") == "verified"
            or len(content) != 1 or not content[0].needs_vision):
        return None
    try:
        return adapters.label_tools()
    except adapters.StepUnavailable:
        return None


def transcribe_scans(pages, pdf, options, report, label_tools=None, audit=None):
    """Visual transcription of pages without a usable text layer, cached in S3 per model and page.
    Returns (failed page numbers, label dict from the last visual call or None)."""
    settings, aws = options.settings, options.get_aws()
    failed, label, vision_pages = [], None, [p for p in pages if p.needs_vision]
    labelled = vision_pages[-1].number if label_tools and vision_pages else None
    for page in vision_pages:
        page_started = time.monotonic()
        if options.no_vision:
            failed.append(page.number)
            report["pages"][page.number - 1].update(method="failed", error="VISION_DISABLED")
            if audit is not None:
                audit.emit("PageFailed", stage="page_transcription", page_number=page.number,
                           error_code="PAGE_TRANSCRIPTION_FAILED", duration_ms=(time.monotonic() - page_started) * 1000)
            continue
        if len(vision_pages) > settings.max_vision_pages and page.number > settings.max_vision_pages:
            failed.append(page.number)
            report["pages"][page.number - 1].update(method="failed", error="TOO_MANY_PAGES_FOR_VISION")
            if audit is not None:
                audit.emit("PageFailed", stage="page_transcription", page_number=page.number,
                           error_code="PAGE_TRANSCRIPTION_FAILED", duration_ms=(time.monotonic() - page_started) * 1000)
            continue
        ask_label = page.number == labelled
        try:
            suffix = "labeled.txt" if ask_label else "txt"
            # a transcript cached from a readable render must not stand in for the masked one: separate folder
            masked = "redacted/" if report.get("redacted") else ""
            cache_key = f"{report['prefix']}vision/{settings.vision_model}/{masked}{page.number}.{suffix}"
            raw = aws.get_bytes_or_none(cache_key)
            if raw is not None:
                raw = raw.decode("utf-8")
                report["pages"][page.number - 1]["cached"] = True
            else:
                png = pdfmod.render_png(pdf, page.number - 1, settings.vision_dpi, settings.max_pixels)
                request = None
                if ask_label:
                    section, schema, _ = label_tools
                    context = "\f".join(p.text for p in pages[:page.number - 1])
                    request = {"section": section, "schema": schema, "pages": len(pages),
                               "context": context[:LABEL_CONTEXT_CHARS]}
                if audit is not None:
                    audit.emit("StepStarted", stage="page_transcription", page_number=page.number)
                raw = options.get_vision().transcribe(png, label=request)
                aws.put_bytes(cache_key, raw.encode("utf-8"), "text/plain; charset=utf-8")
                report["vision_calls"] += 1
            if ask_label:
                page.text, data = split_label_reply(raw)
                if data is not None:
                    label = label_tools[2](data)
            else:
                page.text = raw
            report["pages"][page.number - 1].update(method="vision", chars=len(page.text))
            if audit is not None:
                if report["pages"][page.number - 1].get("cached"):
                    audit.emit("PageCacheReused", stage="page_transcription", page_number=page.number,
                               cached_status="completed", cached_method="vision", cached_model=settings.vision_model)
                else:
                    audit.emit("PageCompleted", stage="page_transcription", page_number=page.number,
                               method="vision", model=settings.vision_model,
                               duration_ms=(time.monotonic() - page_started) * 1000)
        except Exception as error:  # noqa: BLE001 - one bad page must not lose the document
            code = error.code if isinstance(error, VisionError) else type(error).__name__
            log.warning("page %s: visual transcription failed: %s", page.number, code)
            page.text = ""
            failed.append(page.number)
            report["pages"][page.number - 1].update(method="failed", error=code)
            if audit is not None:
                audit.emit("PageFailed", stage="page_transcription", page_number=page.number,
                           error_code="PAGE_TRANSCRIPTION_FAILED", duration_ms=(time.monotonic() - page_started) * 1000)
    return failed, label


def _step(report, name, function):
    """Run one downstream step; its failure degrades the document to `partial`, never loses the text."""
    started = time.monotonic()
    try:
        value = function()
        report["steps"][name] = {"status": "ok", "seconds": round(time.monotonic() - started, 2)}
        return value
    except adapters.StepUnavailable as error:
        report["steps"][name] = {"status": "unavailable", "error": str(error)}
    except Exception as error:  # noqa: BLE001
        report["steps"][name] = {"status": "failed", "error": f"{type(error).__name__}: {error}"}
    return None


def run_document(case_id, document_id=None, *, source=None, options=None, execution_context=None,
                 audit_listener_factory=None):
    """Process one document and return the analysis row (also written to DynamoDB).

    Raises DocumentNotFound when the document is unknown; every other failure ends as processing_status
    `failed` / `partial` in the row, with details in analysis/<document_id>/run.json."""
    options = options or Options()
    audit = ExecutionAudit(execution_context, audit_listener_factory or options.audit_listener_factory)
    if execution_context is not None and (execution_context.case_id != case_id or
                                          execution_context.document_id != document_id):
        raise ValueError("execution context document mismatch")
    settings, aws = options.settings, options.get_aws()
    started = time.monotonic()
    source_started = time.monotonic()
    audit.emit("StepStarted", stage="source_validation")
    if document_id is None and source is None:
        raise ValueError("document_id is required unless a direct S3 source is given")
    if source is not None:
        key, title = source.key, source.title or source.key.rsplit("/", 1)[-1]
    else:
        key, title = _resolve(aws, case_id, document_id)

    def begin(document_id):
        previous = aws.analysis.get_item(Key={"case_id": case_id, "document_id": document_id}).get("Item")
        if options.resume and is_done(previous, settings):
            return previous, True
        _mark(aws, case_id, document_id, "processing", title=title)
        return previous, False

    previous, done = begin(document_id) if document_id else (None, False)
    if done:
        return previous
    try:
        data = aws.get_bytes(key)
    except Exception as error:  # noqa: BLE001
        audit.emit("StepFailed", stage="source_validation", error_code="SOURCE_VALIDATION_FAILED",
                   duration_ms=(time.monotonic() - source_started) * 1000)
        return _fail(aws, case_id, document_id, title, f"DOWNLOAD_FAILED: {type(error).__name__}", audit=audit)
    if len(data) > settings.max_pdf_bytes:
        audit.emit("StepFailed", stage="source_validation", error_code="SOURCE_VALIDATION_FAILED",
                   duration_ms=(time.monotonic() - source_started) * 1000)
        return _fail(aws, case_id, document_id, title, "PDF_TOO_LARGE", audit=audit)
    if not document_id:
        document_id = derive_document_id(case_id, data)
        previous, done = begin(document_id)
        if done:
            return previous

    prefix = analysis_prefix(case_id, document_id)
    report = {"case_id": case_id, "document_id": document_id, "source_key": key, "prefix": prefix,
              "pipeline_version": PIPELINE_VERSION, "model": settings.vision_model, "started_at": now(),
              "vision_calls": 0, "pages": [], "steps": {}}
    sha256 = hashlib.sha256(data).hexdigest()
    reused = _try_reuse(options, report, case_id, document_id, title, sha256, previous)
    if reused is not None:
        return _finish_reused(options, report, reused, started, source is None, sha256, audit=audit)
    redaction = None
    if settings.redact:
        # the readable original goes no further than this step: everything below reads the masked copy
        try:
            redaction = redaction_step.run(options, case_id, document_id, key, data)
        except redaction_step.RedactionError as error:
            audit.emit("StepFailed", stage="source_validation", error_code="SOURCE_VALIDATION_FAILED",
                       duration_ms=(time.monotonic() - source_started) * 1000)
            return _fail(aws, case_id, document_id, title, error.code, audit=audit)
        data = redaction.redacted
        report["redaction"] = redaction.info
        report["redacted"] = True
    else:
        log.warning("%s/%s: PIPELINE_REDACT is off, the readable original feeds pages, text and vectors "
                    "(debugging only, never for real data)", case_id, document_id)
        report["redaction"] = {"status": "disabled"}
    try:
        pdf = pdfmod.open_pdf(data)
    except pdfmod.InvalidPdf as error:
        audit.emit("StepFailed", stage="source_validation", error_code="SOURCE_VALIDATION_FAILED",
                   duration_ms=(time.monotonic() - source_started) * 1000)
        return _fail(aws, case_id, document_id, title, str(error), audit=audit)
    audit.emit("StepFinished", stage="source_validation", duration_ms=(time.monotonic() - source_started) * 1000)
    extraction_started = time.monotonic()
    audit.emit("StepStarted", stage="extraction")
    try:
        pages = pdfmod.extract_pages(pdf, data)
        if options.force_vision:
            for page in pages:
                if page.reason != "BLANK_PAGE":
                    page.needs_vision, page.reason = True, "VISUAL_TRANSCRIPTION_REQUESTED"
        report["pages"] = [{"page": p.number, "method": "vision_pending" if p.needs_vision else
                            ("blank" if p.reason == "BLANK_PAGE" else "text_layer"),
                            "reason": p.reason, "chars": len(p.text)} for p in pages]
        vision_label = None
        for page in pages:
            if not page.needs_vision:
                audit.emit("PageCompleted", stage="page_transcription", page_number=page.number, method="native")
        failed, vision_label = transcribe_scans(pages, pdf, options, report, label_tools_for(options, pages, previous), audit=audit)
        pngs = [pdfmod.render_png(pdf, i, settings.page_dpi, settings.max_pixels) for i in range(len(pdf))]
    except Exception as error:  # noqa: BLE001
        pdf.close()
        audit.emit("StepFailed", stage="extraction", error_code="EXTRACTION_FAILED",
                   duration_ms=(time.monotonic() - extraction_started) * 1000)
        return _fail(aws, case_id, document_id, title, f"EXTRACTION_FAILED: {type(error).__name__}: {error}", audit=audit)
    pdf.close()
    audit.emit("StepFinished", stage="extraction", duration_ms=(time.monotonic() - extraction_started) * 1000)

    text = "\f".join(p.text for p in pages)
    text_key = prefix + "text.txt"
    aws.put_bytes(text_key, text.encode("utf-8"), "text/plain; charset=utf-8")
    for number, png in enumerate(pngs, start=1):
        aws.put_bytes(f"{prefix}pages/{number}.png", png, "image/png")

    row = _row(case_id, document_id, title=title, page_count=len(pages), text_s3_key=text_key,
               label_status="predicted", description=fallback_description(text))
    if failed:
        row["pages_failed"] = set(failed)
    _classify(options, report, row, previous, text, title, len(pages), vision_label)
    _embed(options, report, row, text, pngs)
    _regions(options, report, row, data, prefix)
    if redaction is None:
        _signatures(options, report, row, case_id, document_id, data, prefix, audit=audit)
    else:
        redaction.apply_to_row(row)
        _embed_signature_crops(options, report, row, redaction)

    # Signature detection, regions and the copy check never change the document status (an empty finding is valid).
    degraded = bool(failed) or any(s["status"] in ("failed", "unavailable") for name, s in report["steps"].items()
                                   if name not in ("signatures", "copy_check", "regions"))
    if failed and len(failed) == len(pages):
        row["processing_status"] = "failed"
    else:
        row["processing_status"] = "partial" if degraded else "completed"
    row["updated_at"] = now()
    if not options.defer_copy_check:
        _copy_check(options, report, case_id)
    report.update(finished_at=row["updated_at"], seconds=round(time.monotonic() - started, 1),
                  processing_status=row["processing_status"], pages_failed=sorted(failed))
    _publish_result(aws, row, prefix + "run.json", json.dumps(report, ensure_ascii=False, indent=1).encode(), audit)
    if source is None:
        _register_hash(report, case_id, document_id, sha256, row.get("label"))
    return row


def _try_reuse(options, report, case_id, document_id, title, sha256, previous):
    """(row, info) from the finished analysis of the same content in another case, or None: process normally.
    Never raises: a missing index, a missing/partial original or any copy error only means no reuse."""
    if not options.reuse:
        report["reuse"] = {"status": "disabled"}
        return None
    aws = options.get_aws()
    try:
        find_source, reuse_analysis = adapters.dedup("find_source"), adapters.dedup("reuse_analysis")
    except adapters.StepUnavailable as error:
        report["reuse"] = {"status": "unavailable", "error": str(error)}
        return None
    try:
        origin = find_source(aws, sha256, case_id)
    except Exception as error:  # noqa: BLE001 - table not deployed, no permission, outage ...
        log.warning("%s/%s: content hash index unavailable (%s), processing normally", case_id, document_id, type(error).__name__)
        report["reuse"] = {"status": "index_unavailable", "error": type(error).__name__}
        return None
    if origin is None:
        report["reuse"] = {"status": "no_source"}
        return None
    if options.settings.redact and not origin.get("redacted_s3_key"):
        # an analysis made from the readable original (pages, crops) is not copied into a masked pipeline
        report["reuse"] = {"status": "source_not_redacted",
                           "from": {"case_id": origin["case_id"], "document_id": origin["document_id"]}}
        return None
    try:
        row, info = reuse_analysis(aws, origin, case_id, document_id, title, skip=options.settings.skip,
                                   previous=previous, pipeline_version=PIPELINE_VERSION, now=now)
        if options.settings.redact:  # own masked copy, hash of the original, crops tied to the source's context
            redaction_step.finish_reuse(aws, row, origin, sha256)
    except Exception as error:  # noqa: BLE001 - NotReusable (incomplete original) or an AWS error: reprocess
        log.warning("%s/%s: cannot reuse %s/%s (%s: %s), processing normally", case_id, document_id,
                    origin["case_id"], origin["document_id"], type(error).__name__, error)
        report["reuse"] = {"status": "fallback", "from": {"case_id": origin["case_id"], "document_id": origin["document_id"]},
                           "reason": f"{type(error).__name__}: {error}"}
        return None
    report["reuse"] = {"status": "reused", **info}
    return row, info


def _finish_reused(options, report, reused, started, register, sha256, audit=None):
    row, info = reused
    aws = options.get_aws()
    case_id, document_id = row["case_id"], row["document_id"]
    report["steps"]["reuse"] = {"status": "ok", "reused_from": info["reused_from"]}
    _regions_for_reused(options, report, row)
    if not options.defer_copy_check:
        _copy_check(options, report, case_id)  # copy_suspicion of the copied signatures is recomputed within this case
    report.update(finished_at=row["updated_at"], seconds=round(time.monotonic() - started, 1),
                  processing_status=row["processing_status"], pages_failed=[])
    _publish_result(aws, row, analysis_prefix(case_id, document_id) + "run.json",
                    json.dumps(report, ensure_ascii=False, indent=1, default=str).encode(), audit,
                    publication_complete=info.get("pages_copied") == row.get("page_count"))
    if register:
        _register_hash(report, case_id, document_id, sha256, row.get("label"))
    return row


def _publish_result(aws, row, key, body, audit, publication_complete=True):
    started = time.monotonic()
    if audit is not None:
        audit.emit("StepStarted", stage="result_publishing")
    try:
        aws.put_bytes(key, body, "application/json")
        _put_row(aws, row)
    except Exception:
        if audit is not None:
            audit.emit("StepFailed", stage="result_publishing", error_code="RESULT_PUBLISHING_FAILED",
                       duration_ms=(time.monotonic() - started) * 1000)
        raise
    if not publication_complete:
        # The reuse owner tolerates missing copies in the business row. That is
        # not proof of a complete owned publication; never upgrade its audit.
        if audit is not None:
            audit.emit("StepFailed", stage="result_publishing", error_code="RESULT_PUBLISHING_FAILED",
                       duration_ms=(time.monotonic() - started) * 1000)
        return
    if audit is not None:
        audit.emit("StepFinished", stage="result_publishing", duration_ms=(time.monotonic() - started) * 1000)
    _published(audit, row)


def _published(audit, row):
    if audit is not None:
        audit.emit("ResultPublished", result_status=row["processing_status"])
        audit.emit("RunFinished", run_status=row["processing_status"])


def _register_hash(report, case_id, document_id, sha256, label):
    """Record the document in the content hash index (with its label). Never changes the document's result."""
    try:
        adapters.dedup("register")(sha256, case_id, document_id, label)
    except Exception as error:  # noqa: BLE001 - index missing or not allowed: the document itself is fine
        log.warning("%s/%s: not registered in the content hash index (%s)", case_id, document_id, type(error).__name__)


def _classify(options, report, row, previous, text, title, page_count, vision_label=None):
    if "classify" in options.settings.skip:
        report["steps"]["classify"] = {"status": "skipped"}
        return
    if previous and previous.get("label_status") == "verified":
        # a human verified the label: reruns must not overwrite it
        for name in ("label", "label_status", "description", "confidence"):
            if name in previous:
                row[name] = previous[name]
        report["steps"]["classify"] = {"status": "ok", "note": "kept verified label"}
        return
    if vision_label and vision_label.get("description"):
        # the scan's own transcription call already returned label, description and confidence
        report["steps"]["classify"] = {"status": "ok", "via": "vision_call"}
        result = vision_label
    else:
        result = _step(report, "classify", lambda: adapters.classify(text, title, page_count))
    if result:
        if result.get("label"):
            row["label"] = result["label"]
        row["label_status"] = result.get("label_status") or "predicted"
        if result.get("description"):
            row["description"] = result["description"]
        if result.get("confidence") is not None:
            row["confidence"] = Decimal(str(round(float(result["confidence"]), 4)))


def _embed(options, report, row, text, pngs):
    if "embed" in options.settings.skip:
        report["steps"]["embed"] = {"status": "skipped"}
        return
    _step(report, "embed", lambda: adapters.write_vectors(row["case_id"], row["document_id"], text, pngs,
                                                         label=row.get("label")))


def _regions(options, report, row, data, prefix):
    """Paragraph regions (bbox, text, label) of the masked PDF into analysis/<doc>/regions.json; the row points to it.
    Never changes the document status. With `--skip regions` an existing regions.json is kept and referenced."""
    aws = options.get_aws()
    key = prefix + "regions.json"
    if "regions" in options.settings.skip:
        if aws.get_bytes_or_none(key) is not None:
            row["regions_s3_key"] = key
        report["steps"]["regions"] = {"status": "skipped"}
        return

    def work():
        result, stats = adapters.regions(data, row.get("label"), use_llm=options.settings.regions_llm)
        body = {"case_id": row["case_id"], "document_id": row["document_id"], "title": row.get("title"),
                "document_label": row.get("label"), **result}
        aws.put_bytes(key, json.dumps(body, ensure_ascii=False).encode(), "application/json")
        row["regions_s3_key"] = key
        return stats

    stats = _step(report, "regions", work)
    if stats is not None:
        report["steps"]["regions"]["labels"] = stats


def _regions_for_reused(options, report, row):
    """A reused analysis whose source had no regions.json: build regions from this document's own masked copy
    (no Textract, no vision; only the labelling model). Without a masked copy the document stays without regions."""
    if row.get("regions_s3_key") or "regions" in options.settings.skip or not row.get("redacted_s3_key"):
        return
    aws = options.get_aws()
    data = aws.get_bytes_or_none(row["redacted_s3_key"])
    if data is not None:
        _regions(options, report, row, data, analysis_prefix(row["case_id"], row["document_id"]))


def regions_case(case_id, options=None, document_ids=None):
    """Only the `regions` step for already processed documents of a case: regions.json from each document's masked
    copy (`redacted_s3_key`), `regions_s3_key` set on the row (UpdateItem, nothing else in the row changes) and
    `steps.regions` in run.json. Text, labels, vectors and signatures are not recomputed. A document without a masked
    copy is skipped (`not_redacted`): regions never come from the readable original. Returns one entry per document."""
    options = options or Options()
    aws = options.get_aws()
    from boto3.dynamodb.conditions import Key
    rows, kwargs = [], {"KeyConditionExpression": Key("case_id").eq(case_id)}
    while True:
        page = aws.analysis.query(**kwargs)
        rows += page["Items"]
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    out = []
    for row in sorted(rows, key=lambda r: (r.get("title", ""), r["document_id"])):
        document_id = row["document_id"]
        if document_ids and document_id not in document_ids:
            continue
        entry = {"document_id": document_id, "title": row.get("title")}
        out.append(entry)
        if row.get("processing_status") not in ("completed", "partial"):
            entry["status"] = "not_ready"
            continue
        if not row.get("redacted_s3_key"):
            entry["status"] = "not_redacted"
            continue
        prefix = analysis_prefix(case_id, document_id)
        report = {"steps": {}}
        work = {k: row[k] for k in ("case_id", "document_id", "title", "label") if k in row}
        data = aws.get_bytes(row["redacted_s3_key"])
        _regions(options, report, work, data, prefix)
        step = report["steps"]["regions"]
        entry.update(status=step["status"], **({"error": step["error"]} if "error" in step else {}),
                     **({"labels": step["labels"]} if "labels" in step else {}))
        if work.get("regions_s3_key"):
            aws.analysis.update_item(Key={"case_id": case_id, "document_id": document_id},
                                     UpdateExpression="SET regions_s3_key = :k", ConditionExpression="attribute_exists(case_id)",
                                     ExpressionAttributeValues={":k": work["regions_s3_key"]})
            entry["regions_s3_key"] = work["regions_s3_key"]
        raw = aws.get_bytes_or_none(prefix + "run.json")
        if raw is not None:
            run = json.loads(raw)
            run.setdefault("steps", {})["regions"] = dict(step, at=now(), via="regions_case")
            aws.put_bytes(prefix + "run.json", json.dumps(run, ensure_ascii=False, indent=1, default=str).encode(),
                          "application/json")
    return out


def _embed_signature_crops(options, report, row, redaction):
    """Embedding of the signature crops, from the readable bytes still held in memory (never read back from S3);
    they are dropped right after, whatever the outcome."""
    try:
        if "embed" in options.settings.skip or not redaction.crops:
            if "embed" in options.settings.skip:
                report["steps"]["signature_embed"] = {"status": "skipped"}
            return
        _step(report, "signature_embed", lambda: adapters.write_signature_vectors(
            row["case_id"], row["document_id"], redaction.crops, label=row.get("label")))
    finally:
        redaction.drop_crops()


def _signatures(options, report, row, case_id, document_id, data, prefix, audit=None):
    aws = options.get_aws()
    key = prefix + "signatures.json"
    if aws.get_bytes_or_none(key) is not None:
        # findings made elsewhere (the signature session's CLI with fallback detectors) are never replaced:
        # the file stays, the row points to it, only the copy check may update `copy_suspicion`
        row["signatures_s3_key"] = key
        report["steps"]["signatures"] = {"status": "skipped" if "signatures" in options.settings.skip else "ok",
                                         "note": "kept existing signatures.json"}
        return
    if "signatures" in options.settings.skip:
        report["steps"]["signatures"] = {"status": "skipped"}
        return

    def work():
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "document.pdf")
            with open(path, "wb") as handle:
                handle.write(data)
            found = adapters.detect_signatures(path, case_id, document_id, aws.s3, aws.settings.bucket)
        # one document cannot see the others: copies were not looked for, which is not the same as `none`
        signatures = [{**{k: v for k, v in dict(item).items() if k != "crop_url"},
                       "copy_suspicion": {"level": "not_checked", "matches": []}} for item in found]
        body = {"case_id": case_id, "document_id": document_id, "signatures": signatures}
        aws.put_bytes(key, json.dumps(body, ensure_ascii=False).encode(), "application/json")
        row["signatures_s3_key"] = key

    started = time.monotonic()
    if audit is not None:
        audit.emit("StepStarted", stage="signature_detection")
    _step(report, "signatures", work)
    if audit is not None:
        if report["steps"]["signatures"]["status"] == "ok":
            audit.emit("StepFinished", stage="signature_detection", duration_ms=(time.monotonic() - started) * 1000)
        else:
            audit.emit("StepFailed", stage="signature_detection", error_code="SIGNATURE_DETECTION_FAILED",
                       duration_ms=(time.monotonic() - started) * 1000)


def _copy_check(options, report, case_id):
    """Copy suspicion across the case, after a document (or, in batches, once after the last one)."""
    if {"signatures", "copy"} & options.settings.skip:
        return None
    from . import copies
    result = _step(report, "copy_check", lambda: copies.copy_case(case_id, options))
    if result is not None:
        report["steps"]["copy_check"]["result"] = result
    return result


def _fail(aws, case_id, document_id, title, reason, audit=None):
    log.error("%s/%s failed: %s", case_id, document_id, reason)
    if not document_id:
        raise RuntimeError(reason)
    _mark(aws, case_id, document_id, "failed", title=title)
    aws.put_bytes(analysis_prefix(case_id, document_id) + "run.json",
                  json.dumps({"processing_status": "failed", "error": reason, "failed_at": now(),
                              "pipeline_version": PIPELINE_VERSION}).encode(), "application/json")
    row = aws.analysis.get_item(Key={"case_id": case_id, "document_id": document_id})["Item"]
    _published(audit, row)
    return row


def _final_copy_check(case_id, options):
    if {"signatures", "copy"} & options.settings.skip:
        return
    from . import copies
    try:
        result = copies.copy_case(case_id, options)
        log.info("copy check %s: %s", case_id, result)
    except Exception as error:  # noqa: BLE001 - never changes the status of any document
        log.warning("copy check %s failed: %s: %s", case_id, type(error).__name__, error)


def run_case(case_id, options=None):
    """Process every document of the case (from wonderfulkb-uw-documents). Returns the rows."""
    options = dataclasses.replace(options or Options(), defer_copy_check=True)
    aws = options.get_aws()
    documents = aws.list_documents(case_id)
    for item in documents:  # the whole case is visible as queued before the slow work starts
        if options.resume and is_done(aws.analysis.get_item(Key={"case_id": case_id, "document_id": item["document_id"]}).get("Item"),
                                      options.settings):
            continue
        _mark(aws, case_id, item["document_id"], "queued", title=item.get("filename", item["document_id"]))
    rows = []
    for item in documents:
        try:
            rows.append(run_document(case_id, item["document_id"], options=options))
        except Exception as error:  # noqa: BLE001 - one broken document must not stop the case
            log.exception("document %s crashed", item["document_id"])
            rows.append(_fail(aws, case_id, item["document_id"], item.get("filename"),
                              f"UNEXPECTED: {type(error).__name__}: {error}"))
    _final_copy_check(case_id, options)
    return rows


def run_prefix(case_id, prefix, options=None):
    """Sample PDFs outside the ingest flow: every PDF directly under the S3 `prefix`, processed under `case_id`.
    document_id is derived like the ingest does (uuid5 of case_id and SHA-256), so ids match other tools' output."""
    options = dataclasses.replace(options or Options(), defer_copy_check=True)
    aws = options.get_aws()
    prefix = prefix if prefix.endswith("/") else prefix + "/"
    keys = []
    for page in aws.s3.get_paginator("list_objects_v2").paginate(Bucket=aws.settings.bucket, Prefix=prefix, Delimiter="/"):
        keys += [o["Key"] for o in page.get("Contents", []) if o["Key"].lower().endswith(".pdf")]
    rows = []
    for key in sorted(keys):
        try:
            rows.append(run_document(case_id, None, source=Source(key), options=options))
        except Exception as error:  # noqa: BLE001
            log.exception("%s crashed", key)
            rows.append({"case_id": case_id, "document_id": None, "title": key.rsplit("/", 1)[-1],
                         "processing_status": "failed", "page_count": 0, "error": f"{type(error).__name__}: {error}"})
    _final_copy_check(case_id, options)
    return rows
