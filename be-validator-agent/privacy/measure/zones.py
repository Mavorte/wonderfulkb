"""Varianta v2 konzervativních zón, vzniklá z prvního měření (viz report.md).

Proč: v generických dokumentech není pod podpisem popisek „Podpis“, ale hlavička role nad blokem („Poskytovatel
financování“, „Příjemce financování“) a pod podpisem tištěné jméno a funkce („jednatel“, „zmocněnec“). Zóna z
popisku „podpis“ (v1) podpis netrefí. v2 přidává:

- zóny podle FUNKCE pod podpisem: 45 mm nad řádkem s funkcí (jméno leží mezi funkcí a podpisem),
- zóny podle ROLE nad podpisem: 55 mm pod řádkem s hlavičkou role,
- širší zóny podle popisku „podpis“ (45 mm nad, 4 mm pod),
- sjednocený blok na straně, jen pokud není vyšší než 45 % strany.

Zóny jsou `graphics`: odstraní obrázky (pixely) a kresby, které je dotýkají; text zůstane.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymupdf  # noqa: E402
from signature_privacy import Region  # noqa: E402
from signature_privacy.redact import LABELS, MAX_BLOCK_HEIGHT, MM, PAD, _ascii, _rel, _short_lines  # noqa: E402

FUNCTIONS = ("jednatel", "zmocnenec", "prokurista", "reditel", "predseda", "clen predstavenstva", "statutarni",
             "opravnena osoba", "zastupce", "vedouci", "majitel", "plna moc", "jednajici")
ROLES = ("poskytovatel", "prijemce", "rucitel", "dodavatel", "odberatel", "kupujici", "prodavajici", "pojistitel",
         "pojistnik", "objednatel", "zhotovitel", "dluznik", "vericel", "zastavce", "pojistene")
ABOVE_FUNC_MM = 45
BELOW_ROLE_MM = 55
ABOVE_LABEL_MM = 45
BELOW_LABEL_MM = 4
SIDE_LEFT_MM = 8
SIDE_WIDTH_MM = 80


def _zone(page, line, up_mm, down_mm, left_mm=SIDE_LEFT_MM, width_mm=SIDE_WIDTH_MM):
    x0 = line.x0 - left_mm * MM
    x1 = max(line.x1 + 5 * MM, line.x0 + width_mm * MM)
    z = pymupdf.Rect(x0, line.y0 - up_mm * MM, x1, line.y1 + down_mm * MM) & page.rect
    return None if z.is_empty else _rel(page, z)


def _anchor_lines(page, terms, ocr, number):
    """Krátké řádky s některým z výrazů. Ze strany bez textové vrstvy (sken) se berou řádky z OCR
    (`ocr.lines(doc, number)`, Textract), jinak z textové vrstvy."""
    if len(page.get_text("words")) >= 5 or ocr is None:
        yield from _short_lines(page, terms)
        return
    wanted = {_ascii(t).lower() for t in terms}
    for l in ocr.lines(page.parent, number):
        text = _ascii(l.text).lower()
        if len(l.text.split()) <= 8 and any(t in text for t in wanted):
            yield pymupdf.Rect(l.x0, l.y0, l.x1, l.y1)


def regions_v2(pdf_bytes, findings, labels=LABELS, ocr=None):
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    out = []
    try:
        by_page = {}
        for d in findings or []:
            by_page.setdefault(int(d["page"]), []).append(d["bbox"])
        for i, page in enumerate(doc, start=1):
            zones = []
            for line in _anchor_lines(page, labels, ocr, i):
                zones.append(_zone(page, line, ABOVE_LABEL_MM, BELOW_LABEL_MM))
            for line in _anchor_lines(page, FUNCTIONS, ocr, i):
                zones.append(_zone(page, line, ABOVE_FUNC_MM, 1))
            for line in _anchor_lines(page, ROLES, ocr, i):
                zones.append(_zone(page, line, 2, BELOW_ROLE_MM))
            zones = [z for k, z in enumerate(zones) if z is not None and z not in zones[:k]]
            dets = [tuple(b) for b in by_page.get(i, [])]
            for b in dets:
                out.append(Region(i, b, "full", "detection"))
            for z in zones:
                out.append(Region(i, z, "graphics", "label"))
            allb = zones + [(max(0, b[0] - PAD), max(0, b[1] - PAD), min(1, b[2] + PAD), min(1, b[3] + PAD)) for b in dets]
            if len(allb) > 1:
                blk = (min(b[0] for b in allb), min(b[1] for b in allb), max(b[2] for b in allb), max(b[3] for b in allb))
                if blk[3] - blk[1] <= MAX_BLOCK_HEIGHT:
                    out.append(Region(i, blk, "graphics", "block"))
        return out
    finally:
        doc.close()
