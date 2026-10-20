"""Redaction step (pipeline/redaction_step.py) without AWS: moto for S3/DynamoDB, LocalKeyProvider for the crops,
a fake detector instead of Textract. Synthetic PDFs only."""
import hashlib
import io
import json
import random

import boto3
import pytest
from PIL import Image, ImageDraw

from pipeline import Source, adapters, redaction_step, run_document
from pipeline.aws import Aws
from pipeline.config import Settings

from .conftest import BUCKET, FakeVision, analysis_row, text_pdf

pymupdf = pytest.importorskip("pymupdf")
adapters._ensure_path()
privacy = pytest.importorskip("signature_privacy")
from signature_pipeline.models import Detection  # noqa: E402

PAGE_W, PAGE_H = 595, 842
SIG_RECT = pymupdf.Rect(80, 640, 260, 700)
SIG_BBOX = [SIG_RECT.x0 / PAGE_W, SIG_RECT.y0 / PAGE_H, SIG_RECT.x1 / PAGE_W, SIG_RECT.y1 / PAGE_H]
CASE, DOC = "c1", "d1"
PREFIX = f"cases/{CASE}/analysis/{DOC}/"


def signature_png(seed=7):
    rng = random.Random(seed)
    image = Image.new("RGB", (360, 120), "white")
    draw = ImageDraw.Draw(image)
    for _ in range(6):
        points = [(rng.randint(10, 350), rng.randint(10, 110)) for _ in range(7)]
        draw.line(points, fill=(20, 20, 160), width=4)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def signed_pdf(label=True, seed=7):
    """Text page with a signature scan placed above the label 'Podpis kupujiciho'."""
    doc = pymupdf.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    page.insert_text((50, 80), "Kupni smlouva c. 2026/001 mezi prodavajicim a kupujicim", fontsize=11)
    page.insert_text((50, 100), "Cena plneni cini 1 250 000 Kc bez DPH, splatnost 30 dnu", fontsize=11)
    page.insert_image(SIG_RECT, stream=signature_png(seed))
    if label:
        page.insert_text((80, 735), "Podpis kupujiciho", fontsize=10)
    return doc.tobytes()


class FakeDetector:
    def __init__(self, bboxes=(SIG_BBOX,), fail=False):
        self.bboxes, self.fail, self.calls = bboxes, fail, 0

    def detect(self, doc):
        self.calls += 1
        if self.fail:
            raise RuntimeError("Textract is down")
        return [Detection(1, list(b), "textract", 30.0, {"role": "buyer", "role_evidence": "Podpis kupujiciho"})
                for b in self.bboxes]


@pytest.fixture
def provider():
    return privacy.LocalKeyProvider.generate()


@pytest.fixture
def opts(make_options, provider):
    def make(detector=None, skip=("classify", "embed", "copy"), **kwargs):  # copy: the case step is tested in test_copies
        options = make_options(skip=skip, redact=True, **kwargs)
        options.key_provider = provider
        options.signature_detector = detector if detector is not None else FakeDetector()
        return options
    return make


def keys(s3, prefix=f"cases/{CASE}/"):
    out = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
        out += [o["Key"] for o in page.get("Contents", [])]
    return sorted(out)


def get(s3, key):
    return s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()


def region_mean(pdf_bytes, rect=SIG_RECT, dpi=72):
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        pix = doc[0].get_pixmap(dpi=dpi, clip=rect, colorspace=pymupdf.csGRAY, alpha=False)
        return sum(pix.samples) / len(pix.samples)
    finally:
        doc.close()


def image_hashes(pdf_bytes):
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return {hashlib.sha256(doc.xref_stream_raw(img[0])).hexdigest() for page in doc for img in page.get_images()}
    finally:
        doc.close()


