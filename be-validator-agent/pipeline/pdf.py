"""PDF text layer per page (pypdfium2, pypdf as second opinion) and page renders (pypdfium2)."""
import io
import unicodedata
from dataclasses import dataclass

import pypdf
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

RASTER_COVERAGE = 0.55  # an image covering this much of the page makes the text layer untrustworthy


class InvalidPdf(ValueError):
    pass


@dataclass
class PageText:
    number: int          # 1-based
    text: str            # text layer, may be empty
    needs_vision: bool
    reason: str          # why: NATIVE_TEXT_USED, NATIVE_TEXT_MISSING, ..., BLANK_PAGE


def normalize(text):
    return (text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", " ").replace("\x00", "")
            .replace("￾", "").replace("￿", "").strip())


def text_is_usable(text):
    """True when the text layer reads as language: enough characters and words, almost no garbage."""
    meaningful = [c for c in text if not c.isspace()]
    if len(meaningful) < 20 or len(text.split()) < 3:
        return False, "NATIVE_TEXT_MISSING_OR_TOO_SHORT"
    bad = sum(c == "�" or unicodedata.category(c) in ("Cc", "Co", "Cs") for c in meaningful)
    if bad / len(meaningful) > 0.02:
        return False, "NATIVE_TEXT_ENCODING_UNUSABLE"
    return True, "NATIVE_TEXT_USED"


def raster_coverage(page):
    """Share of the page covered by the largest embedded image (0..1)."""
    width, height = page.get_size()
    area = width * height
    if area <= 0:
        return 0.0
    best = 0.0
    try:
        for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE], max_depth=3):
            left, bottom, right, top = obj.get_bounds()
            w, h = max(0.0, min(right, width) - max(left, 0.0)), max(0.0, min(top, height) - max(bottom, 0.0))
            best = max(best, w * h / area)
    except pdfium.PdfiumError:
        return 0.0
    return best


def open_pdf(data):
    if not data.startswith(b"%PDF-"):
        raise InvalidPdf("NOT_A_PDF")
    try:
        return pdfium.PdfDocument(data)
    except pdfium.PdfiumError as error:
        raise InvalidPdf("INVALID_OR_ENCRYPTED_PDF") from error


def _pypdf_texts(data):
    try:
        return [p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(data)).pages]
    except Exception:  # noqa: BLE001 - pypdf raises many types on damaged files; it is only a second opinion
        return None


def extract_pages(pdf, data):
    """Text layer of every page plus the verdict whether the page must go to visual transcription."""
    pages, fallback = [], None
    for index in range(len(pdf)):
        page = pdf[index]
        try:
            text = normalize(page.get_textpage().get_text_bounded())
        except pdfium.PdfiumError:
            text = ""
        usable, reason = text_is_usable(text)
        if not usable:
            if fallback is None:
                fallback = _pypdf_texts(data) or []
            other = normalize(fallback[index]) if index < len(fallback) else ""
            if text_is_usable(other)[0]:
                text, usable, reason = other, True, "NATIVE_TEXT_USED"
        coverage = raster_coverage(page)
        if usable and coverage >= RASTER_COVERAGE:
            # a full-page scan with a thin digital footer or a hidden OCR layer
            usable, reason = False, "PAGE_HAS_DOMINANT_RASTER_IMAGE"
        if not usable and coverage < 0.02 and not text:
            pages.append(PageText(index + 1, "", False, "BLANK_PAGE"))
        else:
            pages.append(PageText(index + 1, text, not usable, reason))
    return pages


def render_png(pdf, index, dpi, max_pixels):
    page = pdf[index]
    width, height = page.get_size()
    scale = min(dpi / 72, max_pixels / max(width, height, 1))
    out = io.BytesIO()
    page.render(scale=scale).to_pil().convert("RGB").save(out, format="PNG", optimize=False)
    return out.getvalue()
