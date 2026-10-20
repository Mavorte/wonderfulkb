import sys
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[2]))  # classify/ (taxonomie dokumentů, llm)

# Vestavěná Helvetica nemá česká písmena, potřeba je Unicode TrueType (jako v testech podpisů).
_DIRS = ("/System/Library/Fonts/Supplemental", "/Library/Fonts", "/usr/share/fonts/truetype/dejavu")
FONT = next((f"{d}/{n}" for d in _DIRS for n in ("Arial.ttf", "DejaVuSans.ttf") if Path(f"{d}/{n}").exists()), None)
BOLD = next((f"{d}/{n}" for d in _DIRS for n in ("Arial Bold.ttf", "DejaVuSans-Bold.ttf") if Path(f"{d}/{n}").exists()),
            None)


def text(page, point, value, size=10, bold=False):
    font = BOLD if bold else FONT
    if not font:
        pytest.skip("no Unicode TrueType font available")
    page.insert_text(point, value, fontsize=size, fontname="czb" if bold else "cz", fontfile=font)


def hline(page, y, x0=40, x1=555):
    page.draw_line((x0, y), (x1, y), color=(0.5, 0.5, 0.5), width=0.6)


@pytest.fixture
def new_doc():
    docs = []

    def make():
        doc = pymupdf.open()
        docs.append(doc)
        return doc

    yield make
    for doc in docs:
        doc.close()
