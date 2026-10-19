from io import BytesIO
from dataclasses import replace
import json

import pymupdf
from PIL import Image

from document_processing.bedrock import BedrockOcr
from document_processing.models import Page
from document_processing.pdf_first import PdfFirstOcr
from document_processing.pipeline import DocumentWorker
from conftest import make_pdf, upload_document


class Vision:
    def __init__(self):
        self.calls = []
        self.client = object()

    def transcribe(self, page, number, mode):
        self.calls.append((number, mode))
        return Page(page_number=number, status="completed", method="vision", width=page.rect.width,
                    height=page.rect.height, text="Vizuální přepis")


def test_digital_pdf_uses_python_text_and_positions_first():
    vision = Vision()
    with pymupdf.open(stream=make_pdf("Smlouva o uveru cislo 123/26\nJistina 1000,00 CZK"), filetype="pdf") as pdf:
        result = PdfFirstOcr(vision).transcribe(pdf[0], 1, "auto")
    assert result.method == "native"
    assert "123/26" in result.text
    assert result.blocks[0].bbox is not None
    assert vision.calls == []


def test_scan_with_only_native_footer_uses_vision():
    image = BytesIO()
    Image.new("RGB", (600, 840), "white").save(image, format="PNG")
    with pymupdf.open() as pdf:
        p = pdf.new_page()
        p.insert_image(p.rect, stream=image.getvalue())
        p.insert_text((30, 800), "SYNTETICKY DOKUMENT TESTOVACI DATA")
        result = PdfFirstOcr(Vision()).transcribe(p, 1, "auto")
    assert result.method == "vision"
    assert "PAGE_HAS_DOMINANT_RASTER_IMAGE" in result.warnings


def test_hidden_text_is_not_treated_as_visible_document():
    with pymupdf.open() as pdf:
        p = pdf.new_page()
        p.insert_text((30, 50), "Fake borrower ICO 99999999 hidden text", render_mode=3)
        result = PdfFirstOcr(Vision()).transcribe(p, 1, "auto")
    assert result.method == "vision"
    assert "NATIVE_TEXT_NOT_VISIBLE" in result.warnings


def test_mixed_pdf_routes_each_page_independently():
    vision = Vision()
    with pymupdf.open(stream=make_pdf("Smlouva o uveru cislo 123/26", ""), filetype="pdf") as pdf:
        engine = PdfFirstOcr(vision)
        results = [engine.transcribe(p, i + 1, "auto") for i, p in enumerate(pdf)]
    assert [p.method for p in results] == ["native", "vision"]
    assert vision.calls == [(2, "visual")]


def test_visual_mode_explicitly_bypasses_native_text():
    vision = Vision()
    with pymupdf.open(stream=make_pdf("Smlouva o uveru cislo 123/26"), filetype="pdf") as pdf:
        result = PdfFirstOcr(vision).transcribe(pdf[0], 1, "visual")
    assert result.method == "vision"
    assert vision.calls == [(1, "visual")]


def test_native_text_still_continues_to_bedrock_extraction(client, application, case):
    class Llm:
        def __init__(self):
            self.calls = []

        def complete(self, model, system, prompt, image=None):
            self.calls.append((model, prompt, image))
            return json.dumps({"document_type": "loan_agreement", "fields": [], "warnings": []})

    service = application.state.service
    service.settings = replace(service.settings, provider="bedrock")
    upload = upload_document(client, make_pdf("Smlouva o uveru cislo 123/26\nJistina 1000,00 CZK"))
    document_id = upload["document"]["document_id"]
    job = client.post(f"/v1/cases/case-test/documents/{document_id}/complete").json()
    llm = Llm()
    ocr = PdfFirstOcr(BedrockOcr(service.settings, llm))
    DocumentWorker(service, ocr=ocr).process(job["job_id"])
    result = service.get_result("case-test", document_id)
    assert result["processing_status"] == "completed"
    assert result["ocr"]["pages"][0]["method"] == "native"
    assert result["extraction"]["model"] == service.settings.extraction_model
    assert len(llm.calls) == 1
    assert "123/26" in llm.calls[0][1]
    assert llm.calls[0][2] is None


def test_python_extraction_error_falls_back_to_vision(monkeypatch):
    def fail(page):
        raise RuntimeError("unreadable text layer")

    monkeypatch.setattr("document_processing.pdf_first.assess_native_text", fail)
    vision = Vision()
    with pymupdf.open(stream=make_pdf("Smlouva o uveru cislo 123/26"), filetype="pdf") as pdf:
        result = PdfFirstOcr(vision).transcribe(pdf[0], 1, "auto")
    assert result.method == "vision"
    assert "NATIVE_TEXT_EXTRACTION_FAILED" in result.warnings