def test_redacted_copy_has_no_signature_under_the_mask(ingest, opts, aws_env):
    original = signed_pdf()
    ingest(CASE, DOC, original, "smlouva.pdf")
    assert region_mean(original) > 200 and image_hashes(original)  # the signature is really there
    row = run_document(CASE, DOC, options=opts())
    assert row["processing_status"] == "completed"
    masked = get(aws_env, f"cases/{CASE}/redacted/{DOC}.pdf")
    assert region_mean(masked) < 8                                  # black where the signature was
    assert not (image_hashes(original) & image_hashes(masked))      # and the image stream is gone from the file
    assert signature_png() not in masked
    doc = pymupdf.open(stream=masked, filetype="pdf")
    assert "Kupni smlouva" in doc[0].get_text() and "Podpis kupujiciho" in doc[0].get_text()  # text stays
    doc.close()
    head = aws_env.head_object(Bucket=BUCKET, Key=f"cases/{CASE}/redacted/{DOC}.pdf")["Metadata"]
    assert head["original-sha256"] == hashlib.sha256(original).hexdigest() and head["original-size"] == str(len(original))
    assert get(aws_env, f"cases/{CASE}/original/{DOC}.pdf") == original  # the original stays where it was


def test_row_and_signatures_json_have_the_new_shape(ingest, opts, aws_env, provider):
    original = signed_pdf()
    ingest(CASE, DOC, original)
    row = run_document(CASE, DOC, options=opts())
    assert row["original_sha256"] == hashlib.sha256(original).hexdigest()
    assert row["redacted_s3_key"] == f"cases/{CASE}/redacted/{DOC}.pdf"
    assert row["signatures_s3_key"] == PREFIX + "signatures.json"
    assert analysis_row(CASE, DOC) == row
    body = json.loads(get(aws_env, PREFIX + "signatures.json"))
    assert [s["signature_id"] for s in body["signatures"]] == ["sig_01"]
    sig = body["signatures"][0]
    assert sig["crop_s3_key"] == PREFIX + "signatures/sig_01.png.enc" and sig["crop_encrypted"] is True
    assert sig["preview_s3_key"] == PREFIX + "signatures/sig_01.preview.png"
    assert "crop_url" not in sig and "crop_source" not in sig
    assert sig["role"] == "buyer" and sig["phash"] and sig["copy_suspicion"] == {"level": "not_checked", "matches": []}
    assert sig["detector"] == "textract" and sig["page"] == 1
    # nothing readable under signatures/: only the encrypted crop and the distorted preview
    assert [k for k in keys(aws_env) if "/signatures/" in k] == [PREFIX + "signatures/sig_01.png.enc",
                                                                 PREFIX + "signatures/sig_01.preview.png"]
    blob = get(aws_env, sig["crop_s3_key"])
    assert blob.startswith(privacy.MAGIC) and b"\x89PNG" not in blob
    shown = privacy.decrypt_image(blob, privacy.SignatureContext(CASE, DOC, "sig_01"), provider)
    assert shown.startswith(b"\x89PNG") and Image.open(io.BytesIO(shown)).size[0] > 100
    preview = get(aws_env, sig["preview_s3_key"])
    assert preview != shown and Image.open(io.BytesIO(preview)).format == "PNG"
    with pytest.raises(privacy.DecryptionError):  # bound to case/document/signature
        privacy.decrypt_image(blob, privacy.SignatureContext("other", DOC, "sig_01"), provider)


def test_pages_text_and_visual_input_are_built_from_the_masked_copy(ingest, opts, aws_env):
    ingest(CASE, DOC, signed_pdf())
    row = run_document(CASE, DOC, options=opts())
    page = Image.open(io.BytesIO(get(aws_env, PREFIX + "pages/1.png"))).convert("L")
    w, h = page.size
    box = (int(SIG_BBOX[0] * w), int(SIG_BBOX[1] * h), int(SIG_BBOX[2] * w), int(SIG_BBOX[3] * h))
    inner = page.crop((box[0] + 4, box[1] + 4, box[2] - 4, box[3] - 4))
    assert sum(inner.getdata()) / (inner.size[0] * inner.size[1]) < 12  # the rendered page is black there
    assert "Kupni smlouva" in get(aws_env, row["text_s3_key"]).decode()


