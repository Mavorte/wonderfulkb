"""Segmentace strany PDF s textovou vrstvou na regiony (odstavce, položky výčtu, řádky tabulek, nadpisy).

Staví se z řádků PyMuPDF, ne z jeho bloků: blok občas slije dva sloupce formuláře do jednoho (smlouva SOLOM, levý a
pravý sloupec identifikace stran). Postup na straně:

1. Segmenty: řádek PyMuPDF rozdělený na mezerách mezi spany (víc než ~1,2 výšky řádku), prázdné se zahodí.
2. Spojení na řádku do skupin: popisek končící dvojtečkou (nebo samotná značka výčtu `a)`) + hodnota vpravo na stejné
   výšce (`IČ:` `61061344`), pokud hodnota sama není popisek a není příliš daleko. Svislá čára mezi nimi nevadí.
3. Řádky tabulek: skupiny v jednom pásu mezi vodorovnými čarami kresby strany tvoří region `table_row` (pás bez
   vnitřních čar se dělí na řádky podle výšky, zalomený text buňky zůstává v řádku). Pás s jediným sloupcem je
   orámovaný odstavec. Popisek s hodnotou daleko vpravo (formulář bez čar) je také samostatný `table_row`.
4. Svislé slučování do odstavců: další řádek ve stejném sloupci, s podobnou výškou a mezerou menší než ~0,7 výšky.
   Nový odstavec začíná na značce výčtu (`a)`, `1.`, `•`) a po nadpisu.
5. Záhlaví a zápatí (v `document_regions`): text u horního/dolního okraje, nebo stejný text (čísla nahrazená) v horní
   či dolní části víc stran.

Souřadnice jsou relativní ke straně, jak se vykreslí (s rotací), stejně jako `bbox` podpisů.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf

# Mezera mezi spany jednoho řádku PyMuPDF, od které jde o dva segmenty (násobek výšky řádku).
SPAN_GAP = 1.2
# Svislá mezera mezi řádky, do které jsou ještě jeden odstavec (násobek výšky řádku).
LINE_GAP = 0.7
# Popisek a hodnota na řádku smí být od sebe nejvýš tolik (podíl šířky strany); hodnoty bývají zarovnané vpravo.
LABEL_VALUE_GAP = 0.6
# Pás mezi dvěma vodorovnými čarami vyšší než tohle (body) je rám, ne řádek tabulky.
MAX_ROW_BAND = 90
# Vodorovná čára kratší než tohle (podíl šířky strany) se za hranici řádku tabulky nepočítá.
MIN_RULE = 0.25
# Region se středem v tomto pásu u horního/dolního okraje (podíl výšky) je vždy záhlaví/zápatí.
EDGE = 0.02
# V tomto pásu je záhlaví/zápatí jen text, který se opakuje na víc stranách (formuláře SGEF mají opakované
# záhlaví až ve ~20 % výšky, nad ním pokračuje tabulka z předchozí strany).
MARGIN = 0.25
# Popisek a hodnota dál od sebe než tolik výšek řádku jsou řádek formuláře (samostatný region), ne text odstavce.
TABULAR_GAP = 3.0
# Strana s méně znaky textu nemá použitelnou textovou vrstvu (sken), regiony z ní nevznikají.
MIN_PAGE_CHARS = 20

# Značka výčtu: a) (i) 1. 1) 1.8 2.1.1 • -
LIST_MARKER = re.compile(r"^\s*(?:\(?[a-z]\)|\(?[ivx]{1,4}\)|\d{1,2}[.)]|\d{1,2}(?:\.\d{1,2})+\.?|[•▪◦●\-–])\s+\S")
# Samotná značka výčtu jako vlastní segment („a)“ a text položky o kus vpravo).
BARE_MARKER = re.compile(r"^(?:\(?(?:[a-z]|[ivx]{1,4}|\d{1,2}(?:\.\d{1,2})*)[.)]|\d{1,2}(?:\.\d{1,2})+|[•▪◦●\-–])$")
ARTICLE = re.compile(r"^\s*(?:čl(?:ánek|\.)\s*[\dIVX]+|[IVX]{1,5}\.\s+\S|\d{1,2}\.\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ])")
_WS = re.compile(r"\s+")


@dataclass
class Segment:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    bold: bool
    size: float
    # Hodnota připojená v kroku 2 za popisek/značku (v textu regionu ji od popisku dělí mezera, ne ' | ').
    joined: bool = False

    @property
    def h(self):
        return max(self.y1 - self.y0, 1.0)

    @property
    def rect(self):
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass
class Group:
    """Segmenty jednoho vizuálního řádku spojené v kroku 2 (popisek + hodnota, značka + text položky)."""
    segs: list[Segment]

    x0 = property(lambda self: min(s.x0 for s in self.segs))
    y0 = property(lambda self: min(s.y0 for s in self.segs))
    x1 = property(lambda self: max(s.x1 for s in self.segs))
    y1 = property(lambda self: max(s.y1 for s in self.segs))
    h = property(lambda self: max(self.y1 - self.y0, 1.0))
    text = property(lambda self: " ".join(s.text for s in self.segs))

    @property
    def tabular(self):
        """Popisek a hodnota daleko od sebe: řádek formuláře."""
        return (len(self.segs) >= 2 and _is_label(self.segs[0])
                and self.segs[1].x0 - self.segs[0].x1 > TABULAR_GAP * self.segs[0].h)


@dataclass
class Region:
    kind: str
    lines: list[Segment] = field(default_factory=list)
    # U položky výčtu levý okraj textu za značkou: řádek, který začíná vlevo od něj, už do položky nepatří.
    indent: float | None = None

    @property
    def bbox(self):
        return (min(s.x0 for s in self.lines), min(s.y0 for s in self.lines),
                max(s.x1 for s in self.lines), max(s.y1 for s in self.lines))


def _clean(text):
    return _WS.sub(" ", text.replace(" ", " ")).strip()


def _is_bold(span):
    return bool(span["flags"] & 16) or "bold" in span["font"].lower()


def segments(page):
    """Neprázdné segmenty strany v souřadnicích nerotované strany (body)."""
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            if line["dir"][1] and abs(line["dir"][0]) < 0.9:
                continue  # svislý text (razítka, okraje), do odstavců nepatří
            group = []
            for span in line["spans"]:
                if group:
                    prev = group[-1]
                    h = max(prev["bbox"][3] - prev["bbox"][1], 1.0)
                    if span["bbox"][0] - prev["bbox"][2] > SPAN_GAP * h:
                        out.append(_segment(group))
                        group = []
                group.append(span)
            if group:
                out.append(_segment(group))
    return [s for s in out if s is not None]


def _segment(spans):
    text = _clean("".join(s["text"] for s in spans))
    if not text:
        return None
    visible = [s for s in spans if s["text"].strip()]
    return Segment(min(s["bbox"][0] for s in visible), min(s["bbox"][1] for s in visible),
                   max(s["bbox"][2] for s in visible), max(s["bbox"][3] for s in visible), text,
                   all(_is_bold(s) for s in visible), max(s["size"] for s in visible))


def rules(page):
    """Vodorovné čáry kresby strany jako (y, x0, x1) v bodech nerotované strany (i horní a dolní hrany obdélníků).
    Čáry nakreslené po buňkách se na stejné výšce spojí, teprve pak se krátké zahodí."""
    width = page.mediabox.width or page.rect.width
    pieces = []
    for d in page.get_drawings():
        for item in d["items"]:
            if item[0] == "l":
                p, q = item[1], item[2]
                if abs(p.y - q.y) < 1.0:
                    pieces.append((p.y, min(p.x, q.x), max(p.x, q.x)))
            elif item[0] == "re":
                r = item[1]
                if r.height < 2.0:
                    pieces.append(((r.y0 + r.y1) / 2, r.x0, r.x1))
                elif r.width >= 2.0:
                    pieces += [(r.y0, r.x0, r.x1), (r.y1, r.x0, r.x1)]
    merged = []
    for y, x0, x1 in sorted(pieces, key=lambda t: (round(t[0]), t[1])):
        last = merged[-1] if merged else None
        if last and abs(last[0] - y) < 1.0 and x0 <= last[2] + 2.0:
            merged[-1] = (last[0], last[1], max(last[2], x1))
        else:
            merged.append((y, x0, x1))
    return [h for h in merged if h[2] - h[1] >= MIN_RULE * width]


def _band(item, horizontal):
    """(y nad, y pod) nejbližších vodorovných čar, které skupinu pokrývají vodorovně, nebo None."""
    cx = (item.x0 + item.x1) / 2
    above = [y for y, x0, x1 in horizontal if x0 - 1 <= cx <= x1 + 1 and y <= item.y0 + 1.5]
    below = [y for y, x0, x1 in horizontal if x0 - 1 <= cx <= x1 + 1 and y >= item.y1 - 1.5]
    if not above or not below:
        return None
    top, bottom = max(above), min(below)
    if bottom - top > MAX_ROW_BAND:
        return None
    return round(top, 1), round(bottom, 1)


def _same_row(a, b):
    overlap = min(a.y1, b.y1) - max(a.y0, b.y0)
    return overlap >= 0.5 * min(a.h, b.h)


def _is_label(seg):
    return seg.text.endswith(":")


def _opens_row(seg):
    """Segment, za kterým na stejném řádku pokračuje jeho hodnota: popisek s dvojtečkou nebo samotná značka výčtu."""
    return _is_label(seg) or bool(BARE_MARKER.match(seg.text))


def _join_rows(segs, page_width):
    """Spojí popisek s dvojtečkou (nebo značku výčtu) a hodnotu vpravo na stejném řádku do skupiny. Svislá čára mezi
    nimi nevadí, ve formulářích je hodnota v sousední buňce."""
    segs = sorted(segs, key=lambda s: (s.y0, s.x0))
    used, groups = set(), []
    for i, seg in enumerate(segs):
        if i in used:
            continue
        group = [seg]
        used.add(i)
        while _opens_row(group[-1]):
            last = group[-1]
            candidates = [(j, s) for j, s in enumerate(segs) if j not in used and s.x0 >= last.x1 - 1
                          and _same_row(last, s)]
            if not candidates:
                break
            j, nxt = min(candidates, key=lambda c: c[1].x0)
            if _is_label(nxt) or BARE_MARKER.match(nxt.text) or nxt.x0 - last.x1 > LABEL_VALUE_GAP * page_width:
                break
            nxt.joined = True
            group.append(nxt)
            used.add(j)
        groups.append(Group(group))
    return groups


def _heading(group, median_h):
    if len(group.segs) != 1:
        return False
    seg = group.segs[0]
    text = seg.text
    if len(text) > 90 or text.endswith((".", ",", ";")):
        return False
    letters = [c for c in text if c.isalpha()]
    visible = [c for c in text if not c.isspace()]
    # Částka „1 620 000,00 CZK“ je velkými písmeny, ale nadpis to není: písmena musí převažovat.
    wordy = len(letters) >= 3 and len(letters) >= 0.5 * len(visible)
    caps = wordy and sum(c.isupper() for c in letters) / len(letters) > 0.6
    large = seg.h >= 1.25 * median_h
    return (seg.bold and (bool(ARTICLE.match(text)) or caps or (wordy and text.endswith(":")))) or (large and wordy)


def _continues(region, group):
    """Patří řádek `group` pod odstavec `region`?"""
    if region.kind not in ("paragraph", "list_item"):
        return False
    last = region.lines[-1]
    first = group.segs[0]
    h = min(last.h, first.h)
    if abs(last.h - first.h) > 0.35 * max(last.h, first.h):
        return False
    gap = group.y0 - last.y1
    if gap < -0.3 * h or gap > LINE_GAP * max(last.h, first.h):
        return False
    rx0, _, rx1, _ = region.bbox
    if min(rx1, group.x1) - max(rx0, group.x0) <= 0:
        return False
    if LIST_MARKER.match(group.text):
        return False
    # Řádek, který začíná výrazně vlevo od odstavce, je nový sloupec nebo nový odstavec.
    if group.x0 < rx0 - 2 * h:
        return False
    if region.indent is not None and group.x0 < region.indent - h:
        return False
    return True


def _labelled(row):
    return any(g.tabular or g.segs[0].text.endswith(":") for g in row)


def _columns(members):
    """Shlukne skupiny pásu do sloupců podle překryvu v ose x; sloupce zleva doprava, ve sloupci shora dolů."""
    cols: list[list[Group]] = []
    for group in sorted(members, key=lambda g: g.x0):
        col = next((c for c in cols if any(min(g.x1, group.x1) - max(g.x0, group.x0) > 0 for g in c)), None)
        if col is not None:
            col.append(group)
        else:
            cols.append([group])
    return [sorted(c, key=lambda g: g.y0) for c in sorted(cols, key=lambda c: min(g.x0 for g in c))]


def _band_regions(members, median_h):
    """Regiony z jednoho pásu tabulky (mezi dvěma vodorovnými čarami).

    - Formulář bez vnitřních čar (každý vizuální řádek má popisek s dvojtečkou): region na řádek.
    - Jeden sloupec: orámovaný text, dělí se jen na nadpisech a značkách výčtu.
    - Jinak jeden `table_row`; text po sloupcích, takže zalomená buňka („Předběžná splatnost / splátek“) drží pohromadě.
    """
    rows: list[list[Group]] = []
    for group in sorted(members, key=lambda g: (g.y0, g.x0)):
        row = next((r for r in rows if any(_same_row(group, o) for o in r)), None)
        if row is not None:
            row.append(group)
        else:
            rows.append([group])
    if len(rows) > 1 and all(_labelled(r) for r in rows):
        return [Region("table_row", [s for g in sorted(r, key=lambda g: g.x0) for s in g.segs]) for r in rows]
    cols = _columns(members)
    if len(cols) == 1:
        out: list[Region] = []
        for group in cols[0]:
            is_item = bool(LIST_MARKER.match(group.text))
            heading = _heading(group, median_h)
            if out and not (is_item or heading or group.tabular) and out[-1].kind in ("paragraph", "list_item"):
                out[-1].lines.extend(group.segs)
            else:
                kind = "heading" if heading else "table_row" if group.tabular else "list_item" if is_item else "paragraph"
                out.append(Region(kind, list(group.segs)))
        return out
    return [Region("table_row", [s for col in cols for g in col for s in g.segs])]


def segment_page(page):
    """Regiony jedné strany v pořadí čtení (shora dolů, zleva doprava), souřadnice nerotované strany (body).
    `None` = strana bez použitelné textové vrstvy."""
    segs = segments(page)
    if sum(len(s.text) for s in segs) < MIN_PAGE_CHARS:
        return None
    horizontal = rules(page)
    width = page.mediabox.width or page.rect.width
    groups = _join_rows(segs, width)

    bands, free = {}, []
    for group in groups:
        band = _band(group, horizontal)
        if band is None:
            free.append(group)
        else:
            bands.setdefault(band, []).append(group)
    # Pás s jedinou skupinou je jen podtržený nebo orámovaný řádek, zpracuje se jako volný text.
    for band, members in list(bands.items()):
        if len(members) == 1:
            free.extend(bands.pop(band))
    heights = sorted(g.h for g in groups)
    median_h = heights[len(heights) // 2]
    regions = [region for members in bands.values() for region in _band_regions(members, median_h)]
    free.sort(key=lambda g: (g.y0, g.x0))
    open_regions: list[Region] = []
    for group in free:
        if _heading(group, median_h):
            regions.append(Region("heading", list(group.segs)))
            continue
        if group.tabular:
            regions.append(Region("table_row", list(group.segs)))
            continue
        target = next((r for r in reversed(open_regions) if _continues(r, group)), None)
        if target is not None:
            target.lines.extend(group.segs)
            continue
        is_item = bool(LIST_MARKER.match(group.text))
        region = Region("list_item" if is_item else "paragraph", list(group.segs))
        if is_item and len(group.segs) > 1 and BARE_MARKER.match(group.segs[0].text):
            region.indent = group.segs[1].x0
        regions.append(region)
        open_regions.append(region)

    regions.sort(key=lambda r: (round(r.bbox[1] / 4), r.bbox[0]))
    return regions


def _norm(rect, page):
    r = pymupdf.Rect(rect) * page.rotation_matrix
    w, h = page.rect.width, page.rect.height
    return [round(min(max(v, 0.0), 1.0), 4) for v in (r.x0 / w, r.y0 / h, r.x1 / w, r.y1 / h)]


def region_text(region):
    """Text regionu a rozsahy znaků jednotlivých řádků. Buňky (sloupce) řádku tabulky dělí ' | '."""
    parts, spans, pos = [], [], 0
    for i, seg in enumerate(region.lines):
        if i:
            prev = region.lines[i - 1]
            sep = " | " if region.kind == "table_row" and seg.x0 > prev.x1 and not seg.joined else " "
            parts.append(sep)
            pos += len(sep)
        parts.append(seg.text)
        spans.append((seg, pos, pos + len(seg.text)))
        pos += len(seg.text)
    return "".join(parts), spans


_DIGITS = re.compile(r"\d+")


def _mark_page_furniture(per_page):
    """per_page: [(výška strany, [Region])]. Označí záhlaví a zápatí (viz krok 5 v popisu modulu)."""
    def zone(region, height):
        cy = (region.bbox[1] + region.bbox[3]) / 2 / height
        return "top" if cy <= MARGIN else "bottom" if cy >= 1 - MARGIN else None

    seen = {}
    for number, (height, regions) in enumerate(per_page):
        for region in regions:
            z = zone(region, height)
            if z:
                key = (z, _DIGITS.sub("#", region_text(region)[0]))
                seen.setdefault(key, set()).add(number)
    for height, regions in per_page:
        for region in regions:
            if region.kind not in ("paragraph", "heading", "list_item"):
                continue
            z = zone(region, height)
            if not z:
                continue
            cy = (region.bbox[1] + region.bbox[3]) / 2 / height
            repeated = len(seen.get((z, _DIGITS.sub("#", region_text(region)[0])), ())) >= 2
            if repeated or cy <= EDGE or cy >= 1 - EDGE:
                region.kind = "page_header" if z == "top" else "page_footer"


def document_regions(doc):
    """Regiony celého dokumentu ve tvaru `regions.json` (bez štítků). `doc` je otevřený pymupdf.Document."""
    segmented = [(page, segment_page(page)) for page in doc]
    _mark_page_furniture([(page.mediabox.height or page.rect.height, regions or []) for page, regions in segmented])
    pages, out = [], []
    for index, (page, regions) in enumerate(segmented):
        number = index + 1
        pages.append({"page": number, "width": round(page.rect.width, 1), "height": round(page.rect.height, 1),
                      "source": "text_layer" if regions is not None else "no_text_layer"})
        for order, region in enumerate(regions or [], start=1):
            text, spans = region_text(region)
            out.append({
                "region_id": f"p{number}-r{order:02d}",
                "page": number,
                "order": order,
                "bbox": _norm(region.bbox, page),
                "kind": region.kind,
                "text": text,
                "lines": [{"bbox": _norm(seg.rect, page), "start": start, "end": end} for seg, start, end in spans],
                "label": None,
                "source": "text_layer",
            })
    return {"version": 1, "pages": pages, "regions": out}


def regions_for_pdf(data_or_path):
    doc = pymupdf.open(stream=data_or_path, filetype="pdf") if isinstance(data_or_path, (bytes, bytearray)) \
        else pymupdf.open(data_or_path)
    try:
        return document_regions(doc)
    finally:
        doc.close()
