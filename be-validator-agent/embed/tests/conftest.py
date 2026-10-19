import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # infra/validator-agent

DIM = 1024


def png(w=300, h=200, color="white") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


class FakeBedrock:
    def __init__(self, fail_first=0):
        self.calls = []
        self.fail_first = fail_first

    def invoke_model(self, modelId, body, **kw):
        from botocore.exceptions import ClientError
        if self.fail_first > 0:
            self.fail_first -= 1
            raise ClientError({"Error": {"Code": "ThrottlingException", "Message": "x"},
                               "ResponseMetadata": {"HTTPStatusCode": 429}}, "InvokeModel")
        body = json.loads(body)
        self.calls.append((modelId, body))

        def one():
            vec = [0.0] * DIM
            vec[(len(self.calls) + one.n) % DIM] = 1.0
            one.n += 1
            return vec
        one.n = 0
        if "cohere" in modelId:
            n = len(body.get("texts") or body.get("images") or [])
            out = {"embeddings": {"float": [one() for _ in range(n)]}, "response_type": "embeddings_by_type"}
        else:
            out = {"embedding": one()}
        return {"body": io.BytesIO(json.dumps(out).encode())}


class FakeS3Vectors:
    """Minimální paměťová náhrada s filtry $eq/$ne/$and nad metadaty."""

    def __init__(self):
        self.store = {}  # (index, key) -> {"data","metadata"}
        self.put_sizes = []

    def put_vectors(self, vectorBucketName, indexName, vectors):
        assert vectorBucketName == "wonderfulkb-vectors"
        assert len(vectors) <= 500
        self.put_sizes.append(len(vectors))
        for v in vectors:
            assert len(v["data"]["float32"]) == DIM
            self.store[(indexName, v["key"])] = {"data": v["data"], "metadata": v["metadata"]}

    def delete_vectors(self, vectorBucketName, indexName, keys):
        assert len(keys) <= 500
        for k in keys:
            self.store.pop((indexName, k), None)

    def get_vectors(self, vectorBucketName, indexName, keys, returnData=False, returnMetadata=False):
        return {"vectors": [{"key": k, "data": self.store[(indexName, k)]["data"],
                             "metadata": self.store[(indexName, k)]["metadata"]}
                            for k in keys if (indexName, k) in self.store]}

    @staticmethod
    def _match(meta, flt):
        if "$and" in flt:
            return all(FakeS3Vectors._match(meta, f) for f in flt["$and"])
        (field, cond), = flt.items()
        (op, val), = cond.items()
        return meta.get(field) == val if op == "$eq" else meta.get(field) != val

    def query_vectors(self, vectorBucketName, indexName, queryVector, topK, filter=None,
                      returnMetadata=False, returnDistance=False):
        q = queryVector["float32"]
        hits = []
        for (idx, key), v in self.store.items():
            if idx != indexName or (filter and not self._match(v["metadata"], filter)):
                continue
            d = v["data"]["float32"]
            dot = sum(a * b for a, b in zip(q, d))
            nq = sum(a * a for a in q) ** .5
            nd = sum(a * a for a in d) ** .5
            hits.append({"key": key, "distance": 1 - dot / (nq * nd), "metadata": v["metadata"]})
        hits.sort(key=lambda h: h["distance"])
        return {"vectors": hits[:topK]}


@pytest.fixture
def bedrock():
    return FakeBedrock()


@pytest.fixture
def s3v():
    return FakeS3Vectors()


@pytest.fixture(autouse=True)
def no_rate_limit(monkeypatch):
    from embed import clients
    monkeypatch.setattr(clients, "bedrock_limiter", clients.RateLimiter(limit=0))
    monkeypatch.setattr(clients.time, "sleep", lambda s: None)