def test_scan_transcription_reads_the_masked_render_and_caches_apart(ingest, opts, aws_env):
    """A scan: the visual call gets the masked page; the cache lives in vision/<model>/redacted/."""
    doc = pymupdf.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    page.insert_image(pymupdf.Rect(0, 0, PAGE_W, PAGE_H), stream=signature_png(3))  # page = one image
    ingest(CASE, DOC, doc.tobytes())
    seen = []

    class Spy(FakeVision):
        def transcribe(self, png, label=None):
            seen.append(png)
            return super().transcribe(png, label)

    options = opts(detector=FakeDetector(bboxes=[[0.1, 0.7, 0.5, 0.8]]), vision=Spy())
    row = run_document(CASE, DOC, options=options)
    assert seen and row["processing_status"] == "completed"
    image = Image.open(io.BytesIO(seen[0])).convert("L")
    w, h = image.size
    inner = image.crop((int(0.12 * w), int(0.72 * h), int(0.48 * w), int(0.78 * h)))
    assert sum(inner.getdata()) / (inner.size[0] * inner.size[1]) < 12      # black where the signature was
    assert any("/vision/" in k and "/redacted/" in k for k in keys(aws_env))
    assert not any("/vision/" in k and "/redacted/" not in k for k in keys(aws_env))


def test_label_zone_masks_a_signature_the_detector_missed(ingest, opts, aws_env):
    original = signed_pdf()
    ingest(CASE, DOC, original)
    detector = FakeDetector(bboxes=[])
    row = run_document(CASE, DOC, options=opts(detector=detector))
    masked = get(aws_env, row["redacted_s3_key"])
    assert detector.calls == 1 and not image_hashes(masked)           # the zone above the label removed the image
    assert json.loads(get(aws_env, PREFIX + "signatures.json"))["signatures"] == []
    assert not [k for k in keys(aws_env) if "/signatures/" in k]


def test_verification_failure_stops_the_document(ingest, opts, aws_env, monkeypatch):
    ingest(CASE, DOC, signed_pdf())
    monkeypatch.setattr(privacy, "verify_redacted", lambda *a, **k: ["strana 1: oblast full není černá"])
    row = run_document(CASE, DOC, options=opts())
    assert row["processing_status"] == "failed"
    assert json.loads(get(aws_env, PREFIX + "run.json"))["error"] == "REDACTION_VERIFY_FAILED"
    assert keys(aws_env) == [f"cases/{CASE}/analysis/{DOC}/run.json", f"cases/{CASE}/original/{DOC}.pdf"]


def test_a_redaction_that_removed_nothing_is_caught_by_the_real_verification(ingest, opts, aws_env, monkeypatch):
    ingest(CASE, DOC, signed_pdf())
    monkeypatch.setattr(privacy, "redact_pdf", lambda data, regions: data)   # "redaction" returns the readable file
    row = run_document(CASE, DOC, options=opts())
    assert row["processing_status"] == "failed"
    assert json.loads(get(aws_env, PREFIX + "run.json"))["error"] == "REDACTION_VERIFY_FAILED"
    assert not [k for k in keys(aws_env) if "/redacted/" in k or "/pages/" in k or k.endswith("text.txt")]


def test_redaction_crash_writes_nothing(ingest, opts, aws_env, monkeypatch):
    ingest(CASE, DOC, signed_pdf())

    def boom(data, regions):
        raise RuntimeError("PyMuPDF broke")
    monkeypatch.setattr(privacy, "redact_pdf", boom)
    row = run_document(CASE, DOC, options=opts())
    assert row["processing_status"] == "failed"
    assert json.loads(get(aws_env, PREFIX + "run.json"))["error"] == "REDACTION_FAILED"
    assert keys(aws_env) == [PREFIX + "run.json", f"cases/{CASE}/original/{DOC}.pdf"]


def test_kms_failure_leaves_no_readable_or_partial_result(ingest, opts, aws_env, provider, monkeypatch):
    ingest(CASE, DOC, signed_pdf())

    def no_kms(context):
        raise privacy.PrivacyError("KMS unavailable")
    monkeypatch.setattr(provider, "generate_data_key", no_kms)
    row = run_document(CASE, DOC, options=opts())
    assert row["processing_status"] == "failed"
    assert json.loads(get(aws_env, PREFIX + "run.json"))["error"] == "CROP_ENCRYPTION_FAILED"
    # no masked copy without the means to show the signature, no signatures.json, no crop, no page, no text
    assert keys(aws_env) == [PREFIX + "run.json", f"cases/{CASE}/original/{DOC}.pdf"]


