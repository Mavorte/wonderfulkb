import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # infra/validator-agent

REGION, BUCKET = "eu-central-1", "wonderfulkb-raw-document-storage"
HASHES, DOCUMENTS, ANALYSIS = "wonderfulkb-uw-content-hashes", "wonderfulkb-uw-documents", "wonderfulkb-uw-document-analysis"
SHA_A, SHA_B = "a" * 64, "b" * 64


class FakeS3Vectors:
    """Jen put_vectors a get_vectors (moto S3 Vectors zatím nemá); počítá volání."""

    def __init__(self):
        self.store = {}  # (index, key) -> {"data": ..., "metadata": ...}
        self.calls = []

    def put_vectors(self, vectorBucketName, indexName, vectors):
        assert len(vectors) <= 500
        self.calls.append(("put", indexName, len(vectors)))
        for v in vectors:
            self.store[(indexName, v["key"])] = {"key": v["key"], "data": v["data"], "metadata": dict(v["metadata"])}

    def get_vectors(self, vectorBucketName, indexName, keys, returnData=False, returnMetadata=False):
        assert len(keys) <= 100
        self.calls.append(("get", indexName, len(keys)))
        out = []
        for key in keys:
            item = self.store.get((indexName, key))
            if item:
                out.append({"key": key, **({"data": item["data"]} if returnData else {}),
                            **({"metadata": item["metadata"]} if returnMetadata else {})})
        return {"vectors": out}

    def keys(self, index):
        return sorted(k for i, k in self.store if i == index)


def make_table(ddb, name, pk, sk):
    ddb.create_table(TableName=name, BillingMode="PAY_PER_REQUEST",
                     AttributeDefinitions=[{"AttributeName": pk, "AttributeType": "S"}, {"AttributeName": sk, "AttributeType": "S"}],
                     KeySchema=[{"AttributeName": pk, "KeyType": "HASH"}, {"AttributeName": sk, "KeyType": "RANGE"}])


@pytest.fixture
def aws(monkeypatch):
    for name in ("AWS_PROFILE", "PIPELINE_SKIP", "PIPELINE_NO_REUSE", "DEDUP_TEMPLATE_THRESHOLD", "DEDUP_HASHES_TABLE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    with mock_aws():
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION})
        ddb = boto3.client("dynamodb", region_name=REGION)
        make_table(ddb, HASHES, "sha256", "case_document")
        make_table(ddb, DOCUMENTS, "case_id", "document_id")
        make_table(ddb, ANALYSIS, "case_id", "document_id")
        yield s3


@pytest.fixture
def hashes(aws):
    return boto3.resource("dynamodb", region_name=REGION).Table(HASHES)
