import json

import pymupdf

from conftest import FakeDetector, make_contract, text
from signature_pipeline.detect import TextractDetector, dedupe, parse_textract
from signature_pipeline.models import Detection
from signature_pipeline.pipeline import LocalCropStore, process_case, process_pdf
from signature_pipeline.roles import assign_role, role_of


def test_role_from_column_header(contract):
    pdf, (left, right) = contract
    sigs = process_pdf(pdf, FakeDetector({1: [left, right]}), "c1", "d1")
    assert [s.role for s in sigs] == ["provider", "borrower"]
    assert sigs[0].role_source == "nearest_text"
    assert sigs[0].role_evidence == "Poskytovatel financování:"
    assert sigs[1].role_evidence == "Příjemce financování:"


def test_role_unknown_without_label():
    doc = pymupdf.open()
    page = doc.new_page()
    text(page, (60, 90), "Nějaký text bez popisků.")
    sigs = process_pdf(doc.tobytes(), FakeDetector({1: [[0.1, 0.5, 0.4, 0.6]]}))
    assert sigs[0].role == "unknown" and sigs[0].role_evidence is None


def test_sentence_is_not_a_label():
    assert role_of("Dlužník je povinen splácet dohodnuté splátky řádně a včas") == (None, None)
    assert role_of("Podpis a razítko příjemce financování (Pojistníka)")[0] == "borrower"
    assert role_of("Za ručitele")[0] == "guarantor"
    assert role_of("Podpis a razítko pojistitele")[0] == "insurer"


def test_no_detection_is_empty_list(contract):
    out = process_case("c1", {"d1": contract[0]}, FakeDetector({}))
    assert out["d1"]["signatures"] == []


def test_copy_suspected_across_documents():
    a, (a_left, _) = make_contract((1, 2))
    b, (b_left, b_right) = make_contract((1, 3), scale=1.4, offset=(12, -30))  # same stroke 1, bigger, moved
    c, (c_left, _) = make_contract((7, 8))
    out = process_case("c1", {"a": a, "b": b, "c": c},
                       _PerDoc({"a": [a_left], "b": [b_left, b_right], "c": [c_left]}))
    a_sig = out["a"]["signatures"][0]
    assert a_sig["copy_suspicion"]["level"] == "suspected"
    assert a_sig["copy_suspicion"]["matches"][0]["document_id"] == "b"
    assert out["b"]["signatures"][0]["copy_suspicion"]["level"] == "suspected"
    assert out["b"]["signatures"][1]["copy_suspicion"]["level"] == "none"   # different stroke
    assert out["c"]["signatures"][0]["copy_suspicion"]["level"] == "none"


def test_printed_template_text_does_not_cause_false_copy():
    # Different signatures in the same template: dotted line and "Podpis" are in every crop.
    a, (a_left, _) = make_contract((11, 12))
    b, (b_left, _) = make_contract((21, 22))
    out = process_case("c1", {"a": a, "b": b}, _PerDoc({"a": [a_left], "b": [b_left]}))
    assert out["a"]["signatures"][0]["copy_suspicion"]["level"] == "none"


def test_blank_crop_has_no_hash():
    doc = pymupdf.open()
    doc.new_page()
    sigs = process_pdf(doc.tobytes(), FakeDetector({1: [[0.1, 0.1, 0.3, 0.2]]}))
    assert sigs[0].phash is None


def test_crop_is_written(tmp_path, contract):
    pdf, (left, _) = contract
    sigs = process_pdf(pdf, FakeDetector({1: [left]}), "c1", "d1", LocalCropStore(tmp_path))
    assert (tmp_path / "c1" / "d1" / "sig_01.png").stat().st_size > 0
    assert sigs[0].crop_path.endswith("sig_01.png")


def test_parse_textract_and_dedupe():
    response = {"Blocks": [
        {"BlockType": "PAGE"},
        {"BlockType": "SIGNATURE", "Confidence": 60.0, "Geometry": {"BoundingBox": {"Left": .1, "Top": .7, "Width": .2, "Height": .05}}},
        {"BlockType": "SIGNATURE", "Confidence": 20.0, "Geometry": {"BoundingBox": {"Left": .11, "Top": .7, "Width": .2, "Height": .05}}},
        {"BlockType": "SIGNATURE", "Confidence": 30.0, "Geometry": {"BoundingBox": {"Left": .6, "Top": .7, "Width": .3, "Height": .06}}},
    ]}
    found = dedupe(parse_textract(response, 2))
    assert [d.score for d in found] == [60.0, 30.0] and all(d.page == 2 for d in found)


