"""Fixtury pro lokální vývoj a kontraktový test: moto (DynamoDB, S3, Secrets Manager) + FakeVectors.

Data převezme z mocku (infra/validator-agent-mock/seed.py: skutečné texty vzorových dokumentů, deterministické
vektory a podpisy) a zapíše je ve tvaru z be-validator-agent/docs/validator-agent-storage.md. Mock se tím nemění, jen se čte.
"""
import hashlib
import importlib.util
import json
import os
import sys

from boto3.dynamodb.types import TypeSerializer

from core import Api, Clients, Config
from fakes import FakeVectors

# Výřezy se do fixtur zapisují stejně jako je zapisuje signature pipeline: šifrovaně (.png.enc) + zkreslený náhled.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "privacy"))
from signature_privacy import LocalKeyProvider, SignatureContext, distorted_preview, encrypt_image  # noqa: E402

API_KEY = "test-api-key-not-a-secret"
HERE = os.path.dirname(os.path.abspath(__file__))
# repo: be-validator-agent/mock; pracovní kopie: infra/validator-agent-mock
SEED_PATH = next((p for p in (os.path.join(HERE, "..", "mock", "seed.py"),
                              os.path.join(HERE, "..", "..", "validator-agent-mock", "seed.py")) if os.path.exists(p)),
                 os.path.join(HERE, "..", "mock", "seed.py"))
REGION = "eu-central-1"
_ser = TypeSerializer()


