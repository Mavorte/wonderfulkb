import json
from decimal import Decimal

import pytest

from pipeline import DocumentNotFound, Source, adapters, run_case, run_document

from .conftest import BUCKET, FakeVision, analysis_row, mixed_pdf, scan_pdf, text_pdf

LONG = ["Kupni smlouva c. 2026/001 mezi prodavajicim a kupujicim", "Cena plneni cini 1 250 000 Kc bez DPH"]


def s3_text(s3, key):
    return s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode()


def test_text_pdf_uses_text_layer_without_vision(ingest, make_options, aws_env):
    ingest("c1", "d1", text_pdf(LONG, LONG), "smlouva.pdf")
    options = make_options()
    row = run_document("c1", "d1", options=options)
    assert options.vision.calls == 0
    assert row["processing_status"] == "completed"
    assert row["page_count"] == 2 and row["title"] == "smlouva.pdf" and "pages_failed" not in row
    text = s3_text(aws_env, row["text_s3_key"])
    assert row["text_s3_key"] == "cases/c1/analysis/d1/text.txt"
    assert text.count("\f") == 1 and "1 250 000" in text.split("\f")[1]
    for n in (1, 2):
        assert aws_env.get_object(Bucket=BUCKET, Key=f"cases/c1/analysis/d1/pages/{n}.png")["Body"].read(4) == b"\x89PNG"
    assert analysis_row("c1", "d1") == row
    report = json.loads(s3_text(aws_env, "cases/c1/analysis/d1/run.json"))
    assert [p["method"] for p in report["pages"]] == ["text_layer", "text_layer"]


def test_row_has_exactly_the_contract_attributes(ingest, make_options):
    ingest("c1", "d1", text_pdf(LONG))
    row = run_document("c1", "d1", options=make_options())
    allowed = {"case_id", "document_id", "title", "label", "label_status", "description", "confidence", "page_count",
               "processing_status", "pages_failed", "text_s3_key", "signatures_s3_key", "pipeline_version", "updated_at"}
    assert set(row) <= allowed
    assert row["label_status"] == "predicted" and row["description"].startswith("Kupni smlouva")
    assert row["updated_at"].endswith("Z")


def test_scan_goes_to_vision_and_is_cached(ingest, make_options, aws_env):
    ingest("c1", "d1", mixed_pdf())
    options = make_options()
    row = run_document("c1", "d1", options=options)
    assert options.vision.calls == 1 and row["processing_status"] == "completed"
    text = s3_text(aws_env, row["text_s3_key"])
    first, second = text.split("\f")
    assert "Smlouva o zajisteni" in first and second == "PŘEPIS SKENU 1"
    report = json.loads(s3_text(aws_env, "cases/c1/analysis/d1/run.json"))
    assert [p["method"] for p in report["pages"]] == ["text_layer", "vision"]
    assert report["pages"][1]["reason"] == "NATIVE_TEXT_MISSING_OR_TOO_SHORT"
    again = run_document("c1", "d1", options=options)  # idempotent, and the transcript comes from the S3 cache
    assert options.vision.calls == 1
    assert again["text_s3_key"] == row["text_s3_key"] and s3_text(aws_env, again["text_s3_key"]) == text


def test_scan_with_text_footer_is_still_a_scan(ingest, make_options, aws_env):
    import io

    import pypdf
    footer = pypdf.PdfReader(io.BytesIO(text_pdf(["Vygenerovano systemem dne 1. 1. 2026 stranka 1 z 1 zapati"])))
    writer = pypdf.PdfWriter(clone_from=io.BytesIO(scan_pdf()))
    writer.pages[0].merge_page(footer.pages[0])
    out = io.BytesIO()
    writer.write(out)
    ingest("c1", "d1", out.getvalue())
    options = make_options()
    run_document("c1", "d1", options=options)
    assert options.vision.calls == 1
    report = json.loads(s3_text(aws_env, "cases/c1/analysis/d1/run.json"))
    assert report["pages"][0]["reason"] == "PAGE_HAS_DOMINANT_RASTER_IMAGE"


