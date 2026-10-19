"""Živý smoke test proti skutečným úložištím (jen čtení API; zapisuje a nakonec maže VLASTNÍ testovací case).

    AWS_PROFILE=hackathon AWS_REGION=eu-central-1 python3 live_smoke.py

Zapíše do tabulky, bucketu a indexů dva krátce žijící dokumenty case `wonderfulkb-apitest-<hex>` (štítek `apitest`),
zavolá `core.handle` se skutečnými klienty (klíč ze Secrets Manageru, nikdy se nevypisuje) a vše smaže.
"""
import json
import random
import sys
import uuid

import boto3

import core

cfg = core.Config({})
REG = core.REGION
ddb, s3 = boto3.client("dynamodb", region_name=REG), boto3.client("s3", region_name=REG)
vec = boto3.client("s3vectors", region_name=REG)
sec = boto3.client("secretsmanager", region_name=REG)
CASE = "wonderfulkb-apitest-" + uuid.uuid4().hex[:8]
A, B = "apitest-doc-a", "apitest-doc-b"
rnd = random.Random(7)
base = [rnd.gauss(0, 1) for _ in range(1024)]
noise = lambda s: [x + random.Random(s).gauss(0, 0.2) for x in base]  # noqa: E731
tags = {"project": "wonderfulkb"}
fails = 0


def check(label, cond, detail=""):
    global fails
    print(("OK   " if cond else "FAIL ") + label + (f"  {detail}" if not cond else ""))
    fails += not cond


def md(did, verified, **kw):
    return dict(case_id=CASE, document_id=did, label="apitest", verified=verified, model="apitest", model_version="v0", **kw)


def put_vec(index, key, v, m):
    vec.put_vectors(vectorBucketName=cfg.vector_bucket, indexName=index,
                    vectors=[{"key": key, "data": {"float32": v}, "metadata": m}])


def row(did, **extra):
    p = f"cases/{CASE}/analysis/{did}/"
    it = {"case_id": CASE, "document_id": did, "title": "apitest.pdf", "label": "apitest",
          "label_status": "predicted", "description": "živý smoke test", "confidence": "0.5",
          "page_count": 1, "processing_status": "completed", "text_s3_key": p + "text.txt",
          "signatures_s3_key": p + "signatures.json", "pipeline_version": "apitest", "updated_at": "2026-10-19T00:00:00Z"}
    it.update(extra)
    from boto3.dynamodb.types import TypeSerializer
    ser = TypeSerializer()
    ddb.put_item(TableName=cfg.analysis_table, Item={k: ser.serialize(v if k != "confidence" else __import__("decimal").Decimal(v))
                                                     for k, v in it.items()})
    s3.put_object(Bucket=cfg.bucket, Key=p + "text.txt", Body="Strana 1\fStrana 2 – žluťoučký kůň".encode())
    sig = {"case_id": CASE, "document_id": did, "signatures": [{
        "signature_id": "sig_01", "page": 1, "bbox": [0.1, 0.7, 0.4, 0.8], "detector": "textract", "detection_score": 50.0,
        "role": "borrower", "role_source": "nearest_text", "role_evidence": "Za dlužníka", "phash": "00ff00ff00ff00ff",
        "copy_suspicion": {"level": "none", "matches": []}}]}
    s3.put_object(Bucket=cfg.bucket, Key=p + "signatures.json", Body=json.dumps(sig).encode())
    s3.put_object(Bucket=cfg.bucket, Key=p + "signatures/sig_01.png", Body=b"\x89PNG\r\n\x1a\n")


def cleanup():
    for d in (A, B):
        ddb.delete_item(TableName=cfg.analysis_table, Key={"case_id": {"S": CASE}, "document_id": {"S": d}})
    for idx, keys in ((cfg.text_index, [f"{A}#t0", f"{A}#t1", f"{B}#t0"]), (cfg.image_index, [f"{A}#p1"]),
                      (cfg.sig_index, [f"{A}#s0", f"{B}#s0"])):
        vec.delete_vectors(vectorBucketName=cfg.vector_bucket, indexName=idx, keys=keys)
    r = s3.list_object_versions(Bucket=cfg.bucket, Prefix=f"cases/{CASE}/")
    for v in r.get("Versions", []) + r.get("DeleteMarkers", []):
        s3.delete_object(Bucket=cfg.bucket, Key=v["Key"], VersionId=v["VersionId"])