def test_missing_key_provider_stops_before_detection(ingest, make_options, monkeypatch, aws_env):
    monkeypatch.delenv("PRIVACY_KMS_KEY_ID", raising=False)
    monkeypatch.delenv("WKB_LOCAL_MASTER_KEY", raising=False)
    monkeypatch.setattr(privacy.keys, "_default", None)
    ingest(CASE, DOC, signed_pdf())
    detector = FakeDetector()
    options = make_options(skip=("classify", "embed"), redact=True)
    options.signature_detector = detector
    row = run_document(CASE, DOC, options=options)
    assert row["processing_status"] == "failed" and detector.calls == 0
    assert json.loads(get(aws_env, PREFIX + "run.json"))["error"] == "ENCRYPTION_UNAVAILABLE"


def test_detection_failure_stops_the_document(ingest, opts, aws_env):
    ingest(CASE, DOC, signed_pdf())
    row = run_document(CASE, DOC, options=opts(detector=FakeDetector(fail=True)))
    assert row["processing_status"] == "failed"
    assert json.loads(get(aws_env, PREFIX + "run.json"))["error"] == "SIGNATURE_DETECTION_FAILED"
    assert keys(aws_env) == [PREFIX + "run.json", f"cases/{CASE}/original/{DOC}.pdf"]


def test_not_a_pdf_keeps_its_error_code(ingest, opts, aws_env):
    ingest(CASE, DOC, b"just text")
    row = run_document(CASE, DOC, options=opts())
    assert row["processing_status"] == "failed"
    assert json.loads(get(aws_env, PREFIX + "run.json"))["error"] == "NOT_A_PDF"


def test_rerun_overwrites_the_same_keys_and_keeps_the_ids(ingest, opts, aws_env):
    ingest(CASE, DOC, signed_pdf())
    detector = FakeDetector()
    run_document(CASE, DOC, options=opts(detector=detector))
    first = keys(aws_env)
    first_body = json.loads(get(aws_env, PREFIX + "signatures.json"))
    row = run_document(CASE, DOC, options=opts(detector=detector))
    assert keys(aws_env) == first and row["processing_status"] == "completed"
    assert detector.calls == 1                                      # the stored findings are reused, no second Textract
    again = json.loads(get(aws_env, PREFIX + "signatures.json"))
    assert [s["signature_id"] for s in again["signatures"]] == ["sig_01"]
    assert again["signatures"][0] == first_body["signatures"][0]


def test_stored_findings_from_elsewhere_are_used_and_their_readable_crop_is_not_touched(ingest, opts, aws_env):
    ingest(CASE, DOC, signed_pdf())
    legacy = {"case_id": CASE, "document_id": DOC, "signatures": [{
        "signature_id": "sig_01", "page": 1, "bbox": SIG_BBOX, "detector": "textract", "detection_score": 26.0,
        "role": "borrower", "role_source": "nearest_text", "role_evidence": "Prijemce:", "phash": "70419f25363566c7",
        "crop_s3_key": PREFIX + "signatures/sig_01.png",
        "copy_suspicion": {"level": "suspected", "matches": [{"signature_id": "sig_01", "document_id": "x", "score": 0.99}]}}]}
    aws_env.put_object(Bucket=BUCKET, Key=PREFIX + "signatures.json", Body=json.dumps(legacy).encode())
    aws_env.put_object(Bucket=BUCKET, Key=PREFIX + "signatures/sig_01.png", Body=b"legacy readable crop")
    detector = FakeDetector()
    run_document(CASE, DOC, options=opts(detector=detector))
    assert detector.calls == 0
    sig = json.loads(get(aws_env, PREFIX + "signatures.json"))["signatures"][0]
    assert sig["role"] == "borrower" and sig["phash"] == "70419f25363566c7" and sig["detection_score"] == 26.0
    assert sig["copy_suspicion"]["level"] == "suspected"            # findings made elsewhere survive
    assert sig["crop_s3_key"].endswith(".png.enc") and sig["crop_encrypted"] is True and "crop_url" not in sig
    assert get(aws_env, PREFIX + "signatures/sig_01.png") == b"legacy readable crop"  # nothing is deleted here


