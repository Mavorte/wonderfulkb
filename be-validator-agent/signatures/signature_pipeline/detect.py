"""Step 1: where is the signature. Textract AnalyzeDocument with SIGNATURES, one rendered page at a time."""
import hashlib
import json
from pathlib import Path

from .imaging import render_page_png
from .models import Detection

IOU_DUPLICATE = 0.5


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def dedupe(detections):
    """Drop overlapping boxes of the same page, keep the one with the higher score."""
    kept = []
    for d in sorted(detections, key=lambda d: -(d.score or 0)):
        if all(k.page != d.page or iou(k.bbox, d.bbox) < IOU_DUPLICATE for k in kept):
            kept.append(d)
    return sorted(kept, key=lambda d: (d.page, d.bbox[1], d.bbox[0]))


def parse_textract(response, page_number):
    out = []
    for block in response.get("Blocks", []):
        if block.get("BlockType") != "SIGNATURE":
            continue
        b = block["Geometry"]["BoundingBox"]
        x0, y0 = max(0.0, b["Left"]), max(0.0, b["Top"])
        x1, y1 = min(1.0, b["Left"] + b["Width"]), min(1.0, b["Top"] + b["Height"])
        if x1 > x0 and y1 > y0:
            out.append(Detection(page_number, [x0, y0, x1, y1], "textract", float(block.get("Confidence", 0))))
    return out


class TextractDetector:
    """Calls Textract per page on a rendered PNG, so the bbox is relative to the rendered (rotated) page.

    Responses are cached on disk by the SHA-256 of the PNG: re-running the same PDF costs nothing.
    """

    def __init__(self, client=None, region="eu-central-1", dpi=150, cache_dir=None):
        if client is None:
            import boto3
            from botocore.config import Config
            # Textract has a low TPS quota: parallel workers get ProvisionedThroughputExceeded, so back off and retry
            client = boto3.client("textract", region_name=region,
                                  config=Config(retries={"mode": "adaptive", "max_attempts": 10}))
        self.client, self.dpi = client, dpi
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.calls = 0

    def _analyze(self, png):
        key = hashlib.sha256(png).hexdigest()
        cached = self.cache_dir / f"{key}.json" if self.cache_dir else None
        if cached and cached.exists():
            return json.loads(cached.read_text())
        self.calls += 1
        response = self.client.analyze_document(Document={"Bytes": png}, FeatureTypes=["SIGNATURES"])
        response = {"Blocks": response.get("Blocks", [])}
        if cached:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(response))
        return response

    def detect(self, doc):
        found = []
        for index, page in enumerate(doc, start=1):
            found += parse_textract(self._analyze(render_page_png(page, self.dpi)), index)
        return dedupe(found)

    def lines(self, doc, page_number):
        """OCR lines of one page in page points (Textract returns LINE blocks next to SIGNATURE blocks)."""
        from .models import TextLine
        page = doc[page_number - 1]
        r = page.rect
        out = []
        for block in self._analyze(render_page_png(page, self.dpi)).get("Blocks", []):
            if block.get("BlockType") == "LINE" and block.get("Text", "").strip():
                b = block["Geometry"]["BoundingBox"]
                out.append(TextLine(" ".join(block["Text"].split()), r.x0 + b["Left"] * r.width,
                                    r.y0 + b["Top"] * r.height, r.x0 + (b["Left"] + b["Width"]) * r.width,
                                    r.y0 + (b["Top"] + b["Height"]) * r.height))
        return out


class PrecomputedDetector:
    """Takes findings made elsewhere (items of `SignatureItem` from be-document-processing: page, bbox,
    detection_score, role, role_evidence) instead of calling Textract again."""

    def __init__(self, items):
        self.items = items

    def detect(self, doc):
        found = []
        for item in self.items:
            item = item if isinstance(item, dict) else item.model_dump()
            hint = {"role": item.get("role"), "role_evidence": item.get("role_evidence")}
            found.append(Detection(item["page"], list(item["bbox"]), item.get("detector", "textract"),
                                   item.get("detection_score"), hint))
        return dedupe(found)


