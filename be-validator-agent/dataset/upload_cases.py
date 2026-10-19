#!/usr/bin/env python3
"""Nahraje primární PDF z balíku 20 syntetických případů přes ingest API a zapíše mapping.json.

Idempotentní: stejný obsah ve stejném case vrací `duplicate: true` a stejné `document_id`.
Case se NEZAKLÁDÁ (SYN-A01..SYN-C10 už v `wonderfulkb-uw-cases` jsou); ingest vrátí 404, kdyby
nějaký chyběl. Do DynamoDB tabulek se nezapisuje, jen volá ingest API.

Spuštění (balík rozbalený do NOVÉ prázdné složky, viz README.md):
    python3 -I upload_cases.py --pkg <rozbaleny>/synteticke_dokumenty_20_pripadu [--case SYN-A01 ...] [--dry-run]

Klíč: proměnná prostředí INGEST_API_KEY, jinak Secrets Manager `wonderfulkb/ingest-api-key`
(profil `hackathon`). Klíč se nikam nevypisuje; curl ho dostane přes stdin (-K -), ne v argumentech.
"""
import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

INGEST_URL = os.environ.get("INGEST_URL", "<INGEST_API_BASE_URL>")
BUCKET = "wonderfulkb-raw-document-storage"
UPLOADED_BY = "dataset-loader@wonderfulkb"
HERE = Path(__file__).resolve().parent

FAMILY_SCENARIO = {
    "A": "demolition-shears (varianta {variant}, předloha Solom Rec)",
    "B": "tandem-roller (varianta {variant}, předloha Stavby Fišer)",
}


def get_key():
    key = os.environ.get("INGEST_API_KEY")
    if key:
        return key
    out = subprocess.run(
        ["aws", "--profile", "hackathon", "--region", "eu-central-1", "secretsmanager",
         "get-secret-value", "--secret-id", "wonderfulkb/ingest-api-key",
         "--query", "SecretString", "--output", "text"],
        check=True, capture_output=True, text=True)
    return out.stdout.strip()


