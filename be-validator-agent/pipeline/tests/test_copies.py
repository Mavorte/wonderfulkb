import json
from types import SimpleNamespace

import pytest

from pipeline import adapters, run_case, run_document
from pipeline.copies import copy_case

from .conftest import BUCKET, analysis_row, text_pdf

LONG = ["Kupni smlouva c. 2026/001 mezi prodavajicim a kupujicim", "Cena plneni cini 1 250 000 Kc bez DPH"]


def iou(a, b):
    ix, iy = max(0.0, min(a[2], b[2]) - max(a[0], b[0])), max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


class Sig:
    def __init__(self, entry, document_id):
        self.page, self.bbox, self.phash, self.mask = entry["page"], entry["bbox"], entry.get("phash"), entry.get("phash")
        self.signature_id, self.document_id = entry["signature_id"], document_id
        self.copy_suspicion = {"level": "none", "matches": []}


@pytest.fixture
def fake_tools(monkeypatch):
    """Stand-ins for the signature module: a 'mask' is the phash string, equal strings are copies."""
    def process_pdf(data, detector, case_id, document_id, store):
        assert store is None  # the copy check never writes crops
        return [Sig(entry, document_id) for entry in detector]

    def mark_copies(documents):
        for doc_id, sigs in documents.items():
            for sig in sigs:
                sig.copy_suspicion = {"level": "suspected", "matches": [
                    {"signature_id": o.signature_id, "document_id": other, "score": 1.0}
                    for other, others in documents.items() if other != doc_id for o in others
                    if o.mask and o.mask == sig.mask]} if any(
                    o.mask == sig.mask for other, others in documents.items() if other != doc_id for o in others) else \
                    {"level": "none", "matches": []}

    monkeypatch.setattr(adapters, "signature_tools", lambda: (process_pdf, lambda entries: list(entries), mark_copies, iou))


def signature(sid, phash, **extra):
    return {"signature_id": sid, "page": 1, "bbox": [0.1, 0.1, 0.4, 0.2], "detector": "textract", "role": "borrower",
            "phash": phash, "copy_suspicion": {"level": "none", "matches": []}, **extra}


def put_case(ingest, aws_env, shapes, with_json=True):
    for document_id, sigs in shapes.items():
        ingest("c1", document_id, text_pdf(LONG), f"{document_id}.pdf")
        if with_json and sigs is not None:
            body = {"case_id": "c1", "document_id": document_id, "signatures": sigs}
            aws_env.put_object(Bucket=BUCKET, Key=f"cases/c1/analysis/{document_id}/signatures.json",
                               Body=json.dumps(body).encode())


def levels(aws_env, document_id):
    body = json.loads(aws_env.get_object(Bucket=BUCKET, Key=f"cases/c1/analysis/{document_id}/signatures.json")["Body"].read())
    return [s["copy_suspicion"] for s in body["signatures"]]


def test_matches_across_documents_and_none_only_when_whole_case_compared(ingest, aws_env, fake_tools, make_options):
    put_case(ingest, aws_env, {"a": [signature("sig_01", "AAAA")], "b": [signature("sig_01", "AAAA")],
                               "c": [signature("sig_01", "CCCC")]})
    result = copy_case("c1", make_options())
    assert result["complete"] and result["compared"] == 3 and result["documents_changed"] == 2
    assert levels(aws_env, "a")[0]["level"] == "suspected" and levels(aws_env, "a")[0]["matches"][0]["document_id"] == "b"
    assert levels(aws_env, "c")[0] == {"level": "none", "matches": []}
    assert result["transitions"] == {"none->suspected": 2}


def test_incomplete_case_never_says_none(ingest, aws_env, fake_tools, make_options):
    put_case(ingest, aws_env, {"a": [signature("sig_01", "AAAA")], "b": [signature("sig_01", "AAAA")],
                               "c": [signature("sig_01", "CCCC")], "d": None})  # d: no signatures.json yet
    result = copy_case("c1", make_options())
    assert not result["complete"]
    assert levels(aws_env, "a")[0]["level"] == "suspected"      # a found copy is a finding whatever the coverage
    assert levels(aws_env, "c")[0] == {"level": "not_checked", "matches": []}
    assert result["transitions"] == {"none->suspected": 2, "none->not_checked": 1}


