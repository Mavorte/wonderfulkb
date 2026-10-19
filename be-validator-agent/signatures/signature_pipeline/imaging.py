"""Rendering, cropping, perceptual hash and ink masks."""
import io

import numpy as np
import pymupdf
from PIL import Image

HASH_SIZE = 32          # DCT input side
HASH_LOW = 8            # low-frequency block -> 64 bits
MASK_SIDE = 64
MIN_INK_PIXELS = 30     # below this a crop is treated as blank


def render_page_png(page, dpi=150):
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return pix.tobytes("png")


def text_free_page(doc, page_index, bboxes, pad=0.02):
    """Single-page copy of the PDF page without the text inside the given relative boxes (images and
    vector graphics stay). Printed dotted lines, "Podpis" and names would otherwise leak into the crop
    used for hashing and make different signatures in the same template look alike.
    """
    clean = pymupdf.open()
    clean.insert_pdf(doc, from_page=page_index, to_page=page_index)
    page = clean[0]
    r = page.rect
    zones = [pymupdf.Rect(r.x0 + (x0 - pad) * r.width, r.y0 + (y0 - pad) * r.height,
                          r.x0 + (x1 + pad) * r.width, r.y0 + (y1 + pad) * r.height) for x0, y0, x1, y1 in bboxes]
    hit = False
    for w in page.get_text("words"):
        if any(pymupdf.Rect(w[:4]).intersects(z) for z in zones):
            page.add_redact_annot(pymupdf.Rect(w[:4]))
            hit = True
    if hit:
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
    return page


def crop_page(page, bbox, dpi=200, pad=0.01):
    """Render a relative bbox of a page to a PIL image (small padding so strokes are not cut)."""
    r = page.rect
    x0, y0, x1, y1 = bbox
    clip = pymupdf.Rect(r.x0 + (x0 - pad) * r.width, r.y0 + (y0 - pad) * r.height,
                        r.x0 + (x1 + pad) * r.width, r.y0 + (y1 + pad) * r.height) & r
    pix = page.get_pixmap(dpi=dpi, clip=clip, alpha=False)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def png_bytes(image):
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


RULE_FRACTION = 0.85    # a row or column that is inked over this share of the crop is a table border, not a stroke


def _drop_rules(ink):
    """Remove table borders that run through the crop (full-width rows, full-height columns)."""
    ink = ink.copy()
    h, w = ink.shape
    ink[ink.sum(axis=1) > RULE_FRACTION * w, :] = False
    ink[:, ink.sum(axis=0) > RULE_FRACTION * h] = False
    return ink


def ink_mask(image):
    """Boolean mask of ink pixels, tightly cropped, or None for a (nearly) blank crop."""
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    background = np.percentile(gray, 90)
    ink = gray < background - 60
    ink = _drop_rules(ink)
    if ink.sum() < MIN_INK_PIXELS:
        return None
    ys, xs = np.where(ink)
    return ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _dct_matrix(n):
    k = np.arange(n)[:, None]
    i = np.arange(n)[None, :]
    m = np.cos(np.pi * (2 * i + 1) * k / (2 * n)) * np.sqrt(2 / n)
    m[0] /= np.sqrt(2)
    return m


_DCT = _dct_matrix(HASH_SIZE)


def _resize(arr, size):
    img = Image.fromarray((arr * 255).astype(np.uint8))
    return np.asarray(img.resize(size, Image.LANCZOS), dtype=np.float32) / 255.0


def phash_and_mask(image):
    """(phash hex 16 chars, normalised ink mask 64x64 bool, aspect ratio w/h) or (None, None, None).

    The hash is computed from the ink-tight crop, so shifts and padding do not change it.
    """
    mask = ink_mask(image)
    if mask is None:
        return None, None, None
    h, w = mask.shape
    ink = mask.astype(np.float32)
    small = _resize(ink, (HASH_SIZE, HASH_SIZE))
    dct = _DCT @ small @ _DCT.T
    low = dct[:HASH_LOW, :HASH_LOW].flatten()
    bits = low[1:] > np.median(low[1:])          # drop DC
    bits = np.concatenate([[False], bits])        # keep 64 bits, DC position fixed to 0
    value = int("".join("1" if b else "0" for b in bits), 2)
    norm = _resize(ink, (MASK_SIDE, MASK_SIDE)) > 0.2
    return f"{value:016x}", norm, w / h


def hamming(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _dilate(mask):
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def mask_similarity(a, b):
    """Dice coefficient of two ink masks with one-pixel tolerance (symmetric)."""
    da, db = _dilate(a), _dilate(b)
    inter = (a & db).sum() + (b & da).sum()
    total = a.sum() + b.sum()
    return float(inter / total) if total else 0.0
