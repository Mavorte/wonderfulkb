"""KROK 4: migrace stávajících dat do NOVÝCH klíčů. Nic nemaže, čitelné originály, stránky ani výřezy zůstávají.

    python -I migrate.py                                    # výchozí je --dry-run: jen vypíše, co by zapsal
    python -I migrate.py --only SYN-A01/34fcd896-... --apply   # skutečný zápis jednoho dokumentu
    python -I migrate.py --all --apply                      # všechny dokumenty (až po schválení reportu)

AWS přihlášení z prostředí (`eval "$(aws configure export-credentials --profile hackathon --format env)"`),
region eu-central-1. Co skript zapisuje (a nic jiného; objekt `Guard` nemá žádnou metodu na mazání):

 (a) cases/<case>/redacted/<document_id>.pdf   zamaskovaná kopie, metadata original-sha256 a original-size. Jen když
     prošel `verify_redacted` (výchozí přísně; `--tolerant` toleruje okrajové úlomky slov, viz verify_tolerant.py).
     Existující objekt se nepřepíše (If-None-Match).
 (b) analysis/<doc>/signatures/<sig>.png.enc a <sig>.preview.png pro každý čitelný <sig>.png. Round-trip: dešifrovat
     a porovnat se zdrojem; existující .enc se jen ověří. Čitelný <sig>.png zůstává.
 (c) analysis/<doc>/signatures.json: jen pole crop_s3_key (.png.enc), crop_encrypted: true, preview_s3_key u podpisů,
     které mají ověřený .png.enc. Zápis jen s overwrite=True (nová verze v zapnutém verzování), podmíněně na ETag, ať
     se nepřepíše souběžná změna jiné session (např. copy_suspicion).
 (d) vektory #p<n> v indexu wonderfulkb-image, které už existují: přepočet ze stránek vykreslených ze ZAMASKOVANÉHO
     PDF (110 dpi jako pipeline), stejný klíč i metadata; ~20 volání Bedrocku za minutu. Atribut original_sha256 do
     řádku wonderfulkb-uw-document-analysis (jen existující řádek, jen když chybí nebo je stejný).

Dokument, který neprojde ověřením, se přeskočí celý (včetně výřezů) a vypíše se. Žádné klíče, data ani obsah
podpisů se nevypisují.
"""
import argparse
import hashlib
import io
import json
import re
import sys
import time
import uuid
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

HERE = Path(__file__).resolve().parent
VA = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))          # privacy/
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(VA))                   # embed/
import pymupdf  # noqa: E402
from signature_privacy import (DecryptionError, KmsKeyProvider, SignatureContext, decrypt_image,  # noqa: E402
                               distorted_preview, encrypt_image, redact_pdf, verify_redacted)
from measure import local_findings, regions_of  # noqa: E402
from verify_tolerant import verify_tolerant  # noqa: E402

BUCKET = "wonderfulkb-raw-document-storage"
REGION = "eu-central-1"
DOC_NAMESPACE = uuid.UUID("5d3f0a52-7c1e-4a8b-9b36-6f1c2e0d7a11")      # stejný jako ingest
TAGGING = "project=wonderfulkb"
ROW_TABLE = "wonderfulkb-uw-document-analysis"
IMAGE_INDEX = "wonderfulkb-image"
VECTOR_BUCKET = "wonderfulkb-vectors"
PAGE_DPI = 110
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SIG_RE = re.compile(r"^sig_\d+$")
STAGES = ("redacted", "crops", "json", "vectors", "ddb")


class Guard:
    """Jediné S3 operace, které skript smí: čtení, výpis a zápis NOVÉHO objektu (nebo podmíněný zápis nad známým
    ETag). Mazání ani přepis bez podmínky tu není."""

    def __init__(self, client, bucket):
        self.c, self.bucket = client, bucket

    def get(self, key):
        r = self.c.get_object(Bucket=self.bucket, Key=key)
        return r["Body"].read(), r["ETag"]

    def head(self, key):
        try:
            return self.c.head_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return None
            raise

    def list(self, prefix):
        out = []
        for page in self.c.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            out += [o["Key"] for o in page.get("Contents", [])]
        return out

    def put_new(self, key, body, content_type, metadata=None):
        """Zapíše jen když objekt neexistuje (If-None-Match: *). Vrací False, když už existuje."""
        try:
            self.c.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type, IfNoneMatch="*",
                              Metadata={"project": "wonderfulkb", **(metadata or {})}, Tagging=TAGGING)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("PreconditionFailed", "ConditionalRequestConflict"):
                return False
            raise

    def put_if_match(self, key, body, etag, content_type):
        self.c.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type, IfMatch=etag,
                          Metadata={"project": "wonderfulkb"}, Tagging=TAGGING)