def test_mismatching_stored_ids_stop_the_document(ingest, opts, aws_env):
    ingest(CASE, DOC, signed_pdf())
    stored = {"signatures": [{"signature_id": "sig_07", "page": 1, "bbox": SIG_BBOX, "detector": "textract"}]}
    aws_env.put_object(Bucket=BUCKET, Key=PREFIX + "signatures.json", Body=json.dumps(stored).encode())
    row = run_document(CASE, DOC, options=opts())
    assert row["processing_status"] == "failed"
    assert json.loads(get(aws_env, PREFIX + "run.json"))["error"] == "STORED_SIGNATURES_MISMATCH"
    assert not [k for k in keys(aws_env) if "/redacted/" in k]


def test_skipped_signatures_still_mask_but_write_no_crops_and_need_no_key(ingest, make_options, aws_env, monkeypatch):
    monkeypatch.delenv("PRIVACY_KMS_KEY_ID", raising=False)
    monkeypatch.delenv("WKB_LOCAL_MASTER_KEY", raising=False)
    monkeypatch.setattr(privacy.keys, "_default", None)
    original = signed_pdf()
    ingest(CASE, DOC, original)
    detector = FakeDetector()
    options = make_options(skip=("classify", "embed", "signatures"), redact=True)
    options.signature_detector = detector
    row = run_document(CASE, DOC, options=options)
    assert row["processing_status"] == "completed" and detector.calls == 0
    masked = get(aws_env, row["redacted_s3_key"])
    assert not image_hashes(masked)                                  # label zone
    assert "signatures_s3_key" not in row and not [k for k in keys(aws_env) if "signatures" in k]


def test_crops_are_embedded_from_memory_and_signature_embedding_can_be_skipped(ingest, opts, aws_env, monkeypatch):
    ingest(CASE, DOC, signed_pdf())
    seen = []
    monkeypatch.setattr(adapters, "write_vectors", lambda *a, **k: None)
    monkeypatch.setattr(adapters, "write_signature_vectors",
                        lambda case, doc, crops, label=None: seen.append((case, doc, crops, label)))
    row = run_document(CASE, DOC, options=opts(skip=("classify",)))
    assert row["processing_status"] == "completed"
    (case, doc, crops, _), = seen
    assert (case, doc) == (CASE, DOC) and len(crops) == 1 and crops[0][0] == 1
    assert crops[0][1].startswith(b"\x89PNG")                        # the readable crop, taken from memory
    seen.clear()
    run_document(CASE, DOC, options=opts(skip=("classify", "embed")))
    assert seen == []


def test_signature_embedding_failure_degrades_the_status_only(ingest, opts, aws_env, monkeypatch):
    ingest(CASE, DOC, signed_pdf())
    monkeypatch.setattr(adapters, "write_vectors", lambda *a, **k: None)

    def boom(*a, **k):
        raise RuntimeError("Titan throttled")
    monkeypatch.setattr(adapters, "write_signature_vectors", boom)
    row = run_document(CASE, DOC, options=opts(skip=("classify",)))
    assert row["processing_status"] == "partial"
    assert json.loads(get(aws_env, PREFIX + "run.json"))["steps"]["signature_embed"]["status"] == "failed"
    assert get(aws_env, row["redacted_s3_key"])                     # masked copy and crops are in place anyway


def test_nothing_readable_in_logs_or_temp_files(ingest, opts, aws_env, caplog, monkeypatch):
    import tempfile

    def no_temp(*a, **k):
        raise AssertionError("the redaction path must not touch the disk")
    for name in ("mkstemp", "mkdtemp", "NamedTemporaryFile", "TemporaryFile", "TemporaryDirectory"):
        monkeypatch.setattr(tempfile, name, no_temp)
    ingest(CASE, DOC, signed_pdf())
    caplog.set_level("DEBUG")
    row = run_document(CASE, DOC, options=opts())
    assert row["processing_status"] == "completed"
    assert "PNG" not in caplog.text and "\\x89" not in caplog.text


def test_report_describes_the_step_without_data(ingest, opts, aws_env):
    ingest(CASE, DOC, signed_pdf())
    run_document(CASE, DOC, options=opts())
    info = json.loads(get(aws_env, PREFIX + "run.json"))["redaction"]
    assert info["status"] == "ok" and info["detection"] == "detected" and info["signatures"] == 1
    assert info["regions"]["full"] == 1 and info["regions"]["graphics"] >= 1 and info["encrypted_crops"] == 1
    assert info["redacted_s3_key"] == f"cases/{CASE}/redacted/{DOC}.pdf"