def test_textract_detector_caches(tmp_path, contract):
    class Client:
        calls = 0

        def analyze_document(self, **kw):
            Client.calls += 1
            assert kw["FeatureTypes"] == ["SIGNATURES"]
            return {"Blocks": [{"BlockType": "SIGNATURE", "Confidence": 50, "Geometry": {"BoundingBox": {"Left": .1, "Top": .8, "Width": .3, "Height": .05}}}]}

    det = TextractDetector(client=Client(), cache_dir=tmp_path)
    doc = pymupdf.open(stream=contract[0], filetype="pdf")
    assert len(det.detect(doc)) == 1 and len(det.detect(doc)) == 1
    assert Client.calls == 1 and det.calls == 1


def test_api_shape(contract):
    pdf, (left, _) = contract
    out = process_case("c1", {"d1": pdf}, FakeDetector({1: [left]}))
    json.dumps(out)
    sig = out["d1"]["signatures"][0]
    assert {"signature_id", "page", "bbox", "detector", "detection_score", "role", "role_source",
            "role_evidence", "crop_url", "phash", "copy_suspicion"} <= set(sig)
    assert len(sig["phash"]) == 16 and sig["detector"] == "textract"


class _PerDoc:
    """Detector that knows the boxes per document (documents are identified by call order)."""

    def __init__(self, boxes):
        self.queue = list(boxes.values())

    def detect(self, doc):
        return [Detection(1, b, "textract", 40.0) for b in self.queue.pop(0)]


def test_label_above_in_other_column_is_not_adjacent():
    # Wide box straddling the left column: the right header is close but belongs to the other column.
    pdf, (left, _) = make_contract((1, 2))
    wide = [left[0], left[1], left[2] + 0.04, left[3]]
    sig = process_pdf(pdf, FakeDetector({1: [wide]}), "c1", "d1")[0]
    assert sig.role == "provider"


def test_vertical_border_separates_columns():
    doc = pymupdf.open()
    page = doc.new_page()
    text(page, (60, 600), "Ručitel:", 10)
    text(page, (320, 600), "Dlužník:", 10)
    page.draw_line((300, 560), (300, 760))           # table border between the two columns
    box = pymupdf.Rect(330, 650, 480, 700)
    page.draw_rect(box)
    r = page.rect
    rel_box = [box.x0 / r.width, box.y0 / r.height, box.x1 / r.width, box.y1 / r.height]
    sig = process_pdf(doc.tobytes(), FakeDetector({1: [rel_box]}))[0]
    assert sig.role == "borrower"
    # Title over a whole table (no border below it): "Ručitel:" owns a signature far on the right.
    doc2 = pymupdf.open()
    p2 = doc2.new_page()
    text(p2, (60, 400), "Ručitel:", 10)
    box = pymupdf.Rect(300, 480, 420, 530)
    p2.draw_rect(box)
    rel_box = [box.x0 / r.width, box.y0 / r.height, box.x1 / r.width, box.y1 / r.height]
    assert process_pdf(doc2.tobytes(), FakeDetector({1: [rel_box]}))[0].role == "guarantor"


def test_table_border_in_crop_does_not_change_hash():
    from conftest import draw_scribble

    def build(border):
        doc = pymupdf.open()
        page = doc.new_page()
        rect = pymupdf.Rect(100, 300, 260, 360)
        draw_scribble(page, 5, rect)
        if border:
            page.draw_line((90, 296), (270, 296))
        r = page.rect
        box = [(rect.x0 - 8) / r.width, (rect.y0 - 6) / r.height, (rect.x1 + 8) / r.width, (rect.y1 + 6) / r.height]
        return process_pdf(doc.tobytes(), FakeDetector({1: [box]}))[0]

    from signature_pipeline.imaging import hamming, mask_similarity
    plain, bordered = build(False), build(True)
    assert hamming(plain.phash, bordered.phash) <= 4
    assert mask_similarity(plain.mask, bordered.mask) > 0.9


