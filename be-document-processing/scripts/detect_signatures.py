"""Run Textract signature detection on one stored object and optionally draw the boxes.

    PYTHONPATH=src python scripts/detect_signatures.py s3://BUCKET/KEY [--render DIR]

Uses the current AWS credentials in eu-central-1. Textract is billed per page.
Reads the object and writes only to DIR; nothing is changed in AWS.
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import boto3
import pymupdf

from document_processing.signatures import TEXTRACT_REGION, TextractSignatureDetector

parser = argparse.ArgumentParser()
parser.add_argument("uri", help="s3://bucket/key of a PDF, PNG or JPEG")
parser.add_argument("--render", metavar="DIR", help="write one PNG per page with signature boxes in red")
parser.add_argument("--version", help="S3 object version id")
args = parser.parse_args()

target = urlparse(args.uri)
if target.scheme != "s3" or not target.netloc or not target.path.strip("/"):
    sys.exit("expected s3://bucket/key")
bucket, key = target.netloc, target.path.lstrip("/")
content_type = "application/pdf" if key.lower().endswith(".pdf") else "image/png" if key.lower().endswith(".png") else "image/jpeg"

section = TextractSignatureDetector(bucket, region=TEXTRACT_REGION).detect(key, content_type, args.version)
print(json.dumps(section.model_dump(), ensure_ascii=False, indent=2))

if args.render and section.status == "completed" and section.signatures:
    body = boto3.client("s3", region_name=TEXTRACT_REGION).get_object(Bucket=bucket, Key=key)["Body"].read()
    out = Path(args.render)
    out.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(stream=body, filetype=content_type.split("/")[1]) as document:
        for number in sorted({s.page for s in section.signatures}):
            page = document[number - 1]
            for item in (s for s in section.signatures if s.page == number):
                x0, y0, x1, y1 = item.bbox
                width, height = page.rect.width, page.rect.height
                page.draw_rect(pymupdf.Rect(x0 * width, y0 * height, x1 * width, y1 * height), color=(1, 0, 0), width=2)
            page.get_pixmap(dpi=90).save(out / f"{Path(key).stem}-page-{number}.png")
