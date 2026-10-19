"""Stažení PDF (nedůvěryhodná data) a stávajících nálezů do NOVÉ PRÁZDNÉ složky. Jen čtení z S3.

    python fetch.py DATA_DIR            # vytvoří DATA_DIR/generic, DATA_DIR/original, DATA_DIR/sigs, manifest.json

generic:  165 dokumentů z dataset/mapping.json, soubor `<case>__<document_id>.pdf`
original: PDF z cases/solom-rec/original/ a cases/stavby-fiser/original/, soubor `<case>__<název>.pdf`
sigs:     existující analysis/<document_id>/signatures.json (jen nálezy; výřezy ani stránky se nestahují)
"""
import hashlib
import json
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
from botocore.config import Config

BUCKET = "wonderfulkb-raw-document-storage"
DOC_NAMESPACE = uuid.UUID("5d3f0a52-7c1e-4a8b-9b36-6f1c2e0d7a11")      # stejný jako ingest
MAPPING = Path(__file__).resolve().parents[2] / "dataset" / "mapping.json"


def main(data_dir):
    root = Path(data_dir)
    if root.exists() and any(root.iterdir()):
        sys.exit("DATA_DIR musí být nová prázdná složka")
    for d in ("generic", "original", "sigs"):
        (root / d).mkdir(parents=True, exist_ok=True)
    s3 = boto3.Session(region_name="eu-central-1") \
        .client("s3", config=Config(retries={"max_attempts": 8, "mode": "standard"}))
    jobs, manifest = [], {"generic": [], "original": []}
    for c in json.load(open(MAPPING))["cases"]:
        for d in c["documents"]:
            fn = f"{c['case_id']}__{d['document_id']}.pdf"
            jobs.append((d["s3_key"], root / "generic" / fn, c["case_id"], d["document_id"]))
            manifest["generic"].append({"file": fn, "case_id": c["case_id"], "document_id": d["document_id"],
                                        "filename": d["filename"], "sha256": d["sha256"], "quality": d.get("quality")})
    for case in ("solom-rec", "stavby-fiser"):
        pag = s3.get_paginator("list_objects_v2")
        for page in pag.paginate(Bucket=BUCKET, Prefix=f"cases/{case}/original/"):
            for o in page.get("Contents", []):
                if o["Key"].lower().endswith(".pdf"):
                    name = o["Key"].rsplit("/", 1)[1]
                    fn = f"{case}__{name}"
                    jobs.append((o["Key"], root / "original" / fn, case, None))
                    manifest["original"].append({"file": fn, "case_id": case, "filename": name, "s3_key": o["Key"]})

    def get(j):
        key, dest, case, did = j
        s3.download_file(BUCKET, key, str(dest))
        return j

    with ThreadPoolExecutor(6) as ex:
        list(ex.map(get, jobs))
    for m in manifest["original"]:
        sha = hashlib.sha256((root / "original" / m["file"]).read_bytes()).hexdigest()
        m["sha256"] = sha
        m["document_id"] = str(uuid.uuid5(DOC_NAMESPACE, f"{m['case_id']}:{sha}"))
    n = 0
    for grp in ("generic", "original"):
        for m in manifest[grp]:
            k = f"cases/{m['case_id']}/analysis/{m['document_id']}/signatures.json"
            try:
                body = s3.get_object(Bucket=BUCKET, Key=k)["Body"].read()
            except s3.exceptions.NoSuchKey:
                continue
            (root / "sigs" / f"{m['case_id']}__{m['document_id']}.json").write_bytes(body)
            m["signatures_json"] = True
            n += 1
    json.dump(manifest, open(root / "manifest.json", "w"), ensure_ascii=False, indent=1)
    print(f"generic {len(manifest['generic'])}, original {len(manifest['original'])}, signatures.json {n}")


if __name__ == "__main__":
    main(sys.argv[1])