def update_signatures_json(g, key, updates, overwrite=False):
    """Do signatures.json zapíše JEN pole z `updates` ({signature_id: {pole: hodnota}}); ostatní beze změny.
    Bez `overwrite=True` odmítne zápis (bucket je verzovaný, zápis vytvoří novou verzi)."""
    if not overwrite:
        raise PermissionError("zápis do existujícího signatures.json vyžaduje overwrite=True")
    raw, etag = g.get(key)
    body = json.loads(raw)
    changed = 0
    for s in body.get("signatures", []):
        up = updates.get(s.get("signature_id"))
        if up and any(s.get(k) != v for k, v in up.items()):
            s.update(up)
            changed += 1
    if changed:
        g.put_if_match(key, json.dumps(body, ensure_ascii=False).encode(), etag, "application/json")
    return changed


def doc_inventory(g, only, limit):
    """{(case, document_id): {"original": key|None, "name": ..., "sigs": [id], "json": key|None}} z výpisu klíčů."""
    keys = g.list("cases/")
    docs = {}
    for k in keys:
        m = re.match(r"^cases/([^/]+)/analysis/([^/]+)/(signatures\.json|signatures/(sig_\d+)\.png)$", k)
        if m:
            d = docs.setdefault((m[1], m[2]), {"original": None, "sigs": [], "json": None})
            if m[3] == "signatures.json":
                d["json"] = k
            else:
                d["sigs"].append(m[4])
            continue
        m = re.match(r"^cases/([^/]+)/original/([^/]+\.pdf)$", k)
        if m:
            name = m[2]
            did = name[:-4] if UUID_RE.match(name[:-4]) else None
            docs.setdefault(("orig", m[1], name), {"case": m[1], "original": k, "doc_id": did, "sigs": [], "json": None})
    out = {}
    for key, d in docs.items():
        if key[0] == "orig":
            if d["doc_id"]:
                out.setdefault((d["case"], d["doc_id"]), {"original": None, "sigs": [], "json": None})["original"] = d["original"]
            else:   # klíč podle názvu souboru: document_id vznikne z SHA-256 obsahu (jako v ingestu)
                raw, _ = g.get(d["original"])
                did = str(uuid.uuid5(DOC_NAMESPACE, f"{d['case']}:{hashlib.sha256(raw).hexdigest()}"))
                out.setdefault((d["case"], did), {"original": None, "sigs": [], "json": None})["original"] = d["original"]
        else:
            out.setdefault(key, {"original": None, "sigs": [], "json": None}).update(
                {k: v for k, v in d.items() if k in ("sigs", "json")})
    sel = sorted(out.items())
    if only:
        sel = [(k, v) for k, v in sel if f"{k[0]}/{k[1]}" in only]
    return sel[:limit] if limit else sel


def log(msg):
    print(msg, flush=True)


def stage_redacted(g, args, case, did, d, st):
    """(a) Vrací (masked_bytes | None, ok). Při chybě ověření dokument přeskočí."""
    if not d["original"]:
        st["redacted"] = "bez originálu v original/ (nic k maskování)"
        return None, True
    data, _ = g.get(d["original"])
    sha = hashlib.sha256(data).hexdigest()
    st["original_sha256"] = sha
    st["original_size"] = len(data)
    findings = []
    if args.detect == "stored" and d["json"]:
        js = json.loads(g.get(d["json"])[0])
        findings = [{"page": s["page"], "bbox": s["bbox"]} for s in js.get("signatures", []) if s.get("bbox")]
    elif args.detect == "pipeline":
        findings = local_findings(data, [], "pipeline", args.cache)
    regions = regions_of(data, findings, args.zones)
    masked = redact_pdf(data, regions)
    problems = verify_redacted(data, masked, regions)
    if problems and args.tolerant:
        problems, _ = verify_tolerant(data, masked, regions)
        st["verify"] = "tolerant"
    st["findings"], st["regions"] = len(findings), len(regions)
    if problems:
        st["redacted"] = "PŘESKOČENO: verify_redacted: " + "; ".join(sorted(set(problems))[:3])
        return None, False
    key = f"cases/{case}/redacted/{did}.pdf"
    head = g.head(key)
    if head:
        meta = {k.replace("_", "-"): v for k, v in head.get("Metadata", {}).items()}
        same = meta.get("original-sha256") == sha
        st["redacted"] = f"existuje ({'stejný' if same else 'JINÝ'} original-sha256), nepřepisuji"
        return masked, True
    if args.apply:
        g.put_new(key, masked, "application/pdf", {"original-sha256": sha, "original-size": str(len(data))})
        st["redacted"] = f"zapsáno {key} ({len(masked)} B)"
    else:
        st["redacted"] = f"by zapsal {key} ({len(masked)} B, original-sha256, original-size {len(data)})"
    return masked, True