def test_failed_scan_page_makes_document_partial(ingest, make_options):
    ingest("c1", "d1", mixed_pdf())
    row = run_document("c1", "d1", options=make_options(vision=FakeVision(fail_pages={1})))
    assert row["processing_status"] == "partial"
    assert row["pages_failed"] == {2} and row["page_count"] == 2


def test_all_pages_failing_is_failed_but_text_object_exists(ingest, make_options):
    ingest("c1", "d1", scan_pdf(2))
    row = run_document("c1", "d1", options=make_options(vision=FakeVision(fail_pages={1, 2})))
    assert row["processing_status"] == "failed" and row["pages_failed"] == {1, 2}


def test_no_vision_flag_does_not_call_bedrock(ingest, make_options):
    ingest("c1", "d1", scan_pdf())
    options = make_options(no_vision=True)
    row = run_document("c1", "d1", options=options)
    assert options.vision.calls == 0 and row["pages_failed"] == {1}


def test_force_vision_transcribes_text_pages_too(ingest, make_options):
    ingest("c1", "d1", text_pdf(LONG))
    options = make_options(force_vision=True)
    run_document("c1", "d1", options=options)
    assert options.vision.calls == 1


def test_downstream_steps_receive_contract_arguments(ingest, make_options, monkeypatch):
    ingest("c1", "d1", text_pdf(LONG, LONG), "s.pdf")
    seen = {}

    def classify(text, title, page_count):
        seen["classify"] = (text, title, page_count)
        return {"label": "kupni_smlouva", "label_status": "predicted", "description": "Kupní smlouva", "confidence": 0.8731}

    def vectors(case_id, document_id, text, page_pngs, label=None):
        seen["vectors"] = (case_id, document_id, len(page_pngs), label)

    def signatures(path, case_id, document_id, s3, bucket):
        assert open(path, "rb").read(5) == b"%PDF-"
        return [{"signature_id": "sig_01", "page": 1, "bbox": [0.1, 0.1, 0.3, 0.2], "crop_url": None}]

    monkeypatch.setattr(adapters, "classify", classify)
    monkeypatch.setattr(adapters, "write_vectors", vectors)
    monkeypatch.setattr(adapters, "detect_signatures", signatures)
    row = run_document("c1", "d1", options=make_options(skip=()))
    assert seen["classify"][1:] == ("s.pdf", 2) and seen["classify"][0].count("\f") == 1
    assert seen["vectors"] == ("c1", "d1", 2, "kupni_smlouva")
    assert row["processing_status"] == "completed" and row["label"] == "kupni_smlouva"
    assert row["description"] == "Kupní smlouva" and row["confidence"] == Decimal("0.8731")
    assert row["signatures_s3_key"] == "cases/c1/analysis/d1/signatures.json"


def test_missing_sibling_modules_degrade_to_partial_with_clear_error(ingest, make_options, aws_env, monkeypatch):
    monkeypatch.setattr(adapters, "_load", lambda module, attribute: (_ for _ in ()).throw(
        adapters.StepUnavailable(f"module '{module}' is not importable")))
    ingest("c1", "d1", text_pdf(LONG))
    row = run_document("c1", "d1", options=make_options(skip=()))
    assert row["processing_status"] == "partial" and "text_s3_key" in row  # classify and embed missing
    steps = json.loads(s3_text(aws_env, "cases/c1/analysis/d1/run.json"))["steps"]
    assert {s["status"] for s in steps.values()} == {"unavailable"} and "not importable" in steps["classify"]["error"]


def label_tools(monkeypatch):
    def parse(data):
        return {"label": data["label"], "label_status": "predicted", "description": data.get("description", ""),
                "confidence": data.get("confidence")}
    monkeypatch.setattr(adapters, "label_tools", lambda: ("SEKCE ŠTÍTKŮ", {"type": "object"}, parse))


