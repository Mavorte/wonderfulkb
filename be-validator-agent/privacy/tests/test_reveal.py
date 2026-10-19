import json
import logging

import boto3
import pytest
from moto import mock_aws

from signature_privacy import (DecryptionError, KmsKeyProvider, api_key_id, encrypt_image, reveal_signature)

BUCKET = "wonderfulkb-raw-document-storage"
KEY = "cases/case-1/analysis/doc-1/signatures/sig_01.png.enc"


@pytest.fixture(scope="module")
def env():
    with mock_aws():
        s3 = boto3.client("s3", region_name="eu-central-1")
        s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-central-1"})
        kms = boto3.client("kms", region_name="eu-central-1")
        kid = kms.create_key()["KeyMetadata"]["KeyId"]
        yield s3, KmsKeyProvider(kid, client=kms)


def test_reveal_returns_png_and_audits(env, sig_png, ctx, caplog):
    s3, p = env
    s3.put_object(Bucket=BUCKET, Key=KEY, Body=encrypt_image(sig_png, ctx, p))
    caplog.set_level(logging.INFO, logger="wonderfulkb.privacy.audit")
    assert reveal_signature(s3, BUCKET, KEY, ctx, p, caller="fp:abc", request_id="r1") == sig_png
    rec = json.loads(caplog.records[-1].getMessage())
    assert rec["caller"] == "fp:abc" and rec["signature_id"] == "sig_01" and rec["outcome"] == "revealed" and rec["ts"]
    assert "PNG" not in caplog.text


def test_reveal_wrong_signature_is_denied_and_audited(env, sig_png, ctx, caplog):
    s3, p = env
    s3.put_object(Bucket=BUCKET, Key=KEY, Body=encrypt_image(sig_png, ctx, p))
    caplog.set_level(logging.INFO, logger="wonderfulkb.privacy.audit")
    with pytest.raises(DecryptionError):
        reveal_signature(s3, BUCKET, KEY, ctx._replace(signature_id="sig_02"), p, caller="c")
    assert json.loads(caplog.records[-1].getMessage())["outcome"] == "denied"


def test_reveal_missing_object_audited(env, ctx, caplog):
    s3, p = env
    caplog.set_level(logging.INFO, logger="wonderfulkb.privacy.audit")
    with pytest.raises(Exception):
        reveal_signature(s3, BUCKET, "cases/x", ctx, p, caller="c")
    assert json.loads(caplog.records[-1].getMessage())["outcome"] == "error"


def test_api_key_id_never_contains_the_key():
    assert api_key_id({"identity": {"apiKeyId": "k123"}}, "secret") == "k123"
    fp = api_key_id({}, "secret-value")
    assert fp.startswith("fp:") and "secret" not in fp and len(fp) == 15
    assert api_key_id() == "unknown"