def stage_crops(g, args, provider, case, did, d, st):
    """(b) Vrací {signature_id: True} pro podpisy, jejichž .png.enc je ověřený."""
    verified = {}
    base = f"cases/{case}/analysis/{did}/signatures/"
    for sid in sorted(d["sigs"]):
        if not SIG_RE.match(sid):
            continue
        png, _ = g.get(base + sid + ".png")
        ctx = SignatureContext(case, did, sid)
        enc_key, prev_key = base + sid + ".png.enc", base + sid + ".preview.png"
        if g.head(enc_key):
            blob, _ = g.get(enc_key)
            try:
                ok = decrypt_image(blob, ctx, provider) == png if args.apply else None
            except DecryptionError:
                ok = False
            if ok is False:
                st.setdefault("crops_bad", []).append(sid)
                continue
            st.setdefault("crops", []).append(f"{sid}: .png.enc už existuje" + (", round-trip OK" if ok else ""))
            if args.apply and not g.head(prev_key):
                g.put_new(prev_key, distorted_preview(png), "image/png")
            verified[sid] = True
            continue
        if not args.apply:
            st.setdefault("crops", []).append(f"{sid}: by zapsal .png.enc + .preview.png (výřez {len(png)} B)")
            continue
        blob = encrypt_image(png, ctx, provider)
        if decrypt_image(blob, ctx, provider) != png:                    # round-trip před zápisem
            st.setdefault("crops_bad", []).append(sid)
            continue
        g.put_new(enc_key, blob, "application/octet-stream", {"enc": "wkbs1"})
        g.put_new(prev_key, distorted_preview(png), "image/png")
        back, _ = g.get(enc_key)                                         # round-trip i z uloženého objektu
        if decrypt_image(back, ctx, provider) != png:
            st.setdefault("crops_bad", []).append(sid)
            continue
        verified[sid] = True
        st.setdefault("crops", []).append(f"{sid}: zapsáno .png.enc + .preview.png, round-trip OK")
    return verified


def stage_json(g, args, case, did, d, verified, st):
    """(c) Jen pole crop_s3_key, crop_encrypted, preview_s3_key u ověřených výřezů."""
    if not d["json"] or not d["sigs"]:
        return
    base = f"cases/{case}/analysis/{did}/signatures/"
    ups = {sid: {"crop_s3_key": base + sid + ".png.enc", "crop_encrypted": True,
                 "preview_s3_key": base + sid + ".preview.png"}
           for sid in d["sigs"] if (verified.get(sid) or not args.apply and "crops_bad" not in st)}
    if not ups:
        return
    if not args.apply:
        st["json"] = f"by aktualizoval {len(ups)} podpisů v signatures.json (jen 3 pole)"
        return
    st["json"] = f"aktualizováno podpisů: {update_signatures_json(g, d['json'], ups, overwrite=True)}"


def render_pages(masked, pages=None):
    doc = pymupdf.open(stream=masked, filetype="pdf")
    try:
        for i in range(doc.page_count):
            if pages is None or (i + 1) in pages:
                yield i + 1, doc[i].get_pixmap(dpi=PAGE_DPI, alpha=False).tobytes("png")
    finally:
        doc.close()


def stage_vectors(args, s3v, did, case, masked, st, state):
    """(d) Přepočet existujících #p<n> ze zamaskovaných stránek (stejný klíč, stejná metadata)."""
    n_pages = pymupdf.open(stream=masked, filetype="pdf").page_count
    keys = [f"{did}#p{n}" for n in range(1, n_pages + 1)]
    got = s3v.get_vectors(vectorBucketName=VECTOR_BUCKET, indexName=IMAGE_INDEX, keys=keys, returnMetadata=True)["vectors"]
    have = {v["key"]: v.get("metadata", {}) for v in got}
    if not have:
        st["vectors"] = "žádné existující #p<n>"
        return
    if not args.apply:
        st["vectors"] = f"by přepočítal {len(have)} vektorů: " + ", ".join(sorted(k.split('#')[1] for k in have))
        return
    from embed import embeddings
    done = []
    for n, png in render_pages(masked, {int(k.split("#p")[1]) for k in have}):
        wait = state["last"] + 60.0 / args.rpm - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        vec = embeddings.embed_image(png)
        state["last"] = time.monotonic()
        key = f"{did}#p{n}"
        s3v.put_vectors(vectorBucketName=VECTOR_BUCKET, indexName=IMAGE_INDEX,
                        vectors=[{"key": key, "data": {"float32": [float(x) for x in vec]}, "metadata": have[key]}])
        done.append(f"p{n}")
    st["vectors"] = "přepočteno " + ", ".join(done)


