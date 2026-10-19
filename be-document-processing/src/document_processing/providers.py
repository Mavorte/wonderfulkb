from html.parser import HTMLParser
from io import BytesIO

from .models import Block, Cell, Page
from .rendering import normalize_box, render_page


class ProviderError(Exception):
    def __init__(self, code, retryable=False):
        self.code, self.retryable = code, retryable
        super().__init__(code)


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells, self.row, self.column, self.current, self.occupied = [], -1, 0, None, set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self.row += 1
            self.column = 0
        if tag in ("td", "th"):
            self.row = max(0, self.row)
            while (self.row, self.column) in self.occupied:
                self.column += 1
            try:
                row_span, column_span = int(attrs.get("rowspan", 1)), int(attrs.get("colspan", 1))
                if not (1 <= row_span <= 100 and 1 <= column_span <= 100):
                    raise ValueError()
            except ValueError:
                row_span = column_span = 1
            self.current = Cell(row=self.row, column=self.column, row_span=row_span, column_span=column_span, text="")
        if tag == "br" and self.current:
            self.current.text += "\n"

    def handle_data(self, data):
        if self.current:
            self.current.text += data

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.current:
            cell = self.current
            cell.text = cell.text.strip()
            for row in range(cell.row, cell.row + cell.row_span):
                for col in range(cell.column, cell.column + cell.column_span):
                    self.occupied.add((row, col))
            self.cells.append(cell)
            self.column += cell.column_span
            self.current = None


def parse_table(html):
    parser = TableParser()
    parser.feed(html)
    return parser.cells


class LocalOcr:
    """Native PDF text or optional offline RapidOCR baseline. No manufactured text."""
    def __init__(self):
        self.recognizer = None

    def transcribe(self, page, page_number, mode):
        blocks = []
        if mode == "auto" and page.get_text().strip():
            for index, raw in enumerate(page.get_text("blocks", sort=True)):
                if len(raw) > 6 and raw[6] != 0:
                    continue
                rect = __import__("pymupdf").Rect(raw[:4]) * page.rotation_matrix
                blocks.append(Block(block_id=f"p{page_number}-b{index+1}", text=raw[4].strip(),
                                    bbox=normalize_box(rect, page.rect.width, page.rect.height)))
            return Page(page_number=page_number, status="completed", method="native", width=page.rect.width,
                        height=page.rect.height, text="\n".join(b.text for b in blocks), blocks=blocks,
                        warnings=["NATIVE_TEXT_NOT_VISUALLY_VERIFIED", "VISUAL_MARKS_NOT_PROCESSED"], model="pymupdf")
        try:
            import numpy as np
            from PIL import Image
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as error:
            raise ProviderError("LOCAL_VISION_OCR_NOT_INSTALLED") from error
        if self.recognizer is None:
            self.recognizer = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=2)
        png, width, height = render_page(page)
        results, _ = self.recognizer(np.array(Image.open(BytesIO(png))))
        for index, (polygon, text, confidence) in enumerate(results or []):
            xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
            blocks.append(Block(block_id=f"p{page_number}-b{index+1}", text=text,
                                bbox=normalize_box([min(xs), min(ys), max(xs), max(ys)], width, height),
                                confidence=float(confidence)))
        return Page(page_number=page_number, status="completed", method="vision", width=page.rect.width,
                    height=page.rect.height, text="\n".join(b.text for b in blocks), blocks=blocks,
                    warnings=["LOCAL_BASELINE_NOT_CZECH_SPECIALIZED", "VISUAL_MARKS_NOT_PROCESSED"], model="rapidocr-ppocrv4")
