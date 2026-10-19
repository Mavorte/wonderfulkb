import io
import os
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # infra/validator-agent

from pipeline import Options, Settings  # noqa: E402

BUCKET, REGION = "wonderfulkb-raw-document-storage", "eu-central-1"


def text_pdf(*pages):
    """Minimal PDF, one Helvetica text page per argument (a list of lines)."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", None]
    kids = []
    for lines in pages:
        content = "BT /F1 12 Tf 14 TL 50 780 Td " + " ".join(f"({line}) Tj T*" for line in lines) + " ET"
        objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents %d 0 R "
                       b"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>" % (len(objects) + 2))
        kids.append(len(objects))
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content.encode("latin-1")))
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join(f"{k} 0 R" for k in kids).encode(), len(kids))
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def scan_pdf(pages=1):
    """A raster-only PDF: every page is a full-page image with no text layer."""
    images = []
    for n in range(pages):
        image = Image.new("RGB", (800, 1100), "white")
        ImageDraw.Draw(image).text((60, 60 + n), "scanned text", fill="black")
        images.append(image)
    out = io.BytesIO()
    images[0].save(out, format="PDF", save_all=True, append_images=images[1:], resolution=100)
    return out.getvalue()


def mixed_pdf():
    """Page 1 text layer, page 2 scan."""
    import pypdf
    writer = pypdf.PdfWriter()
    writer.append(pypdf.PdfReader(io.BytesIO(text_pdf(["Smlouva o zajisteni prevodu vlastnickeho prava c. 123", "Strana prvni"]))))
    writer.append(pypdf.PdfReader(io.BytesIO(scan_pdf())))
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


class FakeVision:
    def __init__(self, text="PŘEPIS SKENU", fail_pages=(), label_reply=None):
        self.text, self.calls, self.fail, self.label_reply = text, 0, set(fail_pages), label_reply
        self.requests = []

    def transcribe(self, png, label=None):
        from pipeline.vision import LABEL_DELIMITER, VisionError
        assert png.startswith(b"\x89PNG")
        self.calls += 1
        self.requests.append(label)
        if self.calls in self.fail:
            raise VisionError("BEDROCK_HTTP_500")
        reply = f"{self.text} {self.calls}"
        if label:
            reply += f"\n{LABEL_DELIMITER}\n" + (self.label_reply if self.label_reply is not None else
                '{"label": "objednavka", "description": "Objednávka stroje", "confidence": 0.9}')
        return reply


@pytest.fixture
def aws_env(monkeypatch):
    for name in ("AWS_PROFILE", "PIPELINE_SKIP"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    with mock_aws():
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION})
        ddb = boto3.client("dynamodb", region_name=REGION)
        for name in ("wonderfulkb-uw-documents", "wonderfulkb-uw-document-analysis"):
            ddb.create_table(TableName=name, BillingMode="PAY_PER_REQUEST",
                             AttributeDefinitions=[{"AttributeName": "case_id", "AttributeType": "S"},
                                                   {"AttributeName": "document_id", "AttributeType": "S"}],
                             KeySchema=[{"AttributeName": "case_id", "KeyType": "HASH"},
                                        {"AttributeName": "document_id", "KeyType": "RANGE"}])
        yield s3


@pytest.fixture
def make_options(aws_env):
    def make(vision=None, skip=("classify", "embed", "signatures"), redact=False, **kwargs):
        # redact=False keeps the older tests on the plain path (they test text, labels, status); test_redaction.py
        # runs with redact=True, which is the default of Settings
        return Options(settings=Settings(skip=frozenset(skip), redact=redact), vision=vision or FakeVision(), **kwargs)
    return make


@pytest.fixture
def ingest(aws_env):
    """Put a PDF where the ingest service would: S3 original plus a row in wonderfulkb-uw-documents."""
    ddb = boto3.resource("dynamodb", region_name=REGION).Table("wonderfulkb-uw-documents")

    def put(case_id, document_id, data, filename="doc.pdf"):
        key = f"cases/{case_id}/original/{document_id}.pdf"
        aws_env.put_object(Bucket=BUCKET, Key=key, Body=data)
        ddb.put_item(Item={"case_id": case_id, "document_id": document_id, "filename": filename, "s3_key": key,
                           "content_type": "application/pdf", "size_bytes": len(data)})
    return put


def analysis_row(case_id, document_id):
    table = boto3.resource("dynamodb", region_name=REGION).Table("wonderfulkb-uw-document-analysis")
    return table.get_item(Key={"case_id": case_id, "document_id": document_id}).get("Item")
