import math
import random
import sys
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from signature_pipeline.models import Detection  # noqa: E402

# The built-in Helvetica has no Czech letters (ř, ů, ž); a Unicode TrueType font is needed for realistic text.
FONT = next((p for p in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf") if Path(p).exists()), None)


def text(page, point, value, fontsize=10):
    if FONT:
        page.insert_text(point, value, fontsize=fontsize, fontname="cz", fontfile=FONT)
    else:
        pytest.skip("no Unicode TrueType font available")


def scribble(seed, n=60):
    """A smooth random stroke in the unit square, stands in for a handwritten signature."""
    rnd = random.Random(seed)
    pts, x, y, a = [], 0.05, 0.5, 0.0
    for i in range(n):
        a += rnd.uniform(-1.4, 1.4)
        x = min(0.95, max(0.05, x + 0.035 * math.cos(a) + 0.012))
        y = min(0.9, max(0.1, y + 0.09 * math.sin(a)))
        pts.append((x, y))
    return pts


def draw_scribble(page, seed, rect, width=1.4):
    shape = page.new_shape()
    pts = [pymupdf.Point(rect.x0 + x * rect.width, rect.y0 + y * rect.height) for x, y in scribble(seed)]
    shape.draw_polyline(pts)
    shape.finish(color=(0, 0, 0.4), width=width, closePath=False)
    shape.commit()


def rel(page, rect):
    r = page.rect
    return [(rect.x0 - r.x0) / r.width, (rect.y0 - r.y0) / r.height,
            (rect.x1 - r.x0) / r.width, (rect.y1 - r.y0) / r.height]


class FakeDetector:
    """Returns prepared detections, like Textract would."""

    def __init__(self, by_page):
        self.by_page = by_page

    def detect(self, doc):
        return [Detection(p, bbox, "textract", 40.0) for p, boxes in self.by_page.items() for bbox in boxes]


def make_contract(seeds, scale=1.0, offset=(0, 0)):
    """One A4 page with a two-column signature table. Returns (pdf bytes, [rel bbox left, rel bbox right])."""
    doc = pymupdf.open()
    page = doc.new_page()
    text(page, (60, 90), "Smlouva o úvěru. Dlužník se zavazuje splácet dohodnuté splátky.", 10)
    text(page, (60, 600), "Poskytovatel financování:", 10)
    text(page, (320, 600), "Příjemce financování:", 10)
    text(page, (60, 622), "SG Equipment Finance Czech Republic s.r.o.", 9)
    boxes = []
    for i, (x, seed) in enumerate(zip((60, 320), seeds)):
        rect = pymupdf.Rect(x + 10 + offset[0], 650 + offset[1], x + 10 + 150 * scale + offset[0], 650 + 60 * scale + offset[1])
        draw_scribble(page, seed, rect)
        text(page, (x, 722), "..............................", 10)
        text(page, (x, 736), "Podpis", 9)
        boxes.append(rel(page, rect))
    return doc.tobytes(), boxes


@pytest.fixture
def contract():
    return make_contract((1, 2))
