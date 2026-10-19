"""Stream record -> enqueue -> queue -> worker -> the real pipeline.run_document and pipeline.copies, on moto.

Bedrock and Textract are not involved: the PDFs have a text layer and the classify/embed/signatures steps are
skipped, so this proves the wiring, the idempotence and the case step, not the quality of the analysis."""
import json

import pytest

from trigger import common, enqueue_handler, worker_handler

from .conftest import BUCKET, CASE, add_document, drain, signed_pdf, sqs_event, stream_record, text_pdf


class NoNetwork:
    def transcribe(self, png, label=None):
        raise AssertionError("the tests must not call a vision model")


LINE = "Smlouva o uveru, dluznik se zavazuje splacet dohodnute splatky ve lhute a vysi podle prilohy."


@pytest.fixture
def real(ctx, monkeypatch):
    from pipeline import Options
    monkeypatch.setenv("PIPELINE_SKIP", "classify,embed,signatures")
    # The pipeline masks signatures by default (Textract detection + KMS): off here, this file tests the wiring.
    # The deployed worker runs with PIPELINE_REDACT=1 (test_template checks it).
    monkeypatch.setenv("PIPELINE_REDACT", "0")
    monkeypatch.setattr(worker_handler, "_ctx", ctx)
    monkeypatch.setattr(worker_handler, "_options", Options(defer_copy_check=True, vision=NoNetwork()))
    monkeypatch.setattr(worker_handler, "run_document", None)
    monkeypatch.setattr(enqueue_handler, "_ctx", ctx)
    return ctx


def deliver(ctx):
    """Hand every queued message to the worker, as the event source mapping does. Returns the bodies delivered."""
    delivered = []
    for message in drain(ctx):
        delivered.append(json.loads(message["Body"]))
        result = worker_handler.handler({"Records": [{"messageId": message["MessageId"], "body": message["Body"],
                                                      "attributes": {"ApproximateReceiveCount": "1"}}]})
        assert result == {"batchItemFailures": []}
    return delivered


def test_upload_to_completed_row(real):
    ctx = real
    add_document(ctx, "d1", pdf=text_pdf(["Smlouva o uveru c. 1", LINE], [LINE, "Strana druha"]))
    enqueue_handler.handler({"Records": [stream_record(CASE, "d1", filename="Smlouva.pdf")]})
    assert ctx.get_row(CASE, "d1")["processing_status"] == "queued"
    assert [m["type"] for m in deliver(ctx)] == ["document"]
    row = ctx.get_row(CASE, "d1")
    assert row["processing_status"] == "completed" and int(row["page_count"]) == 2
    text = ctx.s3.get_object(Bucket=BUCKET, Key=row["text_s3_key"])["Body"].read().decode()
    assert "Smlouva o uveru" in text and "\f" in text
    # the only document of the case is done: the case step was queued and runs (nothing to compare, no error)
    assert [m["type"] for m in deliver(ctx)] == ["case"]


def test_duplicate_delivery_does_not_run_the_pipeline_again(real):
    ctx = real
    add_document(ctx, "d1", pdf=text_pdf([LINE]))
    common.enqueue_document(ctx, CASE, "d1")
    deliver(ctx)
    key = f"cases/{CASE}/analysis/d1/run.json"
    first = ctx.s3.get_object(Bucket=BUCKET, Key=key)
    stamp = ctx.get_row(CASE, "d1")["updated_at"]
    worker_handler.handler(sqs_event({"v": 1, "type": "document", "case_id": CASE, "document_id": "d1"}))
    second = ctx.s3.get_object(Bucket=BUCKET, Key=key)
    assert first["ETag"] == second["ETag"] and first["LastModified"] == second["LastModified"]
    assert ctx.get_row(CASE, "d1")["updated_at"] == stamp


def test_broken_pdf_ends_failed_without_retries(real):
    ctx = real
    add_document(ctx, "bad", pdf=b"%PDF-1.4 this is not a pdf")
    common.enqueue_document(ctx, CASE, "bad")
    assert [m["type"] for m in deliver(ctx)] == ["document"]
    row = ctx.get_row(CASE, "bad")
    assert row["processing_status"] == "failed"
    assert drain(ctx, ctx.dlq_url) == []


def test_missing_original_ends_failed(real):
    ctx = real
    add_document(ctx, "gone")  # row in the documents table, no object in S3
    common.enqueue_document(ctx, CASE, "gone")
    deliver(ctx)
    assert ctx.get_row(CASE, "gone")["processing_status"] == "failed"


def test_the_case_step_finds_the_same_signature_in_two_documents(real, monkeypatch):
    """Case message -> pipeline.copies.copy_case over signatures.json files that say `not_checked`."""
    ctx = real
    pdf_a, box = signed_pdf(7, "Smlouva o uveru")
    pdf_b, _ = signed_pdf(7, "Dodatek c. 1")     # the same stroke: a pasted signature
    pdf_c, _ = signed_pdf(99, "Rucitelske prohlaseni")  # a different one
    for document_id, pdf in (("d1", pdf_a), ("d2", pdf_b), ("d3", pdf_c)):
        add_document(ctx, document_id, pdf=pdf)
        ctx.analysis.put_item(Item={"case_id": CASE, "document_id": document_id, "processing_status": "completed",
                                    "title": document_id, "updated_at": "2026-10-19T10:00:00Z"})
        found = {"signature_id": "sig_01", "page": 1, "bbox": box, "detector": "textract", "detection_score": 50.0,
                 "role": "borrower", "role_source": "nearest_text", "role_evidence": "Dluznik", "phash": None,
                 "copy_suspicion": {"level": "not_checked", "matches": []}}
        ctx.s3.put_object(Bucket=BUCKET, Key=f"cases/{CASE}/analysis/{document_id}/signatures.json",
                          Body=json.dumps({"case_id": CASE, "document_id": document_id, "signatures": [found]}).encode())
    worker_handler.handler(sqs_event({"v": 1, "type": "case", "case_id": CASE}))
    levels = {}
    for document_id in ("d1", "d2", "d3"):
        body = json.loads(ctx.s3.get_object(Bucket=BUCKET, Key=f"cases/{CASE}/analysis/{document_id}/signatures.json")["Body"].read())
        levels[document_id] = body["signatures"][0]["copy_suspicion"]
        assert body["signatures"][0]["role"] == "borrower"  # nothing else in the file changed
    assert levels["d1"]["level"] == "suspected" and levels["d2"]["level"] == "suspected"
    assert {m["document_id"] for m in levels["d1"]["matches"]} == {"d2"}
    assert levels["d3"]["level"] == "none"
    # idempotent: a second case message changes nothing
    before = ctx.s3.get_object(Bucket=BUCKET, Key=f"cases/{CASE}/analysis/d1/signatures.json")["Body"].read()
    worker_handler.handler(sqs_event({"v": 1, "type": "case", "case_id": CASE}))
    assert ctx.s3.get_object(Bucket=BUCKET, Key=f"cases/{CASE}/analysis/d1/signatures.json")["Body"].read() == before
