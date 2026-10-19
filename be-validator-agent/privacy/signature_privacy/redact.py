"""Redakce podpisových oblastí v PDF a PNG: oblast se opravdu odstraní, ne jen překryje.

Vyžaduje PyMuPDF (`pip install --only-binary :all: pymupdf`; na Pythonu 3.14 jen z hotového kola).

Dvě úrovně (`Region.mode`):
- `full`: nález detektoru. Pod rámečkem se odstraní text, vložené obrázky (přepíšou se i pixely) i vektorové
  kresby, plocha se zaplní černě.
- `graphics`: konzervativní zóna (nad popiskem „Podpis“, blok podpisů). Odstraní se obrázky a vektorové
  kresby, které zónu aspoň dotýkají; text zůstane (pro OCR a role), plocha se nevybarvuje.

Redakce nezaručí, že v dokumentu nezůstal žádný podpis: pokrývá jen to, co detektor nalezl a co leží v zónách
(viz be-validator-agent/docs/validator-agent-privacy.md, část o zbytkovém riziku). `verify_redacted` ověřuje, že oblasti
skutečně vyčistil, ne že pokryly všechny podpisy.
"""
import hashlib
import io
import unicodedata
from dataclasses import dataclass

from PIL import Image, ImageDraw

from .errors import PrivacyError

try:
    import pymupdf
except ImportError:  # pragma: no cover
    pymupdf = None

PAD = 0.01                       # relativní okraj kolem nálezu
LABELS = ("podpis", "razítko", "razitko", "signature", "za dlužníka", "za poskytovatele", "za ručitele",
          "za pojistitele", "za dodavatele", "za odběratele", "za kupujícího", "za prodávajícího")
ZONE_ABOVE_MM = 35               # zóna nad popiskem
ZONE_MIN_WIDTH_MM = 70
ZONE_BELOW_MM = 3
MAX_BLOCK_HEIGHT = 0.45          # sjednocený blok vyšší než tento díl strany se nevytváří
MM = 72 / 25.4


def _ascii(text):
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class Region:
    page: int                    # 1-based, jako v `signatures.json`
    bbox: tuple                  # [x0, y0, x1, y1] relativní souřadnice strany
    mode: str = "full"           # "full" | "graphics"
    source: str = "detection"    # "detection" | "label" | "block" (jen informativně)


def _need_pymupdf():
    if pymupdf is None:
        raise PrivacyError("Redakce PDF vyžaduje PyMuPDF")


def _rect(page, bbox, pad=0.0):
    r = page.rect
    x0, y0, x1, y1 = bbox
    return pymupdf.Rect(r.x0 + (x0 - pad) * r.width, r.y0 + (y0 - pad) * r.height,
                        r.x0 + (x1 + pad) * r.width, r.y0 + (y1 + pad) * r.height) & r


def _rel(page, rect):
    r = page.rect
    return (max(0.0, (rect.x0 - r.x0) / r.width), max(0.0, (rect.y0 - r.y0) / r.height),
            min(1.0, (rect.x1 - r.x0) / r.width), min(1.0, (rect.y1 - r.y0) / r.height))


MAX_LABEL_WORDS = 8             # popisek je krátký řádek; „podpis“ uprostřed odstavce zónu nezakládá


def _short_lines(page, labels):
    """Obdélníky krátkých řádků (≤ 8 slov), které obsahují některý z popisků (bez ohledu na diakritiku)."""
    terms = {_ascii(t).lower() for t in labels}
    lines = {}
    for w in page.get_text("words"):
        lines.setdefault((w[5], w[6]), []).append(w)
    for ws in lines.values():
        text = _ascii(" ".join(w[4] for w in ws)).lower()
        if len(ws) <= MAX_LABEL_WORDS and any(t in text for t in terms):
            yield pymupdf.Rect(min(w[0] for w in ws), min(w[1] for w in ws), max(w[2] for w in ws), max(w[3] for w in ws))


