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
    for folder in (VALIDATOR_AGENT, VALIDATOR_AGENT / "signatures"):
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


def signature_tools():
    """(process_pdf, PrecomputedDetector, mark_copies, iou) of the signature module, for the copy check."""
    return (_load("signature_pipeline.pipeline", "process_pdf"), _load("signature_pipeline.detect", "PrecomputedDetector"),
            _load("signature_pipeline.copycheck", "mark_copies"), _load("signature_pipeline.detect", "iou"))
