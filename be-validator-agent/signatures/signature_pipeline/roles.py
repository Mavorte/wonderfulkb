"""Step 2: whose signature is it. Role from the nearest text on the page (until OCR blocks are available).

Two rules, the closer one wins:
- column header: signature tables put the party above the columns ("Poskytovatel financování:" | "Příjemce
  financování:"), the header can be far above the line, so we look up inside the column of the header;
- adjacent label: "Podpis a razítko pojistitele" below, "Ručitel:" above or left of the line.
Only short lines count, so a role word inside a sentence of the contract text is not taken as a label.
"""
import re
import unicodedata

import pymupdf

from .models import TextLine

MAX_WORDS = 8
MAX_HEADER_GAP = 300.0   # points above the signature where a column header is still accepted
MAX_ADJACENT_GAP = 90.0  # points for a label right next to the signature
MIN_DIVIDER = 25.0       # points: shorter vertical strokes are not table borders

# Role -> regex on text without diacritics, lowercase. Order does not matter, the earliest match in the line wins.
ROLE_PATTERNS = {
    "provider": r"poskytovatel|veritel|sg equipment|sgef|komercni banka|banka\b",
    "borrower": r"dluznik|prijemce (financovani|uveru)|pojistnik|prevodce|klient|zadatel",
    "guarantor": r"rucitel",
    "supplier": r"dodavatel|prodavajici|zhotovitel",
    "buyer": r"kupujici|objednatel|odberatel",
    "insurer": r"pojistitel|pojistovn",
}


def fold(text):
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


# Company names say less than a role word ("Poskytovatel", "Ručitel"): a nearby role word wins over them.
WEAK_PATTERN = r"sg equipment|sgef|komercni banka"
WEAK_PENALTY = 40.0


def is_weak(text):
    return bool(re.search(WEAK_PATTERN, fold(text))) and not re.search(
        "|".join(p for r, p in ROLE_PATTERNS.items() if p != ROLE_PATTERNS["provider"]) + r"|poskytovatel|veritel", fold(text))


def role_of(text):
    """(role, matched fragment) of a line, or (None, None). Earliest match in the line wins."""
    if len(text.split()) > MAX_WORDS:
        return None, None
    folded = fold(text)
    best = None
    for role, pattern in ROLE_PATTERNS.items():
        m = re.search(pattern, folded)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), role)
    return (best[1], text.strip()) if best else (None, None)


def page_lines(page):
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = " ".join("".join(span["text"] for span in line["spans"]).split())
            if text:
                x0, y0, x1, y1 = line["bbox"]
                lines.append(TextLine(text, x0, y0, x1, y1))
    return lines


def _gap(a, b):
    """Euclidean gap between two rectangles (0 when they overlap)."""
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5


def _overlaps_x(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > 0


def vertical_dividers(page):
    """Vertical table borders of the page as (x, y0, y1). Rectangle sides count too."""
    out = []
    for d in page.get_drawings():
        for item in d["items"]:
            if item[0] == "l":
                p, q = item[1], item[2]
                if abs(p.x - q.x) < 1.0:
                    out.append((p.x, min(p.y, q.y), max(p.y, q.y)))
            elif item[0] == "re":
                r = item[1]
                if r.width < 2.0:
                    out.append(((r.x0 + r.x1) / 2, r.y0, r.y1))
                else:
                    out += [(r.x0, r.y0, r.y1), (r.x1, r.y0, r.y1)]
    return [v for v in out if v[2] - v[1] >= MIN_DIVIDER]


def _separated(line, sig, dividers):
    """A vertical border that starts at the header row (or above) and runs down at least to the middle of the
    signature, lying between the header's left edge and the signature, puts them in different cells. A border
    that ends where the signature begins is just the edge of the label cell above it."""
    cx = (sig[0] + sig[2]) / 2
    lo, hi = sorted((line.x0, cx))
    return any(lo + 5 < x < hi and y0 <= line.y1 + 3 and y1 >= (sig[1] + sig[3]) / 2 for x, y0, y1 in dividers)


def assign_role(bbox_pts, lines, page_width, dividers=()):
    """bbox_pts: signature [x0, y0, x1, y1] in points. Returns (role, source, evidence) or (None, None, None)."""
    labelled = [(line, *role_of(line.text)) for line in lines]
    labelled = [(line, role, text) for line, role, text in labelled if role]
    if not labelled:
        return None, None, None
    cx = (bbox_pts[0] + bbox_pts[2]) / 2
    best = None  # (distance, role, evidence)
    for line, role, text in labelled:
        rect = (line.x0, line.y0, line.x1, line.y1)
        above = line.y1 <= bbox_pts[1] + 4
        # A header owns the columns from its left edge to the next labelled line on the same row or to a
        # vertical table border; without either it spans the rest of the page (a title above the table).
        right_edge = min([o.x0 for o, _, _ in labelled
                          if o is not line and abs(o.y0 - line.y0) < 10 and o.x0 > line.x1] + [page_width])
        in_column = line.x0 - 25 <= cx <= right_edge and not _separated(line, bbox_pts, dividers)
        gap_v = bbox_pts[1] - line.y1
        if above and in_column and 0 <= gap_v + 4 <= MAX_HEADER_GAP:
            candidate = gap_v + 0.2 * abs(cx - line.x0)
        elif (_gap(rect, bbox_pts) <= MAX_ADJACENT_GAP and not _separated(line, bbox_pts, dividers)
              and not (above and not _overlaps_x(rect, bbox_pts))):
            # Beside or below the line, or straight above it. A label above and off to the side belongs to
            # another column and is handled by the header rule only.
            candidate = _gap(rect, bbox_pts)
        else:
            continue
        # Company names say less than a role word, so a nearby role word wins over them.
        candidate += WEAK_PENALTY if is_weak(text) else 0.0
        if best is None or candidate < best[0]:
            best = (candidate, role, text)
    return (best[1], "nearest_text", best[2]) if best else (None, None, None)


def lines_from_blocks(blocks, page_number, page):
    """TextLines from OCR blocks of one page. Only blocks with a relative bbox are usable; blocks with
    `bbox: null` (the current OCR output) are skipped."""
    r = page.rect
    lines = []
    for b in blocks or []:
        box = b.get("bbox")
        if b.get("page_number", b.get("page")) == page_number and box and b.get("text", "").strip():
            lines.append(TextLine(" ".join(b["text"].split()), r.x0 + box[0] * r.width, r.y0 + box[1] * r.height,
                                  r.x0 + box[2] * r.width, r.y0 + box[3] * r.height))
    return lines


def rel_to_points(bbox, page):
    r = page.rect
    return [r.x0 + bbox[0] * r.width, r.y0 + bbox[1] * r.height,
            r.x0 + bbox[2] * r.width, r.y0 + bbox[3] * r.height]