def curl(args, key, expect_json=True):
    """curl s klíčem přes stdin config; vrací (http_status, tělo)."""
    cfg = f'header = "x-api-key: {key}"\n'
    r = subprocess.run(["curl", "-sS", "-K", "-", "-w", "\n%{http_code}", *args],
                       input=cfg, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"curl selhal: {r.stderr.strip()[:300]}")
    body, _, status = r.stdout.rpartition("\n")
    return int(status), (json.loads(body) if expect_json and body else body)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cases(pkg):
    """Případy z katalog.csv + cases.json obou sad; PDF jen z primárních složek `dokumenty/`."""
    cat = {}
    with open(pkg / "katalog.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cat[row["case_id"]] = row
    meta = {}
    for sub in ("synteticke_dokumenty", "synteticke_dokumenty_rozsireni"):
        for c in json.load(open(pkg / sub / "data" / "cases.json", encoding="utf-8")):
            meta[c["id"]] = c
    manifest = {m["path"]: m for m in json.load(open(pkg / "manifest.json", encoding="utf-8"))}
    cases = []
    for case_id, row in cat.items():
        m = meta[case_id]
        if m.get("family"):
            scenario = FAMILY_SCENARIO[m["family"]].format(variant=m["variant"])
        else:
            scenario = f"{m['category']} ({m['sector']}, {m['state']}, rozšiřující sada)"
        folder = Path(row["folder"])
        files = sorted((pkg / folder).glob("*.pdf"))
        docs = []
        for p in files:
            man = manifest.get(f"{folder}/{p.name}")
            docs.append({"path": p, "filename": p.name, "sha256": sha256_of(p),
                         "manifest_sha256": man["sha256"] if man else None,
                         "quality": man.get("quality") if man else None})
        cases.append({"case_id": case_id, "scenario": scenario, "source_folder": row["folder"],
                      "asset": row["asset"], "split": row["split"],
                      "expected_documents": int(row["documents"]), "docs": docs})
    return sorted(cases, key=lambda c: c["case_id"])


def upload_case(case, key, uploaded_by):
    args = ["-X", "POST", f"{INGEST_URL}/cases/{case['case_id']}/documents", "-F", f"uploaded_by={uploaded_by}"]
    for d in case["docs"]:
        args += ["-F", f"files=@{d['path']};type=application/pdf;filename={d['filename']}"]
    return curl(args, key)


def list_case(case_id, key):
    docs, token = [], None
    while True:
        q = "limit=100" + (f"&next_token={token}" if token else "")
        status, body = curl([f"{INGEST_URL}/cases/{case_id}/documents?{q}"], key)
        if status != 200:
            raise RuntimeError(f"výpis {case_id}: HTTP {status} {body}")
        docs += body["documents"]
        token = body.get("next_token")
        if not token:
            return docs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", required=True, type=Path, help="rozbalená složka synteticke_dokumenty_20_pripadu")
    ap.add_argument("--case", action="append", help="jen tyto case_id (lze opakovat)")
    ap.add_argument("--dry-run", action="store_true", help="jen spočítat a vypsat, nic nenahrávat")
    ap.add_argument("--out", type=Path, default=HERE / "mapping.json")
    ap.add_argument("--uploaded-by", default=UPLOADED_BY)
    a = ap.parse_args()

    cases = load_cases(a.pkg)
    if a.case:
        cases = [c for c in cases if c["case_id"] in set(a.case)]
    problems = []
    for c in cases:
        if len(c["docs"]) != c["expected_documents"]:
            problems.append(f"{c['case_id']}: {len(c['docs'])} PDF, katalog říká {c['expected_documents']}")
        for d in c["docs"]:
            if d["manifest_sha256"] and d["manifest_sha256"] != d["sha256"]:
                problems.append(f"{c['case_id']}/{d['filename']}: sha256 se liší od manifest.json")
    if problems:
        sys.exit("Kontrola balíku selhala:\n  " + "\n  ".join(problems))
    if a.dry_run:
        for c in cases:
            print(c["case_id"], len(c["docs"]), "PDF,", c["scenario"])
        return

    key = get_key()
    # mapping.json se doplňuje, ať jde spouštět po částech
    existing = {}
    if a.out.exists():
        existing = {m["case_id"]: m for m in json.load(open(a.out, encoding="utf-8"))["cases"]}
    failed = []
    for c in cases:
        status, body = upload_case(c, key, a.uploaded_by)
        if status != 201:
            print(f"{c['case_id']}: CHYBA HTTP {status} {body}", file=sys.stderr)
            failed.append(c["case_id"])
            continue
        by_name = {d["filename"]: d for d in body["documents"]}
        docs = []
        for d in c["docs"]:
            r = by_name[d["filename"]]
            docs.append({"document_id": r["document_id"], "filename": d["filename"],
                         "s3_key": f"cases/{c['case_id']}/original/{r['document_id']}.pdf",
                         "sha256": d["sha256"], "group": "generic", "quality": d["quality"],
                         "size_bytes": r["size_bytes"]})
        listed = list_case(c["case_id"], key)
        ok = (sorted(x["document_id"] for x in listed) == sorted(x["document_id"] for x in docs))
        dup = sum(1 for r in body["documents"] if r["duplicate"])
        print(f"{c['case_id']}: nahráno {len(docs) - dup}, duplicit {dup}, výpis {len(listed)} "
              f"{'OK' if ok else 'NESEDÍ'}")
        if not ok:
            failed.append(c["case_id"])
        existing[c["case_id"]] = {"case_id": c["case_id"], "scenario": c["scenario"],
                                  "source_folder": c["source_folder"], "asset": c["asset"],
                                  "split": c["split"], "documents": docs}
    out = {"ingest_url": INGEST_URL, "bucket": BUCKET, "cases": [existing[k] for k in sorted(existing)]}
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"zapsáno {a.out} ({len(out['cases'])} případů)")
    if failed:
        sys.exit(f"selhalo: {', '.join(failed)}")


if __name__ == "__main__":
    main()