def no_classify(monkeypatch):
    monkeypatch.setattr(adapters, "classify", lambda *a: pytest.fail("classify_document must not run"))


def test_one_page_scan_gets_label_in_the_transcription_call(ingest, make_options, monkeypatch, aws_env):
    label_tools(monkeypatch)
    no_classify(monkeypatch)
    ingest("c1", "d1", scan_pdf(1))
    options = make_options(skip=("embed", "signatures"))
    row = run_document("c1", "d1", options=options)
    assert options.vision.calls == 1  # transcript, label and description in one call
    request = options.vision.requests[0]
    assert request["pages"] == 1 and request["section"] == "SEKCE ŠTÍTKŮ" and request["context"] == ""
    assert (row["label"], row["description"], row["confidence"]) == ("objednavka", "Objednávka stroje", Decimal("0.9"))
    assert s3_text(aws_env, row["text_s3_key"]) == "PŘEPIS SKENU 1"  # the label part is not in the text
    report = json.loads(s3_text(aws_env, "cases/c1/analysis/d1/run.json"))
    assert report["steps"]["classify"] == {"status": "ok", "via": "vision_call"}
    run_document("c1", "d1", options=options)  # cached, label included
    assert options.vision.calls == 1


def test_multi_page_scan_is_classified_over_the_whole_text(ingest, make_options, monkeypatch):
    label_tools(monkeypatch)
    seen = []
    monkeypatch.setattr(adapters, "classify", lambda text, title, n: seen.append((text, n)) or
                        {"label": "predavaci_protokol", "label_status": "predicted", "description": "Celek", "confidence": 0.8})
    ingest("c1", "d1", scan_pdf(2))
    options = make_options(skip=("embed", "signatures"))
    row = run_document("c1", "d1", options=options)
    assert options.vision.requests == [None, None] and seen == [("PŘEPIS SKENU 1\fPŘEPIS SKENU 2", 2)]
    assert row["description"] == "Celek"


def test_mixed_document_is_classified_once_after_assembly(ingest, make_options, monkeypatch):
    label_tools(monkeypatch)
    seen = []
    monkeypatch.setattr(adapters, "classify", lambda text, title, n: seen.append(text) or
                        {"label": "smlouva", "label_status": "predicted", "description": "Souhrn", "confidence": 0.7})
    ingest("c1", "d1", mixed_pdf())
    options = make_options(skip=("embed", "signatures"))
    row = run_document("c1", "d1", options=options)
    assert options.vision.requests == [None] and len(seen) == 1 and "PŘEPIS SKENU 1" in seen[0]
    assert row["description"] == "Souhrn"


def test_broken_label_reply_keeps_text_and_falls_back_to_classify(ingest, make_options, monkeypatch, aws_env):
    label_tools(monkeypatch)
    monkeypatch.setattr(adapters, "classify", lambda *a: {"label": "jine", "label_status": "predicted",
                                                           "description": "Záloha", "confidence": 0.4})
    ingest("c1", "d1", scan_pdf())
    row = run_document("c1", "d1", options=make_options(vision=FakeVision(label_reply="not json"), skip=("embed", "signatures")))
    assert row["description"] == "Záloha" and s3_text(aws_env, row["text_s3_key"]) == "PŘEPIS SKENU 1"


def test_scan_without_label_tools_uses_classify_document(ingest, make_options, monkeypatch):
    monkeypatch.setattr(adapters, "label_tools", lambda: (_ for _ in ()).throw(adapters.StepUnavailable("not yet")))
    monkeypatch.setattr(adapters, "classify", lambda *a: {"label": "jine", "label_status": "predicted",
                                                           "description": "Po přepisu", "confidence": 0.5})
    ingest("c1", "d1", scan_pdf())
    options = make_options(skip=("embed", "signatures"))
    row = run_document("c1", "d1", options=options)
    assert options.vision.requests == [None] and row["description"] == "Po přepisu"