def test_redaction_off_is_loud_and_keeps_the_old_path(ingest, make_options, aws_env, caplog):
    ingest(CASE, DOC, signed_pdf())
    row = run_document(CASE, DOC, options=make_options(skip=("classify", "embed", "signatures"), redact=False))
    assert row["processing_status"] == "completed"
    assert "redacted_s3_key" not in row and "original_sha256" not in row
    assert "PIPELINE_REDACT is off" in caplog.text
    assert not [k for k in keys(aws_env) if "/redacted/" in k]
    assert json.loads(get(aws_env, PREFIX + "run.json"))["redaction"] == {"status": "disabled"}


def test_env_switch(monkeypatch):
    monkeypatch.delenv("PIPELINE_REDACT", raising=False)
    assert Settings().redact is True
    for value in ("0", "false", "No", "off"):
        monkeypatch.setenv("PIPELINE_REDACT", value)
        assert Settings().redact is False
    monkeypatch.setenv("PIPELINE_REDACT", "1")
    assert Settings().redact is True


def test_a_masked_input_is_processed_but_never_re_cut(ingest, opts, aws_env):
    """After a migration `s3_key` may point to redacted/…: no detection, no crops, no overwrite, hash from metadata."""
    original = signed_pdf()
    ingest(CASE, DOC, original)
    run_document(CASE, DOC, options=opts())
    masked_key = f"cases/{CASE}/redacted/{DOC}.pdf"
    before = {k: get(aws_env, k) for k in keys(aws_env) if "/signatures/" in k or k.endswith("signatures.json") or k == masked_key}
    detector = FakeDetector()
    row = run_document("c2", None, source=Source(masked_key, "masked.pdf"), options=opts(detector=detector))
    assert detector.calls == 0 and row["processing_status"] == "completed"
    assert row["original_sha256"] == hashlib.sha256(original).hexdigest() and row["redacted_s3_key"] == masked_key
    assert {k: get(aws_env, k) for k in before} == before
    assert not [k for k in keys(aws_env, "cases/c2/") if "/signatures/" in k or "/redacted/" in k]


def test_resume_redoes_a_document_that_has_no_masked_copy(ingest, opts, aws_env):
    ingest(CASE, DOC, signed_pdf())
    plain = Settings(skip=frozenset({"classify", "embed", "signatures"}), redact=False)
    from pipeline import Options
    run_document(CASE, DOC, options=Options(settings=plain, vision=FakeVision()))
    row = analysis_row(CASE, DOC)
    assert row["processing_status"] == "completed" and "redacted_s3_key" not in row
    options = opts(skip=("classify", "embed"), resume=True)
    again = run_document(CASE, DOC, options=options)
    assert again["redacted_s3_key"]                                 # reprocessed, not skipped
    skipped = run_document(CASE, DOC, options=opts(skip=("classify", "embed"), resume=True))
    assert skipped == again                                         # now it is done


def test_copy_check_never_takes_a_masked_pdf_for_the_original(aws_env, ingest):
    from pipeline import copies
    ingest(CASE, DOC, signed_pdf())
    aws = Aws(Settings())
    aws_env.put_object(Bucket=BUCKET, Key=f"cases/{CASE}/redacted/{DOC}.pdf", Body=signed_pdf())
    boto3.resource("dynamodb", region_name="eu-central-1").Table("wonderfulkb-uw-documents").update_item(
        Key={"case_id": CASE, "document_id": DOC}, UpdateExpression="SET s3_key = :k",
        ExpressionAttributeValues={":k": f"cases/{CASE}/redacted/{DOC}.pdf"})
    aws_env.delete_object(Bucket=BUCKET, Key=f"cases/{CASE}/original/{DOC}.pdf")
    assert copies._find_pdfs(aws, CASE, {DOC}) == {}


# --- shape for documents that reuse the analysis of an identical one (dedup) ---------------------------------

