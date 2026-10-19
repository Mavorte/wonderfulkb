import pytest
from botocore.exceptions import ClientError
from conftest import make_pdf, upload_document
from test_api_pipeline import complete

from document_processing.models import SignatureSection
from document_processing.pipeline import DocumentWorker
from document_processing.signatures import (
    TextractSignatureDetector,
    build_signatures,
    role_for_line,
)


def geometry(left, top, width, height):
    return {"BoundingBox": {"Left": left, "Top": top, "Width": width, "Height": height}}


def line(text, left, top, page=2, width=0.2, height=0.015):
    return {"BlockType": "LINE", "Text": text, "Page": page, "Geometry": geometry(left, top, width, height)}


def signature(left, top, page=2, score=31.4):
    return {"BlockType": "SIGNATURE", "Page": page, "Confidence": score, "Geometry": geometry(left, top, 0.12, 0.04)}


class FakeTextract:
    """Records calls and serves the same blocks in parts of two, as Textract does for large results."""

    def __init__(self, blocks, status="SUCCEEDED", error=None):
        self.blocks, self.status, self.error, self.calls = blocks, status, error, []

    def start_document_analysis(self, **kwargs):
        self.calls.append(("start", kwargs))
        if self.error:
            raise self.error
        return {"JobId": "job-1"}

    def get_document_analysis(self, JobId, NextToken=None):
        self.calls.append(("get", NextToken))
        if self.status != "SUCCEEDED":
            return {"JobStatus": self.status}
        half = (len(self.blocks) + 1) // 2
        if NextToken is None:
            return {"JobStatus": "SUCCEEDED", "Blocks": self.blocks[:half], "NextToken": "more"}
        return {"JobStatus": "SUCCEEDED", "Blocks": self.blocks[half:]}

    def analyze_document(self, **kwargs):
        self.calls.append(("analyze", kwargs))
        return {"Blocks": self.blocks}


def detector(fake, **kwargs):
    return TextractSignatureDetector("bucket", client=fake, sleep=lambda _: None, **kwargs)


BLOCKS = [
    line("Ručitel:", 0.40, 0.33),
    line("Podpis", 0.40, 0.42),
    signature(0.436, 0.372),
    line("Datum", 0.63, 0.74),
    signature(0.627, 0.695, score=12.0),
]


def test_role_comes_from_the_nearest_unambiguous_label():
    items = build_signatures(BLOCKS)
    first, second = items
    assert (first.role, first.role_source, first.role_evidence) == ("guarantor", "nearest_text", "Ručitel:")
    assert first.detection_score == 31.4
    assert first.page == 2 and first.detector == "textract"
    # No party label near the second box: unknown, with no invented evidence.
    assert (second.role, second.role_source, second.role_evidence) == ("unknown", None, None)
    assert second.detection_score == 12.0
    assert "Datum" in second.nearby_text


def test_bbox_is_relative_corners_inside_the_page():
    box = build_signatures([signature(0.95, 0.98)])[0].bbox
    assert box[0] < box[2] <= 1 and box[1] < box[3] <= 1
    assert all(0 <= value <= 1 for value in box)
    assert build_signatures([signature(0.436, 0.372)])[0].bbox == [0.436, 0.372, 0.556, 0.412]


@pytest.mark.parametrize("text,role", [
    ("Za dlužníka", "borrower"), ("Příjemce financování:", "borrower"), ("DLUŽNÍK:", "borrower"), ("Za věřitele", "provider"),
    ("Prodávající", "supplier"), ("kupující", "buyer"), ("Pojistitel", "insurer"),
    ("Podpis", None), ("Dlužník a ručitel", None),
])
def test_role_labels_in_czech(text, role):
    assert role_for_line(text) == role


def test_two_competing_party_labels_give_unknown_instead_of_a_guess():
    # Provider and recipient columns side by side, signature between them.
    table = [line("Poskytovatel financování:", 0.12, 0.70, page=3), line("Příjemce financování:", 0.49, 0.70, page=3),
             signature(0.36, 0.787, page=3)]
    item = build_signatures(table)[0]
    assert (item.role, item.role_source, item.role_evidence) == ("unknown", None, None)
    assert "Poskytovatel financování:" in item.nearby_text