def test_signature_failure_or_absence_never_changes_status(ingest, make_options, monkeypatch, aws_env):
    def boom(*args):
        raise RuntimeError("textract down")
    monkeypatch.setattr(adapters, "detect_signatures", boom)
    ingest("c1", "d1", text_pdf(LONG))
    row = run_document("c1", "d1", options=make_options(skip=("classify", "embed")))
    assert row["processing_status"] == "completed" and "signatures_s3_key" not in row
    assert json.loads(s3_text(aws_env, "cases/c1/analysis/d1/run.json"))["steps"]["signatures"]["status"] == "failed"


def test_empty_signature_finding_is_written(ingest, make_options, monkeypatch, aws_env):
    monkeypatch.setattr(adapters, "detect_signatures", lambda *a: [])
    ingest("c1", "d1", text_pdf(LONG))
    row = run_document("c1", "d1", options=make_options(skip=("classify", "embed")))
    assert json.loads(s3_text(aws_env, row["signatures_s3_key"])) == {"case_id": "c1", "document_id": "d1", "signatures": []}


def test_failing_step_does_not_lose_the_text(ingest, make_options, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("model down")
    monkeypatch.setattr(adapters, "classify", boom)
    ingest("c1", "d1", text_pdf(LONG))
    row = run_document("c1", "d1", options=make_options(skip=("embed", "signatures")))
    assert row["processing_status"] == "partial" and "label" not in row and row["text_s3_key"]


def test_skipped_steps_do_not_degrade_status(ingest, make_options):
    ingest("c1", "d1", text_pdf(LONG))
    assert run_document("c1", "d1", options=make_options(skip=("classify", "embed", "signatures")))["processing_status"] == "completed"


def test_verified_label_survives_rerun(ingest, make_options, monkeypatch):
    import boto3
    ingest("c1", "d1", text_pdf(LONG))
    boto3.resource("dynamodb", region_name="eu-central-1").Table("wonderfulkb-uw-document-analysis").put_item(Item={
        "case_id": "c1", "document_id": "d1", "label": "smlouva", "label_status": "verified", "description": "Ověřeno",
        "confidence": Decimal("1"), "processing_status": "completed", "page_count": 1, "title": "x"})
    monkeypatch.setattr(adapters, "classify", lambda *a: pytest.fail("classify must not run for a verified label"))
    row = run_document("c1", "d1", options=make_options(skip=("embed", "signatures")))
    assert (row["label"], row["label_status"], row["description"]) == ("smlouva", "verified", "Ověřeno")


def test_unknown_document_raises_and_writes_no_row(make_options):
    with pytest.raises(DocumentNotFound):
        run_document("c1", "nope", options=make_options())
    assert analysis_row("c1", "nope") is None


def test_invalid_pdf_ends_failed(ingest, make_options, aws_env):
    ingest("c1", "d1", b"not a pdf at all")
    row = run_document("c1", "d1", options=make_options())
    assert row["processing_status"] == "failed" and row["page_count"] == 0
    assert json.loads(s3_text(aws_env, "cases/c1/analysis/d1/run.json"))["error"] == "NOT_A_PDF"


def test_missing_original_ends_failed(ingest, make_options, aws_env):
    ingest("c1", "d1", text_pdf(LONG))
    aws_env.delete_object(Bucket=BUCKET, Key="cases/c1/original/d1.pdf")
    assert run_document("c1", "d1", options=make_options())["processing_status"] == "failed"


def test_direct_s3_mode_with_own_ids(aws_env, make_options):
    aws_env.put_object(Bucket=BUCKET, Key="cases/unhappy_scenario/01 Form VOP.pdf", Body=text_pdf(LONG))
    row = run_document("sample-1", "doc-vop", source=Source("cases/unhappy_scenario/01 Form VOP.pdf"), options=make_options())
    assert row["processing_status"] == "completed" and row["title"] == "01 Form VOP.pdf"
    assert row["text_s3_key"] == "cases/sample-1/analysis/doc-vop/text.txt"
    assert analysis_row("sample-1", "doc-vop") == row


def test_direct_s3_mode_derives_ingest_document_id(aws_env, make_options):
    import hashlib
    import uuid
    data = text_pdf(LONG)
    aws_env.put_object(Bucket=BUCKET, Key="cases/solom-rec/original/a.pdf", Body=data)
    row = run_document("sample-2", source=Source("cases/solom-rec/original/a.pdf"), options=make_options())
    expected = uuid.uuid5(uuid.UUID("5d3f0a52-7c1e-4a8b-9b36-6f1c2e0d7a11"), f"sample-2:{hashlib.sha256(data).hexdigest()}")
    assert row["document_id"] == str(expected)


def test_run_case_processes_all_documents_and_survives_a_broken_one(ingest, make_options):
    ingest("c1", "d1", text_pdf(LONG), "a.pdf")
    ingest("c1", "d2", scan_pdf(), "b.pdf")
    ingest("c1", "d3", b"broken", "c.pdf")
    ingest("other", "x", text_pdf(LONG), "z.pdf")
    rows = run_case("c1", make_options())
    assert [r["processing_status"] for r in rows] == ["completed", "completed", "failed"]
    assert analysis_row("other", "x") is None


def test_queued_rows_are_visible_before_processing(ingest, make_options):
    ingest("c1", "d1", text_pdf(LONG))
    ingest("c1", "d2", text_pdf(LONG))
    seen = []

    class Spy(FakeVision):
        def transcribe(self, png, label=None):
            seen.append(analysis_row("c1", "d2")["processing_status"])
            return super().transcribe(png, label)

    ingest("c1", "d0", scan_pdf(), "0.pdf")  # sorts first by filename, triggers vision
    run_case("c1", make_options(vision=Spy()))
    assert seen == ["queued"]


def test_run_prefix_takes_only_direct_pdfs_and_derives_ingest_ids(aws_env, make_options):
    import hashlib
    import uuid
    from pipeline import run_prefix
    data = text_pdf(LONG)
    aws_env.put_object(Bucket=BUCKET, Key="cases/unhappy/a.pdf", Body=data)
    aws_env.put_object(Bucket=BUCKET, Key="cases/unhappy/notes.txt", Body=b"x")
    aws_env.put_object(Bucket=BUCKET, Key="cases/unhappy/analysis/old/b.pdf", Body=data)  # analysis output, not an input
    rows = run_prefix("unhappy", "cases/unhappy", make_options())
    assert [r["title"] for r in rows] == ["a.pdf"]
    namespace = uuid.UUID("5d3f0a52-7c1e-4a8b-9b36-6f1c2e0d7a11")
    assert rows[0]["document_id"] == str(uuid.uuid5(namespace, f"unhappy:{hashlib.sha256(data).hexdigest()}"))


def test_resume_skips_completed_documents(ingest, make_options):
    ingest("c1", "d1", text_pdf(LONG))
    ingest("c1", "d2", text_pdf(LONG))
    first = make_options()
    run_document("c1", "d1", options=first)
    options = make_options(resume=True)
    rows = run_case("c1", options)
    assert [r["processing_status"] for r in rows] == ["completed", "completed"]
    assert rows[0]["updated_at"] == analysis_row("c1", "d1")["updated_at"]
    again = run_document("c1", "d1", options=options)
    assert again["updated_at"] == rows[0]["updated_at"]


def test_skipped_signatures_keep_an_existing_signatures_json(ingest, make_options, aws_env):
    ingest("c1", "d1", text_pdf(LONG))
    aws_env.put_object(Bucket=BUCKET, Key="cases/c1/analysis/d1/signatures.json", Body=b'{"signatures": []}')
    row = run_document("c1", "d1", options=make_options())
    assert row["signatures_s3_key"] == "cases/c1/analysis/d1/signatures.json"
    assert s3_text(aws_env, row["signatures_s3_key"]) == '{"signatures": []}'
