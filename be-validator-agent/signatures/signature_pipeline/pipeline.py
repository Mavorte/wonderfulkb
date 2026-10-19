"""Pipeline: detection -> role -> crop -> perceptual hash -> copy suspicion."""
from pathlib import Path

import pymupdf

from .copycheck import mark_copies
from .imaging import crop_page, phash_and_mask, png_bytes, text_free_page
from .models import Signature
from .roles import assign_role, lines_from_blocks, page_lines, rel_to_points, vertical_dividers


class LocalCropStore:
    """Writes crops under `root/<case_id>/<document_id>/<signature_id>.png`; `crop_url` stays empty."""

    def __init__(self, root):
        self.root = Path(root)

    def save(self, case_id, document_id, signature_id, png):
        path = self.root / case_id / document_id / f"{signature_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png)
        return str(path), None


def process_pdf(source, detector, case_id="local", document_id=None, crop_store=None, ocr_text_blocks=None):
    """Signatures of one PDF (path or bytes). Copy suspicion is filled later by `process_case`.

    Role comes from the text layer, else from OCR blocks that carry a bbox, else from the detector's hint."""
    if isinstance(source, (str, Path)):
        document_id = document_id or Path(source).stem
        doc = pymupdf.open(source)
    else:
        doc = pymupdf.open(stream=source, filetype="pdf")
    document_id = document_id or "document"
    try:
        detections = detector.detect(doc)
        clean = {}  # page number -> page without text near the signatures
        signatures = []
        for number, d in enumerate(detections, start=1):
            page = doc[d.page - 1]
            lines = page_lines(page) or lines_from_blocks(ocr_text_blocks, d.page, page)
            role, role_source, evidence = assign_role(rel_to_points(d.bbox, page), lines, page.rect.width,
                                                      vertical_dividers(page))
            if not role and d.hint and d.hint.get("role") not in (None, "unknown"):
                role, role_source, evidence = d.hint["role"], "nearest_text", d.hint.get("role_evidence")
            sig = Signature(f"sig_{number:02d}", d.page, d.bbox, d.detector, d.score,
                            role or "unknown", role_source, evidence)
            # The human crop keeps the page as it is; the hash is computed from the text-free render.
            crop = crop_page(page, d.bbox)
            if d.page not in clean:
                clean[d.page] = text_free_page(doc, d.page - 1, [x.bbox for x in detections if x.page == d.page])
            sig.phash, sig.mask, sig.aspect = phash_and_mask(crop_page(clean[d.page], d.bbox))
            if crop_store:
                sig.crop_path, sig.crop_url = crop_store.save(case_id, document_id, sig.signature_id, png_bytes(crop))
                if getattr(crop_store, "s3", False):
                    sig.crop_s3_key, sig.crop_encrypted = sig.crop_path, bool(crop_store.encrypt)
            signatures.append(sig)
    finally:
        doc.close()
    return signatures


def process_case(case_id, documents, detector, crop_store=None):
    """documents: {document_id: pdf path or bytes}. Returns {document_id: API response (call 3)}."""
    found = {doc_id: process_pdf(src, detector, case_id, doc_id, crop_store) for doc_id, src in documents.items()}
    mark_copies(found)
    return {doc_id: {"case_id": case_id, "document_id": doc_id, "signatures": [s.to_api() for s in sigs]}
            for doc_id, sigs in found.items()}
