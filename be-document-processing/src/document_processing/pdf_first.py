"""Use visible PDF text first; fall back per page to the configured vision LLM."""
import unicodedata

import pymupdf

from .providers import LocalOcr


def assess_native_text(page):
    text = page.get_text(sort=True)
    meaningful = [c for c in text if not c.isspace()]
    if len(meaningful) < 20 or len(text.split()) < 3:
        return False, "NATIVE_TEXT_MISSING_OR_TOO_SHORT"
    bad = sum(c == "\ufffd" or unicodedata.category(c) in ("Cc", "Co", "Cs") for c in meaningful)
    if bad / len(meaningful) > 0.02:
        return False, "NATIVE_TEXT_ENCODING_UNUSABLE"
    # Rendering mode 3 is invisible text. It can be a stale or adversarial OCR
    # layer and does not establish what the user sees on the page.
    for trace in page.get_texttrace():
        if trace.get("type") == 3 or trace.get("opacity", 1) <= 0.01:
            return False, "NATIVE_TEXT_NOT_VISIBLE"
    area = page.rect.width * page.rect.height
    for image in page.get_image_info():
        image_rect = pymupdf.Rect(image["bbox"]) * page.rotation_matrix
        coverage = (image_rect & page.rect).get_area() / area
        if coverage >= 0.55:
            # A tiny digital footer on top of a full-page scan is not a usable
            # transcription of the document body.
            return False, "PAGE_HAS_DOMINANT_RASTER_IMAGE"
    return True, "NATIVE_TEXT_USED"


class PdfFirstOcr:
    def __init__(self, vision):
        self.vision = vision
        self.native = LocalOcr()
        # Keep the same Bedrock client for the downstream structured extraction.
        self.client = getattr(vision, "client", None)

    def transcribe(self, page, page_number, mode):
        if mode == "auto":
            try:
                usable, reason = assess_native_text(page)
                if usable:
                    result = self.native.transcribe(page, page_number, "auto")
                    result.warnings.append(reason)
                    return result
            except (RuntimeError, ValueError, pymupdf.FileDataError):
                reason = "NATIVE_TEXT_EXTRACTION_FAILED"
        else:
            reason = "VISUAL_TRANSCRIPTION_REQUESTED"
        result = self.vision.transcribe(page, page_number, "visual")
        result.warnings.append(reason)
        return result