def stage_ddb(args, ddb, case, did, sha, st):
    if not sha:
        return
    t = ddb.Table(ROW_TABLE)
    item = t.get_item(Key={"case_id": case, "document_id": did}, ProjectionExpression="original_sha256").get("Item")
    if item is None:
        st["ddb"] = "řádek v tabulce neexistuje, nic nezapisuji"
        return
    cur = item.get("original_sha256")
    if cur == sha:
        st["ddb"] = "original_sha256 už je nastaven"
        return
    if cur:
        st["ddb"] = "JINÝ original_sha256 v řádku, nepřepisuji"
        return
    if args.apply:
        t.update_item(Key={"case_id": case, "document_id": did}, UpdateExpression="SET original_sha256 = :s",
                      ConditionExpression="attribute_exists(case_id) AND attribute_not_exists(original_sha256)",
                      ExpressionAttributeValues={":s": sha})
        st["ddb"] = "original_sha256 zapsán"
    else:
        st["ddb"] = "by zapsal original_sha256"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="skutečný zápis (bez něj je to --dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="výchozí; jen vypíše plán")
    ap.add_argument("--only", action="append", default=[], help="case/document_id (lze opakovat)")
    ap.add_argument("--all", action="store_true", help="všechny dokumenty (nutné pro --apply bez --only)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--stages", default=",".join(STAGES))
    ap.add_argument("--detect", choices=["pipeline", "stored", "none"], default="pipeline",
                    help="nálezy pro maskování: výchozí řetěz pipeline (Textract, cache), uložené signatures.json, žádné")
    ap.add_argument("--zones", choices=["v1", "v2"], default="v2")
    ap.add_argument("--cache", help="cache odpovědí Textractu")
    ap.add_argument("--tolerant", action="store_true", help="tolerovat okrajové úlomky slov při ověření")
    ap.add_argument("--rpm", type=float, default=20.0, help="limit volání Bedrocku za minutu")
    ap.add_argument("--report", help="uloží JSON se stavem po dokumentech")
    args = ap.parse_args()
    if args.apply and args.dry_run:
        ap.error("--apply a --dry-run se vylučují")
    if args.apply and not (args.only or args.all):
        ap.error("--apply vyžaduje --only (jeden dokument) nebo --all")
    stages = set(args.stages.split(","))
    cfg = Config(retries={"max_attempts": 8, "mode": "adaptive"})
    sess = boto3.Session(region_name=REGION)
    g = Guard(sess.client("s3", config=cfg), BUCKET)
    s3v = sess.client("s3vectors", config=cfg)
    ddb = sess.resource("dynamodb", config=cfg)
    provider = KmsKeyProvider() if args.apply and "crops" in stages else None
    log(("ZÁPIS" if args.apply else "DRY-RUN") + f" stages={sorted(stages)} zones={args.zones} detect={args.detect}")
    inv = doc_inventory(g, set(args.only), args.limit)
    log(f"dokumentů: {len(inv)}")
    state = {"last": 0.0}
    report, skipped = [], []
    for (case, did), d in inv:
        st = {"case_id": case, "document_id": did}
        try:
            masked, ok = (None, True)
            if "redacted" in stages or "vectors" in stages:
                masked, ok = stage_redacted(g, args, case, did, d, st) if "redacted" in stages else (None, True)
            if not ok:
                skipped.append((case, did, st["redacted"]))
            else:
                verified = {}
                if "crops" in stages and d["sigs"]:
                    verified = stage_crops(g, args, provider, case, did, d, st)
                if "json" in stages:
                    stage_json(g, args, case, did, d, verified, st)
                if "vectors" in stages and masked is not None:
                    stage_vectors(args, s3v, did, case, masked, st, state)
                if "ddb" in stages:
                    stage_ddb(args, ddb, case, did, st.get("original_sha256"), st)
        except Exception as e:  # noqa: BLE001
            st["error"] = f"{type(e).__name__}: {str(e)[:160]}"
        report.append(st)
        log(f"{case}/{did}: " + "; ".join(f"{k}={v}" for k, v in st.items()
                                           if k not in ("case_id", "document_id", "original_sha256", "crops")) +
            (f" crops={len(st['crops'])}" if "crops" in st else ""))
    log(f"\npřeskočeno (neprošlo ověřením): {len(skipped)}")
    for c, i, why in skipped:
        log(f"  {c}/{i}: {why}")
    errs = [s for s in report if "error" in s]
    log(f"chyby: {len(errs)}")
    if args.report:
        json.dump(report, open(args.report, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