class PageImageDetector:
    """Fallback without any service: embedded images on a born-digital page that look like a handwritten signature.

    A signature scan placed on a form is an image of signature size with thin strokes on a light
    background. Logos (top of the page, repeated on pages), barcodes (dense ink) and photographs (large)
    are filtered out. Only candidates; the detector never says a mark is a signature, a person decides.
    """
    name = "page_images"
    WIDTH = (35.0, 230.0)     # points
    HEIGHT = (12.0, 110.0)
    ASPECT = (1.1, 8.0)
    INK = (0.02, 0.40)        # share of dark pixels inside the image box
    TOP_MARGIN = 0.18         # relative page height: header logos live above this
    MAX_REPEAT = 3            # the same image on more pages is a logo, not a signature
    MAX_PER_PAGE = 6          # more candidates on one page means text stored as images (a scanned table)
    PAD = (0.15, 0.5)         # box growth, share of width and height on each side: image boxes are tight

    def __init__(self, dpi=100):
        self.dpi = dpi

    def _ink_share(self, page, rect):
        import numpy as np
        from .imaging import crop_page
        img = crop_page(page, [rect.x0 / page.rect.width, rect.y0 / page.rect.height,
                               rect.x1 / page.rect.width, rect.y1 / page.rect.height], dpi=self.dpi, pad=0.0)
        gray = np.asarray(img.convert("L"), dtype=np.float32)
        return float((gray < 140).mean())

    def detect(self, doc):
        import pymupdf
        repeats = {}
        for page in doc:
            for info in page.get_image_info(xrefs=True):
                repeats.setdefault(info.get("xref"), set()).add(page.number)
        found = []
        for index, page in enumerate(doc, start=1):
            r = page.rect
            page_found = []
            for info in page.get_image_info(xrefs=True):
                b = pymupdf.Rect(info["bbox"]) & r
                if b.is_empty:
                    continue
                aspect = b.width / b.height
                if not (self.WIDTH[0] <= b.width <= self.WIDTH[1] and self.HEIGHT[0] <= b.height <= self.HEIGHT[1]
                        and self.ASPECT[0] <= aspect <= self.ASPECT[1]):
                    continue
                if b.y1 < r.height * self.TOP_MARGIN or len(repeats.get(info.get("xref"), ())) > self.MAX_REPEAT:
                    continue
                if not (self.INK[0] <= self._ink_share(page, b) <= self.INK[1]):
                    continue
                grown = pymupdf.Rect(b.x0 - self.PAD[0] * b.width, b.y0 - self.PAD[1] * b.height,
                                     b.x1 + self.PAD[0] * b.width, b.y1 + self.PAD[1] * b.height) & r
                page_found.append(Detection(index, [grown.x0 / r.width, grown.y0 / r.height,
                                                    grown.x1 / r.width, grown.y1 / r.height], self.name, None))
            if len(page_found) <= self.MAX_PER_PAGE:
                found += page_found
        return dedupe(found)


