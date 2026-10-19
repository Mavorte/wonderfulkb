"""Fake klient S3 Vectors (moto ho zatím nemá). Jen to, co API používá: get_vectors a query_vectors.
Chování podle dokumentace: kosinová vzdálenost = 1 - kosinus, filtr s $eq/$ne/$in/$nin/$and/$or, metadata se vrací na žádost."""
import math


def _cos(a, b):
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def _match(md, f):
    for k, v in f.items():
        if k == "$and":
            if not all(_match(md, x) for x in v):
                return False
        elif k == "$or":
            if not any(_match(md, x) for x in v):
                return False
        else:
            cond = v if isinstance(v, dict) else {"$eq": v}
            for op, arg in cond.items():
                val = md.get(k)
                ok = {"$eq": lambda: k in md and val == arg, "$ne": lambda: val != arg,
                      "$in": lambda: val in arg, "$nin": lambda: val not in arg}[op]()
                if not ok:
                    return False
    return True


class FakeVectors:
    def __init__(self, dimension=1024):
        self.dimension = dimension
        self.idx = {}  # (bucket, index) -> {key: (vector, metadata)}
        self.calls = []

    def put(self, bucket, index, key, vector, metadata):
        assert len(vector) == self.dimension, "dimenze indexu"
        self.idx.setdefault((bucket, index), {})[key] = (list(vector), dict(metadata))

    def get_vectors(self, vectorBucketName, indexName, keys, returnData=False, returnMetadata=False):
        self.calls.append(("get_vectors", indexName, len(keys)))
        assert len(keys) <= 100, "GetVectors bere nejvýš 100 klíčů"
        store = self.idx.get((vectorBucketName, indexName), {})
        out = []
        for k in keys:
            if k in store:
                v, md = store[k]
                e = {"key": k}
                if returnData:
                    e["data"] = {"float32": v}
                if returnMetadata:
                    e["metadata"] = md
                out.append(e)
        return {"vectors": out}

    def query_vectors(self, vectorBucketName, indexName, topK, queryVector, filter=None,
                      returnMetadata=False, returnDistance=False):
        self.calls.append(("query_vectors", indexName, topK, filter))
        assert 1 <= topK <= 100
        q = queryVector["float32"]
        hits = []
        for k, (v, md) in self.idx.get((vectorBucketName, indexName), {}).items():
            if filter and not _match(md, filter):
                continue
            hits.append((1.0 - _cos(q, v), k, md))
        hits.sort(key=lambda t: t[0])
        out = []
        for d, k, md in hits[:topK]:
            e = {"key": k}
            if returnDistance:
                e["distance"] = d
            if returnMetadata:
                e["metadata"] = md
            out.append(e)
        return {"vectors": out}