def test_reuse_entries_point_to_the_source_crop_and_keep_its_context():
    entries = [{"signature_id": "sig_01", "crop_s3_key": "cases/a/analysis/x/signatures/sig_01.png.enc",
                "crop_encrypted": True, "crop_url": "http://x", "phash": "00"}]
    (entry,) = redaction_step.reuse_signature_entries(entries, "a", "x")
    assert entry["crop_source"] == {"case_id": "a", "document_id": "x", "signature_id": "sig_01"}
    assert entry["crop_s3_key"] == "cases/a/analysis/x/signatures/sig_01.png.enc"
    assert entry["preview_s3_key"] == "cases/a/analysis/x/signatures/sig_01.preview.png" and "crop_url" not in entry
    chained = redaction_step.reuse_signature_entries([entry], "b", "y")[0]
    assert chained["crop_source"]["case_id"] == "a"                  # a chain stays one hop: the root context
    with pytest.raises(ValueError):
        redaction_step.reuse_signature_entries([{"signature_id": "sig_01", "crop_s3_key": "k/sig_01.png"}], "a", "x")


def _fake_reuse(monkeypatch, origin, src_prefix):
    """dedup stand-in: find_source returns `origin`; reuse_analysis copies signatures.json like dedup/reuse.py does."""
    calls = []

    def reuse_analysis(aws, source, case_id, document_id, title, *, skip, previous, pipeline_version, now):
        calls.append(document_id)
        prefix = f"cases/{case_id}/analysis/{document_id}/"
        body = json.loads(aws.get_bytes(src_prefix + "signatures.json"))
        body.update(case_id=case_id, document_id=document_id)
        aws.put_bytes(prefix + "text.txt", b"copied text", "text/plain")
        aws.put_bytes(prefix + "signatures.json", json.dumps(body).encode(), "application/json")
        return ({"case_id": case_id, "document_id": document_id, "title": title, "page_count": 1,
                 "text_s3_key": prefix + "text.txt", "label_status": "predicted", "pipeline_version": pipeline_version,
                 "processing_status": "completed", "description": "d", "updated_at": now(),
                 "signatures_s3_key": prefix + "signatures.json"}, {"reused_from": {"case_id": source["case_id"],
                                                                                   "document_id": source["document_id"]}})
    monkeypatch.setattr(adapters, "dedup", lambda name: {"find_source": lambda aws, sha, case: origin,
                                                         "reuse_analysis": reuse_analysis,
                                                         "register": lambda *a: None}[name])
    return calls


def test_a_duplicate_gets_its_own_masked_copy_and_crops_tied_to_the_source(ingest, opts, aws_env, monkeypatch):
    original = signed_pdf()
    ingest(CASE, DOC, original)
    source_row = run_document(CASE, DOC, options=opts())
    ingest("c9", "d9", original)
    calls = _fake_reuse(monkeypatch, source_row, PREFIX)
    detector = FakeDetector()
    row = run_document("c9", "d9", options=opts(detector=detector))
    assert calls == ["d9"] and detector.calls == 0                   # reused, nothing detected for d9
    assert row["redacted_s3_key"] == "cases/c9/redacted/d9.pdf"
    assert row["original_sha256"] == hashlib.sha256(original).hexdigest()
    assert get(aws_env, row["redacted_s3_key"]) == get(aws_env, f"cases/{CASE}/redacted/{DOC}.pdf")
    head = aws_env.head_object(Bucket=BUCKET, Key=row["redacted_s3_key"])["Metadata"]
    assert head["original-sha256"] == row["original_sha256"]
    sig = json.loads(get(aws_env, "cases/c9/analysis/d9/signatures.json"))["signatures"][0]
    assert sig["crop_s3_key"] == PREFIX + "signatures/sig_01.png.enc"
    assert sig["crop_source"] == {"case_id": CASE, "document_id": DOC, "signature_id": "sig_01"}
    assert not [k for k in keys(aws_env, "cases/c9/") if "/signatures/" in k]   # no second copy of any crop


def test_an_unmasked_source_is_not_reused(ingest, opts, aws_env, monkeypatch):
    ingest("c9", "d9", signed_pdf())
    legacy_origin = {"case_id": CASE, "document_id": DOC, "processing_status": "completed", "text_s3_key": "x"}
    calls = _fake_reuse(monkeypatch, legacy_origin, PREFIX)
    row = run_document("c9", "d9", options=opts())
    assert calls == [] and row["redacted_s3_key"] == "cases/c9/redacted/d9.pdf"
    assert json.loads(get(aws_env, "cases/c9/analysis/d9/run.json"))["reuse"]["status"] == "source_not_redacted"


