"""Writes results to S3 in the layout of be-validator-agent/docs/validator-agent-storage.md:

    cases/<case_id>/analysis/<document_id>/signatures.json            body of call 3, without crop_url
    cases/<case_id>/analysis/<document_id>/signatures/<sig>.png       readable crop   (only with allow_plain=True)
    cases/<case_id>/analysis/<document_id>/signatures/<sig>.png.enc   encrypted crop  (encrypt=True)
    cases/<case_id>/analysis/<document_id>/signatures/<sig>.preview.png  distorted preview (encrypt=True)

Readable crops are not written any more (decision of 19. 10. 2026, be-validator-agent/docs/validator-agent-privacy.md): a store that
neither encrypts nor is explicitly allowed to write readable files refuses to save. Encryption uses the
`signature_privacy` library from infra/validator-agent/privacy/ (KMS alias/wonderfulkb-signatures).
"""
import json
import sys
from pathlib import Path

BUCKET = "wonderfulkb-raw-document-storage"
TAGGING = "project=wonderfulkb"
_PRIVACY_DIR = Path(__file__).resolve().parents[2] / "privacy"


class PlaintextNotAllowed(RuntimeError):
    """The store would write a readable signature crop without being allowed to."""


def analysis_prefix(case_id, document_id):
    return f"cases/{case_id}/analysis/{document_id}/"


def _privacy():
    """`signature_privacy` (sibling directory of the repository), imported only when encryption is on."""
    try:
        import signature_privacy
    except ImportError:
        sys.path.insert(0, str(_PRIVACY_DIR))
        import signature_privacy
    return signature_privacy


def object_exists(client, bucket, key):
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception as error:   # botocore ClientError: 404 / NoSuchKey / NotFound means free
        code = getattr(error, "response", {}).get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


class S3CropStore:
    """Crop store for `process_pdf`. `crop_url` stays empty (the API adds its own link).

    encrypt=True      crop -> `.png.enc` (AES-256-GCM, KMS envelope, context = case/document/signature) and a
                      distorted `.preview.png`; no readable PNG is written.
    allow_plain=True  readable `.png` (development only).
    on_plain          optional callable `(case_id, document_id, signature_id, png_bytes)` called with the
                      plaintext crop in memory before it is encrypted or written (embedding of the crop goes
                      here, so the crop is never read back from S3).
    """
    s3 = True

    def __init__(self, client=None, bucket=BUCKET, encrypt=False, provider=None, allow_plain=False, on_plain=None):
        if client is None:
            import boto3
            client = boto3.client("s3", region_name="eu-central-1")
        self.client, self.bucket = client, bucket
        self.encrypt, self.provider, self.allow_plain, self.on_plain = encrypt, provider, allow_plain, on_plain

    def _put(self, key, body, content_type, metadata=None):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type,
                               Metadata={"project": "wonderfulkb", **(metadata or {})}, Tagging=TAGGING)

    def save(self, case_id, document_id, signature_id, png):
        if not self.encrypt and not self.allow_plain:
            raise PlaintextNotAllowed("readable signature crops are not written; use encrypt=True "
                                      "(or allow_plain=True for development)")
        if self.on_plain:
            self.on_plain(case_id, document_id, signature_id, png)
        base = f"{analysis_prefix(case_id, document_id)}signatures/{signature_id}"
        if not self.encrypt:
            self._put(base + ".png", png, "image/png")
            return base + ".png", None
        privacy = _privacy()
        context = privacy.SignatureContext(case_id, document_id, signature_id)
        blob = privacy.encrypt_image(png, context, self.provider)
        self._put(base + ".png.enc", blob, "application/octet-stream", {"enc": "wkbs1"})
        self._put(base + ".preview.png", privacy.distorted_preview(png), "image/png")
        return base + ".png.enc", None


def write_signatures_json(response, client=None, bucket=BUCKET, overwrite=False):
    """`response` is one item of `process_case(...)`. Returns the S3 key (for `signatures_s3_key`).

    An existing `signatures.json` is never replaced unless `overwrite=True`: `FileExistsError` instead.
    """
    if client is None:
        import boto3
        client = boto3.client("s3", region_name="eu-central-1")
    key = analysis_prefix(response["case_id"], response["document_id"]) + "signatures.json"
    if not overwrite and object_exists(client, bucket, key):
        raise FileExistsError(f"s3://{bucket}/{key} already exists")
    body = {"case_id": response["case_id"], "document_id": response["document_id"],
            "signatures": [{k: v for k, v in s.items() if k != "crop_url"} for s in response["signatures"]]}
    client.put_object(Bucket=bucket, Key=key, Body=json.dumps(body, ensure_ascii=False).encode(),
                      ContentType="application/json", Metadata={"project": "wonderfulkb"}, Tagging=TAGGING)
    return key