def conservative_regions(pdf_bytes: bytes, detections, labels=LABELS) -> list:
    """Z nálezů (`[{"page": 1, "bbox": [...]}, …]`) a popisků v textové vrstvě udělá seznam oblastí.

    Nález: `full` s okrajem. Popisek: zóna `graphics` nad ním (35 mm, šířka aspoň 70 mm). Na stránce s nálezem
    nebo popiskem navíc jeden blok (sjednocení zón a nálezů), pokud není vyšší než 45 % strany."""
    _need_pymupdf()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    out = []
    try:
        by_page = {}
        for d in detections or []:
            by_page.setdefault(int(d["page"]), []).append(d["bbox"])
        for i, page in enumerate(doc, start=1):
            R = page.rect
            zones = []
            for line in _short_lines(page, labels):
                x1 = max(line.x1 + 5 * MM, line.x0 + ZONE_MIN_WIDTH_MM * MM)
                z = pymupdf.Rect(line.x0 - 5 * MM, line.y0 - ZONE_ABOVE_MM * MM, x1, line.y1 + ZONE_BELOW_MM * MM) & R
                if not z.is_empty and _rel(page, z) not in zones:
                    zones.append(_rel(page, z))
            dets = [tuple(b) for b in by_page.get(i, [])]
            for b in dets:
                out.append(Region(i, tuple(b), "full", "detection"))
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


def redact_pdf(pdf_bytes: bytes, regions) -> bytes:
    """Nové PDF s odstraněným obsahem v oblastech. Původní data se nezachovávají (garbage collection, scrub)."""
    _need_pymupdf()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        for mode in ("graphics", "full"):      # nejdřív zóny: jejich odstranění kreseb by jinak smazalo černé vybarvení
            for pno in sorted({r.page for r in regions if r.mode == mode}):
                if not 1 <= pno <= doc.page_count:
                    raise PrivacyError("Oblast mimo rozsah stran")
                page = doc[pno - 1]
                for r in (x for x in regions if x.page == pno and x.mode == mode):
                    rect = _rect(page, r.bbox, PAD if mode == "full" else 0.0)
                    if rect.is_empty:
                        continue
                    if mode == "full":
                        page.add_redact_annot(rect, fill=(0, 0, 0))
                    else:
                        page.add_redact_annot(rect, fill=False)
                if mode == "full":
                    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                                          graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
                                          text=pymupdf.PDF_REDACT_TEXT_REMOVE)
                else:
                    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                                          graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
                                          text=pymupdf.PDF_REDACT_TEXT_NONE)
        doc.scrub(metadata=True, redactions=True, thumbnails=True, embedded_files=True, attached_files=True,
                  hidden_text=False, javascript=True, xml_metadata=True)
        return doc.tobytes(garbage=4, deflate=True, clean=True)
    finally:
        doc.close()


def _stream_hashes(doc):
    out = set()
    for x in range(1, doc.xref_length()):
        try:
            raw = doc.xref_stream_raw(x)
        except Exception:  # noqa: BLE001
            continue
        if raw and len(raw) > 64:
            out.add(hashlib.sha256(raw).hexdigest())
    return out


def verify_redacted(original_pdf: bytes, redacted_pdf: bytes, regions, dpi=100) -> list:
    """Seznam zjištěných problémů (prázdný seznam = redakce oblasti vyčistila).

    Kontroly: (1) žádný datový proud obrázku, který v originále zasahoval do oblasti, nezůstal v novém
    souboru beze změny; (2) v oblasti `full` není text ani kresba a vykreslená plocha je černá; (3) v oblasti
    `graphics` po odstranění textu nezůstal žádný obsah (obrázek ani kresba). Kolaterální změny mimo oblasti
    hlídá `changed_outside`."""
    _need_pymupdf()
    problems = []
    a = pymupdf.open(stream=original_pdf, filetype="pdf")
    b = pymupdf.open(stream=redacted_pdf, filetype="pdf")
    try:
        if a.page_count != b.page_count:
            return ["Různý počet stran"]
        new_hashes = _stream_hashes(b)
        notext = {}
        for r in regions:
            pa, pb = a[r.page - 1], b[r.page - 1]
            rect = _rect(pb, r.bbox, PAD if r.mode == "full" else 0.0)
            for info in pa.get_image_info(xrefs=True):
                if pymupdf.Rect(info["bbox"]).intersects(rect) and info.get("xref"):
                    raw = a.xref_stream_raw(info["xref"])
                    if raw and len(raw) > 64 and hashlib.sha256(raw).hexdigest() in new_hashes:
                        problems.append(f"strana {r.page}: původní obrázek (xref {info['xref']}) zůstal v souboru")
            fills = [_rect(pb, x.bbox, PAD) + (-2, -2, 2, 2) for x in regions if x.page == r.page and x.mode == "full"]
            for d in pb.get_drawings():
                if d.get("fill") == (0.0, 0.0, 0.0) and len(d["items"]) == 1 and d["items"][0][0] == "re" \
                        and any(pymupdf.Rect(d["rect"]) in f for f in fills):
                    continue                                    # černé vybarvení z redakce samotné
                if pymupdf.Rect(d["rect"]).intersects(rect):
                    problems.append(f"strana {r.page}: vektorová kresba zasahuje do oblasti {r.source}")
                    break
            if r.mode == "graphics":
                if r.page not in notext:
                    notext[r.page] = _without_text(b, r.page)
                if not _zone_clean(notext[r.page], rect, fills, dpi):
                    problems.append(f"strana {r.page}: v oblasti {r.source} zůstal obrázek nebo kresba")
            if r.mode == "full":
                if pb.get_text("words", clip=rect):
                    problems.append(f"strana {r.page}: text v oblasti full")
                if not _is_black(pb, rect, dpi):
                    problems.append(f"strana {r.page}: oblast full není černá")
        return problems
    finally:
        a.close()
        b.close()


