"""Kontrolní vykreslení: strany PDF jako PNG s obdélníky regionů (barva podle `kind`, nahoře `region_id`)."""
from __future__ import annotations

from pathlib import Path

import pymupdf

COLORS = {
    "paragraph": (0.10, 0.45, 0.85),
    "list_item": (0.55, 0.20, 0.75),
    "table_row": (0.05, 0.60, 0.35),
    "heading": (0.85, 0.35, 0.05),
    "page_header": (0.55, 0.55, 0.55),
    "page_footer": (0.55, 0.55, 0.55),
}


def render(pdf_path, result, out_dir, dpi=110):
    """Zapíše `<out_dir>/<název>-p<n>.png` pro každou stranu s textovou vrstvou. Vrací seznam cest."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    paths = []
    try:
        for info in result["pages"]:
            page = doc[info["page"] - 1]
            # Kreslí se do kopie strany v rotovaných souřadnicích: obdélník z normalizovaného bboxu.
            pix = page.get_pixmap(dpi=dpi)
            img = pymupdf.open()
            sheet = img.new_page(width=pix.width, height=pix.height)
            sheet.insert_image(sheet.rect, pixmap=pix)
            for region in (r for r in result["regions"] if r["page"] == info["page"]):
                x0, y0, x1, y1 = region["bbox"]
                rect = pymupdf.Rect(x0 * pix.width, y0 * pix.height, x1 * pix.width, y1 * pix.height)
                color = COLORS.get(region["kind"], (0.9, 0, 0))
                sheet.draw_rect(rect + (-1.5, -1.5, 1.5, 1.5), color=color, width=1.2)
                sheet.insert_text((rect.x0, max(rect.y0 - 2.5, 7)), region["region_id"].split("-")[1],
                                  fontsize=6.5, color=color)
            path = out_dir / f"{Path(pdf_path).stem}-p{info['page']}.png"
            sheet.get_pixmap(dpi=72).save(path)
            img.close()
            paths.append(path)
    finally:
        doc.close()
    return paths