def main():
    key = sec.get_secret_value(SecretId=cfg.secret_id)["SecretString"].strip()
    api = core.Api()
    get = lambda path, q=None, k=key: core.handle("GET", "/v1" + path, q or {}, {"x-api-key": k}, api=api)  # noqa: E731
    try:
        row(A)
        row(B, label_status="verified")
        put_vec(cfg.text_index, f"{A}#t0", noise(1), md(A, False, page=1, page_from=1, page_to=1, chunk_id="c0"))
        put_vec(cfg.text_index, f"{A}#t1", noise(2), md(A, False, page=2, page_from=2, page_to=2, chunk_id="c1"))
        put_vec(cfg.text_index, f"{B}#t0", noise(3), md(B, True, page=1, page_from=1, page_to=2, chunk_id="c0"))
        put_vec(cfg.image_index, f"{A}#p1", noise(4), md(A, False, page=1))
        put_vec(cfg.sig_index, f"{A}#s0", noise(5), md(A, False, page=1))
        put_vec(cfg.sig_index, f"{B}#s0", noise(6), md(B, True, page=1))

        st, b = get(f"/cases/{CASE}/documents")
        check("seznam: 2 dokumenty", st == 200 and [d["document_id"] for d in b["documents"]] == [A, B], (st, b))
        st, b = get(f"/cases/{CASE}/documents/{A}")
        check("dokument: text z S3 (UTF-8, \\f), confidence float", st == 200 and b["text"] == "Strana 1\fStrana 2 – žluťoučký kůň"
              and b["confidence"] == 0.5 and b["page_count"] == 1, (st, str(b)[:200]))
        st, b = get(f"/cases/{CASE}/documents/{A}/vectors", {"similar_to_verified": ["5"], "include_values": ["false"]})
        check("vektory: 2 textové, 1 obrazový, bez hodnot", st == 200 and len(b["text_vectors"]) == 2 and len(b["image_vectors"]) == 1
              and all("values" not in v and v["dimension"] == 1024 for v in b["text_vectors"] + b["image_vectors"]), (st, str(b)[:300]))
        nb = b.get("neighbors", [])
        check("neighbors: jen ověřený dokument B, ne vlastní; score v 0..1",
              st == 200 and nb and nb[0]["document_id"] == B and all(n["document_id"] != A and 0 <= n["score"] <= 1 for n in nb)
              and all(n["document_id"].startswith("apitest") or n["label"] for n in nb), nb)
        print("     neighbors (počet, první):", len(nb), nb[:1])
        st, b = get(f"/cases/{CASE}/documents/{A}/vectors", {"include": ["text"]})
        check("vektory s hodnotami", st == 200 and len(b["text_vectors"][0]["values"]) == 1024 and b["image_vectors"] == [], st)
        st, b = get(f"/cases/{CASE}/documents/{A}/signatures", {"match_client": ["true"]})
        s = b["signatures"][0] if st == 200 else {}
        check("podpisy: crop_url, vektor, similar_signatures z téhož case",
              st == 200 and "X-Amz-Expires=300" in s["crop_url"] and ".s3.eu-central-1.amazonaws.com" in s["crop_url"]
              and s["vector"]["dimension"] == 1024 and s["similar_signatures"] and s["similar_signatures"][0]["document_id"] == B, (st, str(s)[:300]))
        print("     similar_signatures:", s.get("similar_signatures"))
        st, b = get(f"/cases/{CASE}/documents/{A}/signatures", {"include_vectors": ["false"]})
        check("podpisy bez vektoru", st == 200 and "vector" not in b["signatures"][0], st)
        check("špatný klíč 403", get(f"/cases/{CASE}/documents", k="spatny")[0] == 403)
        check("neznámý dokument 404", get(f"/cases/{CASE}/documents/neexistuje")[0] == 404)
        check("neznámý case 404", get("/cases/wonderfulkb-neexistuje/documents")[0] == 404)
    finally:
        cleanup()
        left = ddb.query(TableName=cfg.analysis_table, KeyConditionExpression="case_id = :c",
                         ExpressionAttributeValues={":c": {"S": CASE}}, Select="COUNT")["Count"]
        print("úklid hotov, zbylé řádky v tabulce:", left)
    sys.exit(1 if fails else 0)


main()