def _signature_ink(png):
    """Mean grey inside the signature box of a page render (dark ink: low, black mask: ~0, empty paper: ~255)."""
    page = Image.open(io.BytesIO(png)).convert("L")
    w, h = page.size
    inner = page.crop((int(SIG_BBOX[0] * w) + 4, int(SIG_BBOX[1] * h) + 4, int(SIG_BBOX[2] * w) - 4, int(SIG_BBOX[3] * h) - 4))
    return sum(inner.getdata()) / (inner.size[0] * inner.size[1])


def test_original_pages_are_readable_renders_the_size_of_the_masked_pages(ingest, opts, aws_env):
    ingest(CASE, DOC, signed_pdf())
    row = run_document(CASE, DOC, options=opts())
    assert row["processing_status"] == "completed"
    original = get(aws_env, f"cases/{CASE}/original-pages/{DOC}/1.png")
    masked = get(aws_env, PREFIX + "pages/1.png")
    assert Image.open(io.BytesIO(original)).size == Image.open(io.BytesIO(masked)).size  # the same boxes fit both
    assert _signature_ink(masked) < 12 < 40 < _signature_ink(original) < 250              # black mask vs. ink on paper
    tags = aws_env.get_object_tagging(Bucket=BUCKET, Key=f"cases/{CASE}/original-pages/{DOC}/1.png")["TagSet"]
    assert tags == [{"Key": "project", "Value": "wonderfulkb"}]
    step = json.loads(get(aws_env, PREFIX + "run.json"))["steps"]["original_pages"]
    assert step["status"] == "ok" and step["pages"] == 1


def test_a_duplicate_gets_its_own_original_pages(ingest, opts, aws_env, monkeypatch):
    original = signed_pdf()
    ingest(CASE, DOC, original)
    source_row = run_document(CASE, DOC, options=opts())
    ingest("c9", "d9", original)
    _fake_reuse(monkeypatch, source_row, PREFIX)
    run_document("c9", "d9", options=opts(detector=FakeDetector()))
    assert get(aws_env, "cases/c9/original-pages/d9/1.png") == get(aws_env, f"cases/{CASE}/original-pages/{DOC}/1.png")


def test_a_masked_input_gets_no_original_pages(ingest, opts, aws_env):
    ingest(CASE, DOC, signed_pdf())
    run_document(CASE, DOC, options=opts())
    run_document("c2", None, source=Source(f"cases/{CASE}/redacted/{DOC}.pdf", "masked.pdf"), options=opts())
    assert not [k for k in keys(aws_env, "cases/c2/") if "/original-pages/" in k]


def test_a_failed_original_render_does_not_degrade_the_document(ingest, opts, aws_env, monkeypatch):
    from pipeline import pdf as pdfmod
    real = pdfmod.render_png
    calls = []

    def first_call_fails(*args):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("render failed")
        return real(*args)
    monkeypatch.setattr(pdfmod, "render_png", first_call_fails)
    ingest(CASE, DOC, signed_pdf())
    row = run_document(CASE, DOC, options=opts())
    assert row["processing_status"] == "completed"
    assert json.loads(get(aws_env, PREFIX + "run.json"))["steps"]["original_pages"]["status"] == "failed"
    assert not [k for k in keys(aws_env) if "/original-pages/" in k]


def test_original_pages_case_renders_only_the_original_pages(ingest, opts, aws_env):
    from pipeline import original_pages_case
    ingest(CASE, DOC, signed_pdf())
    ingest(CASE, "d2", signed_pdf(seed=3))
    assert original_pages_case(CASE, opts(), ["d2"]) == [{"document_id": "d2", "title": "doc.pdf", "status": "ok",
                                                          "seconds": pytest.approx(0, abs=30), "pages": 1}]
    assert keys(aws_env) == sorted([f"cases/{CASE}/original/{DOC}.pdf", f"cases/{CASE}/original/d2.pdf",
                                    f"cases/{CASE}/original-pages/d2/1.png"])