def test_border_ending_at_signature_does_not_separate():
    # Label cell with its own border (like the black "Objednatel" cell), signature right below the cell.
    doc = pymupdf.open()
    page = doc.new_page()
    text(page, (60, 700), "Objednatel", 10)
    page.draw_line((110, 685), (110, 715))           # right edge of the label cell, ends above the signature
    box = pymupdf.Rect(140, 713, 260, 760)
    page.draw_rect(box)
    r = page.rect
    rel_box = [box.x0 / r.width, box.y0 / r.height, box.x1 / r.width, box.y1 / r.height]
    assert process_pdf(doc.tobytes(), FakeDetector({1: [rel_box]}))[0].role == "buyer"


def _scan_like_pdf():
    """A page with a signature but no text layer (as a scan)."""
    doc = pymupdf.open()
    page = doc.new_page()
    from conftest import draw_scribble
    rect = pymupdf.Rect(300, 650, 450, 710)
    draw_scribble(page, 3, rect)
    r = page.rect
    return doc.tobytes(), [rect.x0 / r.width, rect.y0 / r.height, rect.x1 / r.width, rect.y1 / r.height]


def test_precomputed_findings_give_role_when_pdf_has_no_text():
    from signature_pipeline.detect import PrecomputedDetector
    pdf, box = _scan_like_pdf()
    item = {"page": 1, "bbox": box, "detection_score": 12.0, "role": "guarantor", "role_evidence": "Ručitel:"}
    sig = process_pdf(pdf, PrecomputedDetector([item]))[0]
    assert (sig.role, sig.role_source, sig.role_evidence, sig.detection_score) == ("guarantor", "nearest_text", "Ručitel:", 12.0)
    unknown = process_pdf(pdf, PrecomputedDetector([{**item, "role": "unknown", "role_evidence": None}]))[0]
    assert unknown.role == "unknown"


def test_pdf_text_beats_upstream_hint(contract):
    from signature_pipeline.detect import PrecomputedDetector
    pdf, (left, _) = contract
    item = {"page": 1, "bbox": left, "role": "buyer", "role_evidence": "Kupující"}
    assert process_pdf(pdf, PrecomputedDetector([item]))[0].role == "provider"


def test_ocr_blocks_with_bbox_give_role_when_pdf_has_no_text():
    pdf, box = _scan_like_pdf()
    blocks = [{"page_number": 1, "text": "Za dlužníka", "bbox": [box[0], box[1] - 0.04, box[2], box[1] - 0.01]},
              {"page_number": 1, "text": "Ručitel", "bbox": None}]   # no bbox: unusable, ignored
    sig = process_pdf(pdf, FakeDetector({1: [box]}), ocr_text_blocks=blocks)[0]
    assert sig.role == "borrower" and sig.role_evidence == "Za dlužníka"


def test_detect_signatures_interface(contract):
    from signature_pipeline import detect_signatures
    pdf, (left, right) = contract
    out = detect_signatures(pdf, detector=FakeDetector({1: [left, right]}))
    assert [s["role"] for s in out] == ["provider", "borrower"]
    assert all("crop_url" not in s for s in out)


class _S3:
    """Fake S3 client with put_object and head_object."""

    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, **kw):
        self.objects[(Bucket, Key)] = Body

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            error = Exception("not found")
            error.response = {"Error": {"Code": "404"}}
            raise error


def test_s3_layout_plain_crops_need_explicit_permission(contract):
    import pytest
    from signature_pipeline.store import PlaintextNotAllowed, S3CropStore, write_signatures_json
    pdf, (left, _) = contract
    with pytest.raises(PlaintextNotAllowed):
        process_case("c1", {"d1": pdf}, FakeDetector({1: [left]}), S3CropStore(_S3()))
    s3 = _S3()
    out = process_case("c1", {"d1": pdf}, FakeDetector({1: [left]}), S3CropStore(s3, allow_plain=True))
    key = write_signatures_json(out["d1"], s3)
    assert key == "cases/c1/analysis/d1/signatures.json"
    assert ("wonderfulkb-raw-document-storage", "cases/c1/analysis/d1/signatures/sig_01.png") in s3.objects
    body = json.loads(s3.objects[("wonderfulkb-raw-document-storage", key)])
    assert body["signatures"][0]["role"] == "provider" and "crop_url" not in body["signatures"][0]
    assert body["signatures"][0]["crop_s3_key"].endswith("sig_01.png") and body["signatures"][0]["crop_encrypted"] is False
    assert len(s3.objects) == 2