def _seed_module():
    spec = importlib.util.spec_from_file_location("mock_seed", SEED_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _put(ddb, table, item):
    ddb.put_item(TableName=table, Item={k: _ser.serialize(v) for k, v in item.items() if v is not None})


def add_document_hash(ddb, cfg, case_id, document_id, sha256, label=None, register=True):
    """Řádek v tabulce dokumentů ingestu (jen sha256 a klíč) a záznam v indexu hashů."""
    _put(ddb, cfg.documents_table, {"case_id": case_id, "document_id": document_id, "sha256": sha256})
    if register:
        _put(ddb, cfg.hashes_table, {"sha256": sha256, "case_document": f"{case_id}#{document_id}",
                                     "case_id": case_id, "document_id": document_id, "label": label,
                                     "registered_at": "2026-10-19T12:00:00Z"})


def build(api_key=API_KEY):
    """Musí běžet uvnitř moto `mock_aws()`. Vrátí (Api, index případů pro test)."""
    import boto3
    for k, v in (("AWS_ACCESS_KEY_ID", "testing"), ("AWS_SECRET_ACCESS_KEY", "testing"),
                 ("AWS_DEFAULT_REGION", REGION)):
        os.environ.setdefault(k, v)
    seed = _seed_module()
    store = seed.Store()
    cfg = Config({"API_KEY": api_key})
    ddb = boto3.client("dynamodb", region_name=REGION)
    s3 = boto3.client("s3", region_name=REGION)
    for t in (cfg.analysis_table, cfg.cases_table):
        keys = [{"AttributeName": "case_id", "KeyType": "HASH"}]
        attrs = [{"AttributeName": "case_id", "AttributeType": "S"}]
        if t == cfg.analysis_table:
            keys.append({"AttributeName": "document_id", "KeyType": "RANGE"})
            attrs.append({"AttributeName": "document_id", "AttributeType": "S"})
        ddb.create_table(TableName=t, KeySchema=keys, AttributeDefinitions=attrs, BillingMode="PAY_PER_REQUEST")
    # duplicity napříč případy: tabulka dokumentů ingestu (jen sha256) a index hashů
    ddb.create_table(TableName=cfg.documents_table, BillingMode="PAY_PER_REQUEST",
                     KeySchema=[{"AttributeName": "case_id", "KeyType": "HASH"},
                                {"AttributeName": "document_id", "KeyType": "RANGE"}],
                     AttributeDefinitions=[{"AttributeName": "case_id", "AttributeType": "S"},
                                           {"AttributeName": "document_id", "AttributeType": "S"}])
    ddb.create_table(TableName=cfg.hashes_table, BillingMode="PAY_PER_REQUEST",
                     KeySchema=[{"AttributeName": "sha256", "KeyType": "HASH"},
                                {"AttributeName": "case_document", "KeyType": "RANGE"}],
                     AttributeDefinitions=[{"AttributeName": "sha256", "AttributeType": "S"},
                                           {"AttributeName": "case_document", "AttributeType": "S"}])
    s3.create_bucket(Bucket=cfg.bucket, CreateBucketConfiguration={"LocationConstraint": REGION})
    vec = FakeVectors(cfg.dimension)
    provider = LocalKeyProvider.generate()  # hlavní klíč jen v paměti procesu; v AWS je to KMS

    for cid, c in store.cases.items():
        _put(ddb, cfg.cases_table, {"case_id": cid, "client": c["client"]})
    for (cid, did), d in store.docs.items():
        ready = d["processing_status"] in ("completed", "partial")
        prefix = f"cases/{cid}/analysis/{did}/"
        row = {"case_id": cid, "document_id": did, "title": d["title"], "label": d["label"],
               "label_status": d["label_status"], "description": d["description"],
               "confidence": None if d["confidence"] is None else __import__("decimal").Decimal(str(d["confidence"])),
               "processing_status": d["processing_status"], "pipeline_version": "fixture",
               "updated_at": "2026-10-19T12:00:00Z"}
        if ready:
            row.update(page_count=d["page_count"], text_s3_key=prefix + "text.txt")
            if d["pages_failed"]:
                row["pages_failed"] = set(d["pages_failed"])
            s3.put_object(Bucket=cfg.bucket, Key=prefix + "text.txt", Body=d["text"].encode("utf-8"))
            sigs = []
            for s in d.get("_sigs", []):
                matches = [dict(signature_id=o["signature_id"], document_id=o["_doc"][1], score=1.0)
                           for o in store.sigs.values() if o["phash"] == s["phash"] and o["_doc"] != s["_doc"]]
                sid = s["signature_id"]
                sigs.append({k: s[k] for k in ("signature_id", "page", "bbox", "detector", "detection_score",
                                               "role", "role_source", "role_evidence", "phash")}
                            | {"copy_suspicion": {"level": "suspected" if matches else "none", "matches": matches},
                               "crop_s3_key": f"{prefix}signatures/{sid}.png.enc", "crop_encrypted": True})
                png = seed.signature_png(s["_seed"])
                s3.put_object(Bucket=cfg.bucket, Key=f"{prefix}signatures/{sid}.png.enc",
                              Body=encrypt_image(png, SignatureContext(cid, did, sid), provider))
                s3.put_object(Bucket=cfg.bucket, Key=f"{prefix}signatures/{sid}.preview.png",
                              Body=distorted_preview(png))
                n = int(s["signature_id"].split("_")[1]) - 1  # embed číslují od 0
                vec.put(cfg.vector_bucket, cfg.sig_index, f"{did}#s{n}", s["_vec"],
                        dict(case_id=cid, document_id=did, page=s["page"],
                             label=d["label"], verified=d["verified"], model=seed.SIG_MODEL[0],
                             model_version=seed.SIG_MODEL[1]))
            s3.put_object(Bucket=cfg.bucket, Key=prefix + "signatures.json",
                          Body=json.dumps({"case_id": cid, "document_id": did, "signatures": sigs}).encode())
            row["signatures_s3_key"] = prefix + "signatures.json"
            common = dict(case_id=cid, document_id=did, label=d["label"], verified=d["verified"])
            for i, ((a, b), v) in enumerate(zip(d["_chunks"], d["_text_vecs"])):
                vec.put(cfg.vector_bucket, cfg.text_index, f"{did}#t{i}", v,
                        dict(common, page=a, page_from=a, page_to=b, chunk_id=f"c{i}",
                             model=seed.TEXT_MODEL[0], model_version=seed.TEXT_MODEL[1]))
            for p in range(1, d["page_count"] + 1):
                v = seed.embed("image", seed.IMAGE_DIM, d["label"], did, f"p{p}")
                vec.put(cfg.vector_bucket, cfg.image_index, f"{did}#p{p}", v,
                        dict(common, page=p, model=seed.IMAGE_MODEL[0], model_version=seed.IMAGE_MODEL[1]))
        _put(ddb, cfg.analysis_table, row)
        sha = hashlib.sha256(f"fixture:{cid}:{did}".encode()).hexdigest()  # v datech fixtur žádné duplicity nejsou
        add_document_hash(ddb, cfg, cid, did, sha, d["label"])

    clients = Clients(cfg, ddb=ddb, s3=s3, vectors=vec, key_provider=provider)
    index = {"cases": [
        {"case_id": cid, "client": c["client"], "documents": [
            {"document_id": did, "title": store.docs[(cid, did)]["title"], "label": store.docs[(cid, did)]["label"],
             "processing_status": store.docs[(cid, did)]["processing_status"],
             "verified": store.docs[(cid, did)]["verified"]} for did in c["docs"]]}
        for cid, c in store.cases.items()]}
    return Api(clients), index, clients