def same_mark(a, b):
    """Two boxes of one page mark the same thing: they overlap (IoU >= 0.2) or one contains the other's centre."""
    if a.page != b.page:
        return False
    if iou(a.bbox, b.bbox) >= 0.2:
        return True

    def centre_in(inner, outer):
        cx, cy = (inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2
        w, h = outer[2] - outer[0], outer[3] - outer[1]
        return outer[0] - 0.1 * w <= cx <= outer[2] + 0.1 * w and outer[1] - 0.1 * h <= cy <= outer[3] + 0.1 * h

    return centre_in(a.bbox, b.bbox) or centre_in(b.bbox, a.bbox)


class CombinedDetector:
    """Detectors in order of trust: the first one is kept whole, each later one adds only boxes that no
    earlier box already marks (`same_mark`)."""

    def __init__(self, primary, *fallbacks):
        self.detectors = (primary, *fallbacks)

    def detect(self, doc):
        kept = []
        for detector in self.detectors:
            for d in detector.detect(doc):
                if not any(same_mark(k, d) for k in kept):
                    kept.append(d)
        return sorted(kept, key=lambda d: (d.page, d.bbox[1], d.bbox[0]))


class LabelAnchoredDetector:
    """Second detector anchored on the printed label "Podpis": look at the area above it and decide about ink.

    Signatures stand right above a label ("Podpis", "Datum a podpis", "razítko a podpis"). The area above
    the label is rendered without printed text (text layer redacted, or OCR lines painted white on a
    scan), table borders and underlines are dropped, and the page counts as signed when enough ink is left.
    It decides only "ink here or not", never what the ink is: a stamp or a paraph counts too.
    """
    name = "label_anchored"
    WIDTH = 140.0           # points, centred on the label
    HEIGHT = 70.0           # points above the label
    MIN_INK_PX = 120        # at 100 dpi
    MIN_SIZE = (20.0, 8.0)  # points, ink box
    RULE_RUN = 0.5          # a stroke running over this share of the area is a rule, not handwriting
    LABEL = r"\bpodpis\b|razitko a podpis"

    def __init__(self, ocr=None, dpi=100):
        self.ocr, self.dpi = ocr, dpi

    def _is_label(self, text):
        import re
        from .roles import fold
        return len(text.split()) <= 7 and re.search(self.LABEL, fold(text)) is not None

    def _regions(self, labels, page):
        import pymupdf
        r = page.rect
        out = []
        for l in labels:
            cx = (l.x0 + l.x1) / 2
            half = max(self.WIDTH / 2, (l.x1 - l.x0) / 2)
            region = pymupdf.Rect(cx - half, l.y0 - self.HEIGHT, cx + half, l.y0 - 1) & r
            if region.width > 10 and region.height > 10:
                out.append(region)
        return out

    def _ink_box(self, img):
        """Tight pixel box (x0, y0, x1, y1) of the remaining ink, or None."""
        import numpy as np
        ink = np.asarray(img.convert("L"), dtype=np.float32) < 140
        h, w = ink.shape

        def longest_run(a):
            best = np.zeros(a.shape[0], dtype=int)
            cur = np.zeros(a.shape[0], dtype=int)
            for j in range(a.shape[1]):
                cur = np.where(a[:, j], cur + 1, 0)
                best = np.maximum(best, cur)
            return best

        rows = longest_run(ink) >= self.RULE_RUN * w
        for y in np.where(rows)[0]:
            ink[max(0, y - 1):y + 2, :] = False
        cols = longest_run(ink.T) >= 0.7 * h
        for x in np.where(cols)[0]:
            ink[:, max(0, x - 1):x + 2] = False
        if ink.sum() < self.MIN_INK_PX:
            return None
        ys, xs = np.where(ink)
        scale = self.dpi / 72.0
        if (xs.max() - xs.min()) / scale < self.MIN_SIZE[0] or (ys.max() - ys.min()) / scale < self.MIN_SIZE[1]:
            return None
        return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1

    def detect(self, doc):
        from PIL import ImageDraw
        from .imaging import crop_page, text_free_page
        from .roles import page_lines
        found = []
        for index, page in enumerate(doc, start=1):
            lines = page_lines(page)
            text_layer = bool(lines)
            if not text_layer and self.ocr:
                lines = self.ocr.lines(doc, index)
            regions = self._regions([l for l in lines if self._is_label(l.text)], page)
            if not regions:
                continue
            r = page.rect
            rel = [[g.x0 / r.width, g.y0 / r.height, g.x1 / r.width, g.y1 / r.height] for g in regions]
            clean = text_free_page(doc, index - 1, rel, pad=0.0) if text_layer else page
            for g, box in zip(regions, rel):
                img = crop_page(clean, box, dpi=self.dpi, pad=0.0)
                if not text_layer:      # scan: paint what OCR read as printed text
                    scale = self.dpi / 72.0
                    draw = ImageDraw.Draw(img)
                    for l in lines:
                        draw.rectangle([(l.x0 - g.x0) * scale - 1, (l.y0 - g.y0) * scale - 1,
                                        (l.x1 - g.x0) * scale + 1, (l.y1 - g.y0) * scale + 1], fill="white")
                ink = self._ink_box(img)
                if ink is None:
                    continue
                scale = self.dpi / 72.0
                x0, y0 = g.x0 + ink[0] / scale - 2, g.y0 + ink[1] / scale - 2
                x1, y1 = g.x0 + ink[2] / scale + 2, g.y0 + ink[3] / scale + 2
                found.append(Detection(index, [max(0.0, x0 / r.width), max(0.0, y0 / r.height),
                                               min(1.0, x1 / r.width), min(1.0, y1 / r.height)], self.name, None))
        return dedupe(found)


class VectorStrokeDetector:
    """Fallback for signatures drawn as vector curves (generated documents, some e-signature renderers).

    Groups the page's stroked curve drawings into clusters (neighbours within `JOIN` points) and keeps the
    clusters of signature size with enough curve segments. Logos and charts can look the same, so the top
    and bottom margins of the page are skipped and every finding is only a candidate for a person.
    """
    name = "vector_strokes"
    JOIN = 6.0
    MIN_CURVES = 8
    WIDTH = (30.0, 260.0)
    HEIGHT = (10.0, 130.0)
    MARGIN = (0.12, 0.06)      # relative page height skipped at the top and bottom
    MAX_FILLED_SHARE = 0.5     # clusters made mostly of filled shapes are logos or boxes, not strokes

    def detect(self, doc):
        import pymupdf
        found = []
        for index, page in enumerate(doc, start=1):
            r = page.rect
            items = []
            for d in page.get_drawings():
                curves = sum(1 for it in d["items"] if it[0] == "c")
                if curves == 0 or (d.get("width") or 0) > 4:
                    continue
                items.append((pymupdf.Rect(d["rect"]), curves, d.get("fill") is not None and d.get("color") is None))
            clusters = []                # [Rect, curves, filled_curves]
            for rect, curves, filled in items:
                grown = pymupdf.Rect(rect.x0 - self.JOIN, rect.y0 - self.JOIN, rect.x1 + self.JOIN, rect.y1 + self.JOIN)
                hit = [c for c in clusters if c[0].intersects(grown)]
                merged = [pymupdf.Rect(rect), curves, curves if filled else 0]
                for c in hit:
                    merged[0] |= c[0]
                    merged[1] += c[1]
                    merged[2] += c[2]
                    clusters.remove(c)
                clusters.append(merged)
            for rect, curves, filled in clusters:
                if (curves >= self.MIN_CURVES and filled / curves <= self.MAX_FILLED_SHARE
                        and self.WIDTH[0] <= rect.width <= self.WIDTH[1] and self.HEIGHT[0] <= rect.height <= self.HEIGHT[1]
                        and r.height * self.MARGIN[0] <= rect.y0 and rect.y1 <= r.height * (1 - self.MARGIN[1])):
                    found.append(Detection(index, [max(0.0, rect.x0 / r.width), max(0.0, rect.y0 / r.height),
                                                   min(1.0, rect.x1 / r.width), min(1.0, rect.y1 / r.height)],
                                           self.name, None))
        return dedupe(found)


def default_detector(textract, vector=False):
    """Default order of trust: Textract, then embedded images, then ink above the "Podpis" label.
    `vector=True` adds the vector-stroke detector, which gives more false findings (parts of stamps):
    opt-in. Every finding keeps the name of the detector that found it in `detector`."""
    extra = [PageImageDetector(), LabelAnchoredDetector(ocr=textract)]
    if vector:
        extra.append(VectorStrokeDetector())
    return CombinedDetector(textract, *extra)