def test_signatures_json_is_not_overwritten_by_default(contract):
    import pytest
    from signature_pipeline.store import write_signatures_json
    s3 = _S3()
    pdf, (left, _) = contract
    out = process_case("c1", {"d1": pdf}, FakeDetector({1: [left]}))
    write_signatures_json(out["d1"], s3)
    with pytest.raises(FileExistsError):
        write_signatures_json(out["d1"], s3)
    write_signatures_json(out["d1"], s3, overwrite=True)      # explicit


def _privacy_or_skip():
    import pytest
    from signature_pipeline.store import _privacy
    try:
        return _privacy()
    except ImportError:
        pytest.skip("signature_privacy (needs cryptography) is not importable")


def test_encrypted_store_writes_enc_and_preview_never_readable_png(contract):
    from signature_pipeline.store import S3CropStore, write_signatures_json
    sp = _privacy_or_skip()
    provider = sp.LocalKeyProvider.generate()
    s3, seen = _S3(), []
    pdf, (left, _) = contract
    store = S3CropStore(s3, encrypt=True, provider=provider, on_plain=lambda *a: seen.append(a))
    out = process_case("c1", {"d1": pdf}, FakeDetector({1: [left]}), store)
    keys = sorted(k for _, k in s3.objects)
    base = "cases/c1/analysis/d1/signatures/sig_01"
    assert keys == [base + ".png.enc", base + ".preview.png"]
    blob = s3.objects[("wonderfulkb-raw-document-storage", base + ".png.enc")]
    assert blob[:4] == b"WKBS" and b"PNG" not in blob[:64]
    plain = sp.decrypt_image(blob, sp.SignatureContext("c1", "d1", "sig_01"), provider)
    assert plain[:8] == b"\x89PNG\r\n\x1a\n"
    # the embedding hook got the same plaintext bytes, before encryption
    assert len(seen) == 1 and seen[0][:3] == ("c1", "d1", "sig_01") and seen[0][3] == plain
    sig = out["d1"]["signatures"][0]
    assert sig["crop_s3_key"] == base + ".png.enc" and sig["crop_encrypted"] is True and sig["crop_url"] is None
    write_signatures_json(out["d1"], s3)
    body = json.loads(s3.objects[("wonderfulkb-raw-document-storage", "cases/c1/analysis/d1/signatures.json")])
    assert body["signatures"][0]["crop_encrypted"] is True and "crop_url" not in body["signatures"][0]


def test_default_detector_chain_and_opt_in_vector():
    from signature_pipeline.detect import default_detector
    names = [type(d).__name__ for d in default_detector(FakeDetector({})).detectors]
    assert names == ["FakeDetector", "PageImageDetector", "LabelAnchoredDetector"]
    assert type(default_detector(FakeDetector({}), vector=True).detectors[-1]).__name__ == "VectorStrokeDetector"


def _stroke_png(seed=1, size=(300, 110)):
    import io
    from PIL import Image, ImageDraw
    from conftest import scribble
    img = Image.new("RGB", size, "white")
    ImageDraw.Draw(img).line([(x * size[0], y * size[1]) for x, y in scribble(seed)], fill=(10, 10, 90), width=3)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _page_with_images(placements):
    doc = pymupdf.open()
    page = doc.new_page()
    for rect, png in placements:
        page.insert_image(pymupdf.Rect(*rect), stream=png)
    return doc


def test_page_image_detector_finds_signature_sized_image_only():
    from signature_pipeline.detect import PageImageDetector
    png = _stroke_png()
    doc = _page_with_images([((100, 650, 250, 705), png),      # signature on the form
                             ((60, 30, 160, 70), png),         # logo at the top of the page
                             ((100, 300, 160, 310), png)])     # too small
    found = PageImageDetector().detect(doc)
    assert len(found) == 1 and found[0].detector == "page_images" and found[0].score is None
    x0, y0, x1, y1 = found[0].bbox
    assert x0 < 100 / 595 < 250 / 595 < x1 and y0 < 650 / 842 and y1 > 705 / 842   # box grown around the image