def test_labels_beyond_the_search_window_are_ignored():
    far = [line("Ručitel:", 0.40, 0.10), signature(0.436, 0.372)]
    assert build_signatures(far)[0].role == "unknown"
    other_page = [line("Ručitel:", 0.40, 0.33, page=1), signature(0.436, 0.372)]
    assert build_signatures(other_page)[0].role == "unknown"


def test_detector_pages_through_next_token_and_sends_s3_version():
    fake = FakeTextract(BLOCKS)
    section = detector(fake).detect("originals/c/d", "application/pdf", "v123")
    assert section.status == "completed" and len(section.signatures) == 2
    start = fake.calls[0][1]
    assert start["FeatureTypes"] == ["SIGNATURES"]
    assert start["DocumentLocation"]["S3Object"] == {"Bucket": "bucket", "Name": "originals/c/d", "Version": "v123"}
    assert ("get", "more") in fake.calls


def test_no_signature_is_a_valid_empty_result_not_an_error():
    section = detector(FakeTextract([line("Smlouva", 0.1, 0.1)])).detect("k", "application/pdf")
    assert section.status == "completed" and section.signatures == [] and section.error is None


def test_image_uses_single_page_analysis():
    fake = FakeTextract([signature(0.1, 0.1, page=1)])
    section = detector(fake).detect("k", "image/png")
    assert [name for name, _ in fake.calls] == ["analyze"]
    assert section.signatures[0].page == 1


def test_failures_are_reported_by_code_only():
    denied = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "arn:aws:iam::123456789012:role/x"}}, "StartDocumentAnalysis")
    section = detector(FakeTextract([], error=denied)).detect("k", "application/pdf")
    assert (section.status, section.error) == ("failed", "TEXTRACT_ACCESSDENIEDEXCEPTION")
    assert "123456789012" not in section.model_dump_json()
    assert detector(FakeTextract([], status="FAILED")).detect("k", "application/pdf").error == "TEXTRACT_JOB_FAILED"


def test_job_that_never_finishes_times_out_as_retryable_code():
    section = detector(FakeTextract([], status="IN_PROGRESS"), timeout_seconds=0).detect("k", "application/pdf")
    assert section.error == "TEXTRACT_TIMEOUT"


def test_only_frankfurt_is_accepted():
    with pytest.raises(ValueError):
        TextractSignatureDetector("bucket", client=object(), region="eu-west-1")


def process(client, application, detector_instance):
    upload = upload_document(client, make_pdf("SMLOUVA O UVERU C. 123/26\nJistina 1 000,00 CZK"))
    job = complete(client, upload)
    DocumentWorker(application.state.service, signature_detector=detector_instance).process(job["job_id"])
    document_id = upload["document"]["document_id"]
    return client.get(f"/v1/cases/case-test/documents/{document_id}/result").json()


class StaticDetector:
    def __init__(self, section):
        self.section, self.calls = section, []

    def detect(self, key, content_type, version=None):
        self.calls.append((key, content_type, version))
        return self.section


def test_result_carries_signatures_next_to_ocr(client, application, case):
    section = SignatureSection(status="completed", signatures=build_signatures(BLOCKS))
    fake = StaticDetector(section)
    result = process(client, application, fake)
    assert result["processing_status"] == "completed"
    assert [s["role"] for s in result["signatures"]["signatures"]] == ["guarantor", "unknown"]
    assert fake.calls[0][0].startswith("originals/case-test/") and fake.calls[0][1] == "application/pdf"


def test_signature_failure_does_not_degrade_ocr_status(client, application, case):
    result = process(client, application, StaticDetector(SignatureSection(status="failed", error="TEXTRACT_TIMEOUT")))
    assert result["processing_status"] == "completed" and result["errors"] == []
    assert result["signatures"] == {"status": "failed", "detector": "textract", "signatures": [], "error": "TEXTRACT_TIMEOUT"}


def test_result_without_detector_has_no_signature_section(client, application, case):
    assert process(client, application, None)["signatures"] is None
