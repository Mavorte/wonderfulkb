"""Fixtures: every AWS service is moto, nothing here can reach a real account."""
import json
import math
import os
import random
import sys
from pathlib import Path

import boto3
import pytest

os.environ.update(AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing", AWS_SESSION_TOKEN="testing",
                  AWS_DEFAULT_REGION="eu-central-1", AWS_REGION="eu-central-1")
os.environ["PIPELINE_REGIONS_LLM"] = "0"  # region labels from regexes, never Bedrock
for name in ("AWS_PROFILE", "PIPELINE_SKIP", "AWS_ENDPOINT_URL"):
    os.environ.pop(name, None)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # infra/validator-agent

from moto import mock_aws  # noqa: E402

from trigger import common  # noqa: E402

BUCKET, REGION = "wonderfulkb-raw-document-storage", "eu-central-1"
CASE = "TEST-1"


def table(ddb, name):
    ddb.create_table(TableName=name, BillingMode="PAY_PER_REQUEST",
                     AttributeDefinitions=[{"AttributeName": "case_id", "AttributeType": "S"},
                                           {"AttributeName": "document_id", "AttributeType": "S"}],
                     KeySchema=[{"AttributeName": "case_id", "KeyType": "HASH"},
                                {"AttributeName": "document_id", "KeyType": "RANGE"}])


@pytest.fixture
def aws():
    with mock_aws():
        ddb = boto3.client("dynamodb", region_name=REGION)
        table(ddb, "wonderfulkb-uw-documents")
        table(ddb, "wonderfulkb-uw-document-analysis")
        ddb.create_table(TableName="wonderfulkb-uw-cases", BillingMode="PAY_PER_REQUEST",
                         AttributeDefinitions=[{"AttributeName": "case_id", "AttributeType": "S"}],
                         KeySchema=[{"AttributeName": "case_id", "KeyType": "HASH"}])
        ddb.create_table(TableName="wonderfulkb-trigger-execution", BillingMode="PAY_PER_REQUEST",
                         AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"},
                                               {"AttributeName": "sk", "AttributeType": "S"}],
                         KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"},
                                    {"AttributeName": "sk", "KeyType": "RANGE"}])
        boto3.client("s3", region_name=REGION).create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION})
        sqs = boto3.client("sqs", region_name=REGION)
        dlq = sqs.create_queue(QueueName="wonderfulkb-trigger-documents-dlq")["QueueUrl"]
        queue = sqs.create_queue(QueueName="wonderfulkb-trigger-documents")["QueueUrl"]
        yield common.Context(queue_url=queue, dlq_url=dlq)


@pytest.fixture
def ctx(aws):
    return aws


def drain(ctx, url=None):
    """All messages currently on the queue (default: the main one) as parsed bodies, without hiding them."""
    sqs, url, out = ctx.sqs, url or ctx.queue_url, []
    while True:
        response = sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=10, VisibilityTimeout=0,
                                       MessageAttributeNames=["All"])
        if not response.get("Messages"):
            break
        for message in response["Messages"]:
            sqs.delete_message(QueueUrl=url, ReceiptHandle=message["ReceiptHandle"])
            out.append(message)
    return out


def bodies(messages):
    return [json.loads(m["Body"]) for m in messages]


def add_document(ctx, document_id, case_id=CASE, filename=None, pdf=None):
    item = {"case_id": case_id, "document_id": document_id, "filename": filename or f"{document_id}.pdf",
            "s3_key": f"cases/{case_id}/original/{document_id}.pdf", "size_bytes": 1, "sha256": "x"}
    ctx.documents.put_item(Item=item)
    if pdf is not None:
        ctx.s3.put_object(Bucket=BUCKET, Key=item["s3_key"], Body=pdf)
    return item


def stream_record(case_id, document_id, event="INSERT", filename="a.pdf", sequence="1"):
    image = {"case_id": {"S": case_id}, "document_id": {"S": document_id}, "filename": {"S": filename}}
    return {"eventName": event, "dynamodb": {"SequenceNumber": sequence, "Keys": {
        "case_id": {"S": case_id}, "document_id": {"S": document_id}}, "NewImage": image}}


def sqs_event(*bodies_, receive_count=1):
    return {"Records": [{"messageId": f"m{i}", "body": b if isinstance(b, str) else json.dumps(b),
                         "attributes": {"ApproximateReceiveCount": str(receive_count)}}
                        for i, b in enumerate(bodies_)]}


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


def signed_pdf(stroke_seed, title):
    """One page with a text line and a drawn 'signature' (a smooth random stroke). Returns (pdf bytes, relative bbox)."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((60, 90), title, fontsize=11)
    rect = pymupdf.Rect(70, 650, 230, 710)
    rnd, pts, x, y, a = random.Random(stroke_seed), [], 0.05, 0.5, 0.0
    for _ in range(60):
        a += rnd.uniform(-1.4, 1.4)
        x = min(0.95, max(0.05, x + 0.035 * math.cos(a) + 0.012))
        y = min(0.9, max(0.1, y + 0.09 * math.sin(a)))
        pts.append(pymupdf.Point(rect.x0 + x * rect.width, rect.y0 + y * rect.height))
    shape = page.new_shape()
    shape.draw_polyline(pts)
    shape.finish(color=(0, 0, 0.4), width=1.4, closePath=False)
    shape.commit()
    r = page.rect
    return doc.tobytes(), [(rect.x0 - 10) / r.width, (rect.y0 - 10) / r.height, (rect.x1 + 10) / r.width, (rect.y1 + 10) / r.height]
