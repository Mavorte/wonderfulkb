"""Thin adapters over the sibling modules classify/, embed/ and the signature module.

Each one imports lazily and raises StepUnavailable with a clear message when the module is not there yet,
so the pipeline can run without them (`--skip` / PIPELINE_SKIP) or report the step as failed."""
import importlib
import os
import sys
from pathlib import Path

VALIDATOR_AGENT = Path(__file__).resolve().parent.parent  # infra/validator-agent


class StepUnavailable(RuntimeError):
    pass


def _ensure_path():
    # classify/ and embed/ live next to pipeline/; make them importable even without the .pth from setup.sh
    # signatures/ holds the package signature_pipeline, so that directory goes on the path too
    # privacy/ holds the package signature_privacy (encryption, redaction)
    for folder in (VALIDATOR_AGENT, VALIDATOR_AGENT / "signatures", VALIDATOR_AGENT / "privacy"):
        if str(folder) not in sys.path:
            sys.path.append(str(folder))


def _load(module, attribute):
    _ensure_path()
    try:
        mod = importlib.import_module(module)
    except ImportError as error:
        raise StepUnavailable(f"module '{module}' is not importable ({error}); "
                              f"expected the sibling module in infra/validator-agent providing {attribute}()") from error
    function = getattr(mod, attribute, None)
    if function is None:
        raise StepUnavailable(f"module '{module}' has no {attribute}() yet")
    return function


def classify(text, title, page_count):
    return _load("classify", "classify_document")(text, title, page_count)


def label_tools():
    """(prompt section, output schema, parse function) for a label returned by the vision call itself."""
    return (_load("classify", "build_label_prompt_section")(), _load("classify", "LABEL_OUTPUT_SCHEMA"),
            _load("classify", "parse_label_output"))


def write_vectors(case_id, document_id, text, page_pngs, label=None):
    return _load("embed", "write_document_vectors")(case_id, document_id, text, page_pngs, label=label)


def detect_signatures(pdf_path, case_id, document_id, s3, bucket):
    """Signatures of one PDF as dicts of the OpenAPI `Signature` (no crop_url). Readable crops are never written
    (privacy decision of 19. 10.): no crop store is passed at all; with PIPELINE_ENCRYPT_CROPS=1 the module's
    S3CropStore writes only encrypted crops (KMS, needs `cryptography`, not verified from here)."""
    detect = _load("signature_pipeline", "detect_signatures")
    store = None
    if os.environ.get("PIPELINE_ENCRYPT_CROPS") == "1":
        store = _load("signature_pipeline.store", "S3CropStore")(s3, bucket, encrypt=True)
    return detect(str(pdf_path), None, case_id=case_id, document_id=document_id, crop_store=store)


def privacy():
    """The `signature_privacy` package (redaction, encryption, preview); needs PyMuPDF and cryptography."""
    _ensure_path()
    try:
        import signature_privacy
    except ImportError as error:
        raise StepUnavailable(f"signature_privacy is not importable ({error}); "
                              f"see infra/validator-agent/privacy/requirements-redact.txt") from error
    return signature_privacy


def signature_detector():
    """Default chain of the signature module: Textract -> embedded images -> ink above the 'Podpis' label."""
    return _load("signature_pipeline.detect", "default_detector")(_load("signature_pipeline.detect", "TextractDetector")())


def detect_boxes(pdf_bytes, detector=None):
    """Findings on the PDF held in memory (no file, no crop): [{page, bbox, detector, detection_score, role,
    role_evidence}] in the order the module numbers them (sig_01, ...). `detector` is anything with detect(doc)."""
    try:
        import pymupdf
    except ImportError as error:
        raise StepUnavailable(f"PyMuPDF is not importable ({error})") from error
    detector = detector or signature_detector()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        found = detector.detect(doc)
    finally:
        doc.close()
    return [{"page": d.page, "bbox": list(d.bbox), "detector": d.detector, "detection_score": d.score,
             "role": (d.hint or {}).get("role"), "role_evidence": (d.hint or {}).get("role_evidence")} for d in found]


def crop_store(s3, bucket, provider, on_plain):
    """The module's S3CropStore in its only allowed form here: encrypted crop + distorted preview; `on_plain`
    receives the readable crop in memory (for the embedding) and nothing readable reaches S3."""
    return _load("signature_pipeline.store", "S3CropStore")(s3, bucket, encrypt=True, provider=provider, on_plain=on_plain)


def sign_crops(pdf_bytes, items, case_id, document_id, store):
    """Role, crop (from `pdf_bytes`, in memory), phash for the given findings; the crop goes through `store`.
    Returns dicts of the OpenAPI `Signature` without crop_url."""
    process_pdf = _load("signature_pipeline.pipeline", "process_pdf")
    precomputed = _load("signature_pipeline.detect", "PrecomputedDetector")
    return [s.to_api(with_crop_url=False) for s in process_pdf(pdf_bytes, precomputed(items), case_id, document_id, store)]


def write_signature_vectors(case_id, document_id, crops, label=None):
    return _load("embed", "write_signature_vectors")(case_id, document_id, crops, label=label)


def dedup(attribute):
    """Funkce z modulu `dedup/` (index hashů a znovupoužití analýzy); modul chybí = StepUnavailable, zpracuje se normálně."""
    module = {"find_source": "dedup.reuse", "reuse_analysis": "dedup.reuse", "register": "dedup.hashindex"}[attribute]
    return _load(module, attribute)


def signature_tools():
    """(process_pdf, PrecomputedDetector, mark_copies, iou) of the signature module, for the copy check."""
    return (_load("signature_pipeline.pipeline", "process_pdf"), _load("signature_pipeline.detect", "PrecomputedDetector"),
            _load("signature_pipeline.copycheck", "mark_copies"), _load("signature_pipeline.detect", "iou"))
