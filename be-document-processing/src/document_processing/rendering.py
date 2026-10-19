from io import BytesIO
import warnings

import pymupdf as fitz
from PIL import Image, ImageOps


class InvalidDocument(ValueError):
    pass


def open_document(body, content_type, max_pages=50):
    """Inspect actual bytes, not filename; images share PDF display coordinates."""
    try:
        if content_type == "application/pdf":
            if not body.startswith(b"%PDF-"):
                raise InvalidDocument("CONTENT_TYPE_MISMATCH")
            document = fitz.open(stream=body, filetype="pdf")
            if document.needs_pass:
                document.close()
                raise InvalidDocument("ENCRYPTED_PDF")
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(body)) as image:
                    expected = "PNG" if content_type == "image/png" else "JPEG"
                    if image.format != expected:
                        raise InvalidDocument("CONTENT_TYPE_MISMATCH")
                    if image.width * image.height > 40_000_000:
                        raise InvalidDocument("IMAGE_TOO_LARGE")
                    image = ImageOps.exif_transpose(image).convert("RGB")
                    png = BytesIO()
                    image.save(png, format="PNG")
            source = fitz.open(stream=png.getvalue(), filetype="png")
            try:
                document = fitz.open(stream=source.convert_to_pdf(), filetype="pdf")
            finally:
                source.close()
        if not 1 <= len(document) <= max_pages:
            document.close()
            raise InvalidDocument("PAGE_LIMIT_EXCEEDED")
        if any(p.rect.width < 1 or p.rect.height < 1 or p.rect.width * p.rect.height > 30_000_000 for p in document):
            document.close()
            raise InvalidDocument("PAGE_DIMENSIONS_INVALID")
        return document
    except InvalidDocument:
        raise
    except Exception as error:
        raise InvalidDocument("INVALID_DOCUMENT") from error


def render_page(page):
    # Bound memory for unusually large sheets. No hidden PDF text enters vision OCR.
    scale = min(200 / 72, 2400 / max(page.rect.width, page.rect.height))
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    return pixmap.tobytes("png"), pixmap.width, pixmap.height


def normalize_box(rect, width, height):
    x0, y0, x1, y1 = rect
    return [round(max(0, min(1, x0 / width)), 6), round(max(0, min(1, y0 / height)), 6),
            round(max(0, min(1, x1 / width)), 6), round(max(0, min(1, y1 / height)), 6)]
