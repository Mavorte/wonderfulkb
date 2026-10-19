"""Interface from be-validator-agent/docs/validator-agent-storage.md: detect_signatures(pdf_path, ocr_text_blocks=None) -> list[dict]."""
from .detect import TextractDetector, default_detector
from .pipeline import process_pdf


def detect_signatures(pdf_path, ocr_text_blocks=None, detector=None, case_id="local", document_id=None,
                      crop_store=None):
    """Signatures of one PDF as dicts of `Signature` (OpenAPI), without `crop_url`.

    `detector` defaults to Textract + embedded images + label-anchored ink (`default_detector`); pass `PrecomputedDetector(items)` to reuse findings of
    be-document-processing. Copy suspicion needs the other documents of the case, so it stays `none` here;
    use `process_case` for that.
    """
    detector = detector or default_detector(TextractDetector())
    sigs = process_pdf(pdf_path, detector, case_id, document_id, crop_store, ocr_text_blocks)
    return [s.to_api(with_crop_url=False) for s in sigs]