def test_page_image_detector_ignores_pages_of_text_as_images():
    from signature_pipeline.detect import PageImageDetector
    png = _stroke_png()
    doc = _page_with_images([((60, 200 + 40 * i, 200, 225 + 40 * i), png) for i in range(8)])
    assert PageImageDetector().detect(doc) == []


def test_combined_detector_adds_only_what_primary_missed():
    from signature_pipeline.detect import CombinedDetector, PageImageDetector
    png = _stroke_png()
    doc = _page_with_images([((100, 650, 250, 705), png), ((330, 650, 480, 705), png)])
    r = doc[0].rect
    found_by_primary = [100 / r.width, 650 / r.height, 250 / r.width, 705 / r.height]
    combined = CombinedDetector(FakeDetector({1: [found_by_primary]}), PageImageDetector()).detect(doc)
    assert [d.detector for d in combined].count("textract") == 1 and [d.detector for d in combined].count("page_images") == 1


def _bezier_scribble(page, rect, segments=12, color=(0, 0, 0.5)):
    shape = page.new_shape()
    w, h = rect.width / segments, rect.height
    for i in range(segments):
        x = rect.x0 + i * w
        shape.draw_bezier(pymupdf.Point(x, rect.y0 + h / 2), pymupdf.Point(x + w / 3, rect.y0),
                          pymupdf.Point(x + 2 * w / 3, rect.y1), pymupdf.Point(x + w, rect.y0 + h / 2))
    shape.finish(color=color, width=1.2, closePath=False)
    shape.commit()


def test_vector_stroke_detector_finds_curve_cluster_not_logo_or_few_curves():
    from signature_pipeline.detect import VectorStrokeDetector
    doc = pymupdf.open()
    page = doc.new_page()
    _bezier_scribble(page, pymupdf.Rect(100, 600, 230, 650))      # signature
    _bezier_scribble(page, pymupdf.Rect(60, 30, 160, 70))         # logo in the top margin
    _bezier_scribble(page, pymupdf.Rect(300, 400, 380, 440), segments=3)   # too few curves
    found = VectorStrokeDetector().detect(doc)
    assert len(found) == 1 and found[0].detector == "vector_strokes" and found[0].page == 1
    assert found[0].bbox[1] > 0.7


def test_label_anchored_detects_ink_above_podpis_but_not_printed_text():
    from signature_pipeline.detect import LabelAnchoredDetector
    doc = pymupdf.open()
    page = doc.new_page()
    from conftest import draw_scribble
    draw_scribble(page, 4, pymupdf.Rect(100, 600, 240, 650))
    text(page, (100, 660), "..............................", 10)      # printed dotted line
    text(page, (140, 676), "Podpis", 9)
    text(page, (350, 660), "..............................", 10)      # unsigned slot: only printed text
    text(page, (390, 676), "Podpis", 9)
    page.draw_line((330, 640), (520, 640))                           # table border above the unsigned slot
    found = LabelAnchoredDetector().detect(doc)
    assert len(found) == 1 and found[0].detector == "label_anchored"
    assert found[0].bbox[0] < 0.4         # the left slot only


def test_label_anchored_ignores_podpis_inside_sentences():
    from signature_pipeline.detect import LabelAnchoredDetector
    doc = pymupdf.open()
    page = doc.new_page()
    from conftest import draw_scribble
    draw_scribble(page, 4, pymupdf.Rect(100, 600, 240, 650))
    text(page, (60, 676), "Smlouva vzniká podpisem obou stran a platí od data podpis dohody smluvními stranami.", 8)
    assert LabelAnchoredDetector().detect(doc) == []


def test_combined_detector_merges_boxes_of_the_same_mark():
    from signature_pipeline.detect import CombinedDetector
    a = FakeDetector({1: [[0.10, 0.70, 0.30, 0.76]]})
    b = FakeDetector({1: [[0.12, 0.69, 0.28, 0.75], [0.60, 0.70, 0.80, 0.76]]})   # first overlaps, second is new
    assert len(CombinedDetector(a, b).detect(None)) == 2