def changed_outside(original_pdf: bytes, redacted_pdf: bytes, regions, dpi=100, threshold=40) -> dict:
    """{strana: podíl pixelů mimo oblasti, které se vykreslením liší}. Jen strany s nenulovou změnou.

    Redakce kreseb ruší vše, co oblast dotýká (i dlouhé čáry rámečků a tabulek), proto malá změna je očekávaná;
    velká znamená, že oblasti jsou příliš široké."""
    _need_pymupdf()
    a = pymupdf.open(stream=original_pdf, filetype="pdf")
    b = pymupdf.open(stream=redacted_pdf, filetype="pdf")
    out = {}
    try:
        for n in range(a.page_count):
            ra, rb = _render_gray(a[n], dpi), _render_gray(b[n], dpi)
            if ra.shape != rb.shape:
                out[n + 1] = 1.0
                continue
            diff = abs(ra.astype(int) - rb.astype(int)) > threshold
            diff[~_outside_mask(a[n], [r for r in regions if r.page == n + 1], ra.shape, dpi)] = False
            if diff.any():
                out[n + 1] = float(diff.mean())
        return out
    finally:
        a.close()
        b.close()


def _without_text(doc, page_no):
    """Jednostránkový PDF stejné strany bez textu (zůstane jen rastr a kresba), pro kontrolu zóny."""
    tmp = pymupdf.open()
    tmp.insert_pdf(doc, from_page=page_no - 1, to_page=page_no - 1)
    page = tmp[0]
    page.add_redact_annot(page.rect)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                          text=pymupdf.PDF_REDACT_TEXT_REMOVE)
    return page


def _render_gray(page, dpi):
    import numpy as np
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def _is_black(page, rect, dpi):
    pix = page.get_pixmap(dpi=dpi, clip=rect, colorspace=pymupdf.csGRAY, alpha=False)
    import numpy as np
    return float(np.frombuffer(pix.samples, dtype=np.uint8).mean()) < 8


def _zone_clean(page, rect, ignore, dpi):
    """Po odstranění textu je zóna jednobarevná (nic nezbylo). Plochy `ignore` (vybarvení oblastí `full`) se
    nepočítají."""
    import numpy as np
    pix = page.get_pixmap(dpi=dpi, clip=rect, colorspace=pymupdf.csGRAY, alpha=False)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    s = dpi / 72
    for f in ignore:
        a[max(0, int((f.y0 - rect.y0) * s)):max(0, int((f.y1 - rect.y0) * s)),
          max(0, int((f.x0 - rect.x0) * s)):max(0, int((f.x1 - rect.x0) * s))] = 255
    return a.size == 0 or a.std() < 4


def _outside_mask(page, regions, shape, dpi):
    import numpy as np
    s = dpi / 72
    mask = np.ones(shape, dtype=bool)
    for r in regions:
        rect = _rect(page, r.bbox, PAD if r.mode == "full" else 0.0)
        x0, y0 = max(0, int(rect.x0 * s) - 2), max(0, int(rect.y0 * s) - 2)
        mask[y0:int(rect.y1 * s) + 3, x0:int(rect.x1 * s) + 3] = False
    return mask


def redact_png(png_bytes: bytes, boxes, pad=PAD) -> bytes:
    """PNG s černými obdélníky přes relativní boxy `[x0, y0, x1, y1]`. Rastr nemá vrstvy, takže jde o skutečné
    zamazání. Pro stránky vykreslené z už zredigovaného PDF to není potřeba."""
    try:
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    except Exception:  # noqa: BLE001
        raise PrivacyError("Vstup není čitelný obrázek") from None
    w, h = img.size
    d = ImageDraw.Draw(img)
    for x0, y0, x1, y1 in boxes:
        d.rectangle([max(0, (x0 - pad) * w), max(0, (y0 - pad) * h), min(w, (x1 + pad) * w), min(h, (y1 + pad) * h)],
                    fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