def test_findings_and_other_fields_stay_untouched(ingest, aws_env, fake_tools, make_options):
    own = signature("sig_01", "AAAA", detector="label_anchored", crop_s3_key="x.png.enc", crop_encrypted=True)
    put_case(ingest, aws_env, {"a": [own]})
    copy_case("c1", make_options())
    body = json.loads(aws_env.get_object(Bucket=BUCKET, Key="cases/c1/analysis/a/signatures.json")["Body"].read())
    assert body["signatures"][0] == {**own, "copy_suspicion": {"level": "none", "matches": []}}  # single document: compared with all others


def test_idempotent_and_row_gets_the_key(ingest, aws_env, fake_tools, make_options):
    put_case(ingest, aws_env, {"a": [signature("sig_01", "AAAA")], "b": [signature("sig_01", "AAAA")]})
    options = make_options()
    run_document("c1", "a", options=options)  # creates the analysis row (signatures.json already exists: kept)
    first = copy_case("c1", options)
    second = copy_case("c1", options)
    assert first["documents_changed"] == 2 and second["documents_changed"] == 0 and second["transitions"] == {}
    assert analysis_row("c1", "a")["signatures_s3_key"] == "cases/c1/analysis/a/signatures.json"


def test_missing_pdf_means_not_compared(ingest, aws_env, fake_tools, make_options):
    put_case(ingest, aws_env, {"a": [signature("sig_01", "AAAA")], "b": [signature("sig_01", "BBBB")]})
    aws_env.delete_object(Bucket=BUCKET, Key="cases/c1/original/b.pdf")
    result = copy_case("c1", make_options())
    assert result["not_compared"] == ["b"] and not result["complete"]
    assert levels(aws_env, "a")[0]["level"] == "not_checked"


def test_blank_signature_without_ink_is_not_checked(ingest, aws_env, fake_tools, make_options):
    put_case(ingest, aws_env, {"a": [signature("sig_01", None)]})
    copy_case("c1", make_options())
    assert levels(aws_env, "a")[0]["level"] == "not_checked"


def test_document_run_writes_not_checked_never_none(ingest, aws_env, make_options, monkeypatch):
    monkeypatch.setattr(adapters, "detect_signatures", lambda *a: [signature("sig_01", "AAAA", crop_url="u")])
    ingest("c1", "a", text_pdf(LONG))
    options = make_options(skip=("classify", "embed", "copy"))
    row = run_document("c1", "a", options=options)
    body = json.loads(aws_env.get_object(Bucket=BUCKET, Key=row["signatures_s3_key"])["Body"].read())
    assert body["signatures"][0]["copy_suspicion"] == {"level": "not_checked", "matches": []}
    assert "crop_url" not in body["signatures"][0]


def test_existing_signatures_json_is_not_replaced_by_a_run(ingest, aws_env, make_options, monkeypatch):
    monkeypatch.setattr(adapters, "detect_signatures", lambda *a: pytest.fail("must not detect again"))
    ingest("c1", "a", text_pdf(LONG))
    original = json.dumps({"case_id": "c1", "document_id": "a", "signatures": [signature("sig_01", "AAAA", detector="page_images")]})
    aws_env.put_object(Bucket=BUCKET, Key="cases/c1/analysis/a/signatures.json", Body=original.encode())
    row = run_document("c1", "a", options=make_options(skip=("classify", "embed", "copy")))
    assert row["signatures_s3_key"] == "cases/c1/analysis/a/signatures.json" and row["processing_status"] == "completed"
    assert aws_env.get_object(Bucket=BUCKET, Key=row["signatures_s3_key"])["Body"].read().decode() == original


def test_case_runs_the_copy_check_once_after_the_last_document(ingest, aws_env, make_options, monkeypatch):
    calls = []
    monkeypatch.setattr(adapters, "detect_signatures", lambda *a: [signature("sig_01", "AAAA")])
    import pipeline.copies as copies
    monkeypatch.setattr(copies, "copy_case", lambda case_id, options: calls.append(case_id) or {})
    ingest("c1", "a", text_pdf(LONG))
    ingest("c1", "b", text_pdf(LONG))
    rows = run_case("c1", make_options(skip=("classify", "embed")))
    assert calls == ["c1"] and [r["processing_status"] for r in rows] == ["completed", "completed"]


def test_copy_check_failure_does_not_change_the_status(ingest, aws_env, make_options, monkeypatch):
    monkeypatch.setattr(adapters, "detect_signatures", lambda *a: [])
    import pipeline.copies as copies
    monkeypatch.setattr(copies, "copy_case", lambda case_id, options: (_ for _ in ()).throw(RuntimeError("boom")))
    ingest("c1", "a", text_pdf(LONG))
    assert run_document("c1", "a", options=make_options(skip=("classify", "embed")))["processing_status"] == "completed"
