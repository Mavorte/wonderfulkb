"""Locate signatures with Amazon Textract and attribute each to a party by nearby OCR text.

The output only says that a signature-like mark exists at a position and which
party label stands next to it. It does not establish that a signature is genuine,
and it does not establish that every signature on the page was found.
"""
import hashlib
import re
import time
import unicodedata

from .models import SignatureItem, SignatureSection
from .providers import ProviderError

# Textract SIGNATURES is billed per page and only runs in the configured region.
TEXTRACT_REGION = "eu-central-1"
NEARBY_MAX_DY = 0.10        # relative page height searched around the box
NEARBY_MAX_DX = 0.25        # relative page width beyond the box edges
NEARBY_KEEP = 6
# Two different party labels this close in distance make the attribution a guess.
ROLE_AMBIGUITY_MARGIN = 0.05

# Czech party labels, matched on diacritic-free lowercase word starts.
ROLE_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("guarantor", re.compile(r"\bruci?tel")),
    ("borrower", re.compile(r"\b(dluznik|zadatel|klient|prijemce financovani)")),
    ("provider", re.compile(r"\b(veritel|poskytovatel|banka\b|banku\b)")),
    ("buyer", re.compile(r"\bkupujic")),
    ("supplier", re.compile(r"\b(prodavajic|dodavatel|prodejce)")),
    ("insurer", re.compile(r"\b(pojistitel|pojistovn)")),
)


def _fold(text):
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _clamp(value):
    return min(1.0, max(0.0, value))


def box_to_corners(geometry):
    box = geometry["BoundingBox"]
    left, top = _clamp(box["Left"]), _clamp(box["Top"])
    return [round(left, 5), round(top, 5),
            round(_clamp(box["Left"] + box["Width"]), 5), round(_clamp(box["Top"] + box["Height"]), 5)]


def role_for_line(text):
    """Return the one role a label line names; ambiguous or unlabelled lines return None."""
    folded = _fold(text)
    found = {role for role, pattern in ROLE_PATTERNS if pattern.search(folded)}
    return found.pop() if len(found) == 1 else None


def assign_role(context):
    """Role of the nearest party label, or unknown when none exists or two different labels compete."""
    labelled = [(distance, text, role_for_line(text)) for distance, text in context]
    labelled = [item for item in labelled if item[2]]
    if not labelled:
        return "unknown", None
    distance, text, role = labelled[0]
    if any(other != role and d - distance <= ROLE_AMBIGUITY_MARGIN for d, _, other in labelled[1:]):
        return "unknown", None
    return role, text


def nearby_lines(box, lines):
    """(distance, text) of lines around a signature box, nearest first; `lines` are (text, corners)."""
    x0, y0, x1, y1 = box
    cy = (y0 + y1) / 2
    ranked = []
    for text, (lx0, ly0, lx1, ly1) in lines:
        dy = abs((ly0 + ly1) / 2 - cy)
        dx = max(0.0, lx0 - x1, x0 - lx1)
        if dy <= NEARBY_MAX_DY and dx <= NEARBY_MAX_DX and text.strip():
            ranked.append((dy + 0.5 * dx, text.strip()))
    ranked.sort(key=lambda item: item[0])
    return ranked


def build_signatures(blocks):
    """Turn Textract blocks (all result pages concatenated) into SignatureItem records."""
    lines_by_page: dict[int, list] = {}
    for block in blocks:
        if block["BlockType"] == "LINE" and block.get("Text"):
            lines_by_page.setdefault(block.get("Page", 1), []).append(
                (block["Text"], box_to_corners(block["Geometry"])))
    items = []
    for block in blocks:
        if block["BlockType"] != "SIGNATURE":
            continue
        page = block.get("Page", 1)
        bbox = box_to_corners(block["Geometry"])
        context = nearby_lines(bbox, lines_by_page.get(page, []))
        role, evidence = assign_role(context)
        digest = hashlib.sha1(f"{page}:{bbox}".encode()).hexdigest()[:12]
        items.append(SignatureItem(
            signature_id=f"sig-{page}-{digest}", page=page, bbox=bbox,
            detection_score=block.get("Confidence"), role=role,
            role_source="nearest_text" if evidence else None, role_evidence=evidence,
            nearby_text=[text for _, text in context[:NEARBY_KEEP]]))
    items.sort(key=lambda item: (item.page, item.bbox[1], item.bbox[0]))
    return items


class TextractSignatureDetector:
    """Runs Textract against a stored object and never lets a failure fail the document."""

    def __init__(self, bucket, client=None, region=TEXTRACT_REGION, timeout_seconds=150, poll_seconds=2.0,
                 sleep=time.sleep):
        if region != TEXTRACT_REGION:
            raise ValueError("Textract signature detection is restricted to eu-central-1 (Frankfurt)")
        if client is None:
            import boto3
            client = boto3.client("textract", region_name=region)
        self.client, self.bucket = client, bucket
        self.timeout_seconds, self.poll_seconds, self.sleep = timeout_seconds, poll_seconds, sleep

    def _location(self, key, version):
        location = {"Bucket": self.bucket, "Name": key}
        if version and version != "local-immutable":
            location["Version"] = version
        return {"S3Object": location}

    def _blocks_async(self, key, version):
        started = self.client.start_document_analysis(
            DocumentLocation=self._location(key, version), FeatureTypes=["SIGNATURES"])
        job_id, deadline = started["JobId"], time.monotonic() + self.timeout_seconds
        while True:
            page = self.client.get_document_analysis(JobId=job_id)
            if page["JobStatus"] == "SUCCEEDED":
                break
            if page["JobStatus"] in ("FAILED", "PARTIAL_SUCCESS"):
                raise ProviderError("TEXTRACT_JOB_" + page["JobStatus"], False)
            if time.monotonic() > deadline:
                raise ProviderError("TEXTRACT_TIMEOUT", True)
            self.sleep(self.poll_seconds)
        blocks = list(page["Blocks"])
        # Results arrive in parts of up to 1000 blocks.
        while page.get("NextToken"):
            page = self.client.get_document_analysis(JobId=job_id, NextToken=page["NextToken"])
            blocks.extend(page["Blocks"])
        return blocks

    def _blocks_image(self, key, version):
        # Asynchronous analysis accepts only PDF and TIFF; a PNG/JPEG is one page.
        response = self.client.analyze_document(
            Document=self._location(key, version), FeatureTypes=["SIGNATURES"])
        return response["Blocks"]

    def detect(self, key, content_type, version=None):
        try:
            blocks = (self._blocks_async if content_type == "application/pdf" else self._blocks_image)(key, version)
            return SignatureSection(status="completed", signatures=build_signatures(blocks))
        except ProviderError as error:
            return SignatureSection(status="failed", error=error.code)
        except Exception as error:
            # Code only: botocore messages can carry object keys and account details.
            response = getattr(error, "response", None)
            code = response.get("Error", {}).get("Code", "ERROR") if isinstance(response, dict) else "ERROR"
            return SignatureSection(status="failed", error="TEXTRACT_" + re.sub(r"\W", "_", str(code)).upper())
