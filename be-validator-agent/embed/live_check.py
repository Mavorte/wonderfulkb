"""Živé ověření proti AWS (eu-central-1, profil z WONDERFULKB_AWS_PROFILE, např. `hackathon`).

Spuštění z `infra/validator-agent/`:  python -m embed.live_check
Zapíše pár testovacích vektorů (case_id `wonderfulkb-test-embed-*`), dotáže se, změří zpoždění
zápis→dotaz a nakonec smaže jen klíče, které si sám zapsal. Spotřeba Bedrocku: ~15 volání.
"""
from __future__ import annotations

import os
import json
import re
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import boto3
import pypdfium2 as pdfium

from . import clients, embeddings, vectors
from . import chunk_text, embed_text, nearest_verified, set_verified, write_document_vectors

ROOT = Path(__file__).resolve().parents[3]
# Vzorové dokumenty z hackathonového balíku nejsou v repu: WONDERFULKB_SAMPLES_DIR ukazuje na složku `vzorove-dokumenty`.
TEXT_DIR = Path(os.environ.get("WONDERFULKB_SAMPLES_DIR", ROOT / "vzorove-dokumenty")) / "text"
RAW_BUCKET = "wonderfulkb-raw-document-storage"
RUN = uuid.uuid4().hex[:8]


def md_to_text(path: Path) -> str:
    """Vzorové .md mají `## Strana N` + blok ```text; vrátí text se stranami oddělenými \\f."""
    md = path.read_text(encoding="utf-8", errors="replace")
    pages = re.findall(r"## Strana \d+.*?```text\n(.*?)\n```", md, flags=re.S)
    return "\f".join(pages)


def find(sub: str, name: str) -> Path:
    return next(p for p in (TEXT_DIR / sub).glob("*.md") if p.name.startswith(name))


def render_pdf(sub: str, prefix: str) -> list[bytes]:
    """Stáhne PDF z S3 do nové prázdné složky a vykreslí stránky přes pypdfium2."""
    import io
    keys = boto3.Session(profile_name=clients._session().profile_name, region_name=clients.REGION) \
        .client("s3").list_objects_v2(Bucket=RAW_BUCKET, Prefix=f"cases/{sub}/original/{prefix}")["Contents"]
    key = keys[0]["Key"]
    with tempfile.TemporaryDirectory(prefix="embed-live-") as d:
        dest = Path(d) / "doc.pdf"
        boto3.Session(profile_name=clients._session().profile_name, region_name=clients.REGION) \
            .client("s3").download_file(RAW_BUCKET, key, str(dest))
        pdf = pdfium.PdfDocument(str(dest))
        out = []
        for page in pdf:
            buf = io.BytesIO()
            page.render(scale=1.2).to_pil().save(buf, "PNG")
            out.append(buf.getvalue())
        return out


def wait_visible(vec, index, case_id, want_key, timeout=60.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        res = nearest_verified(vec, index, 10, case_id=case_id)
        if any(r["key"] == want_key for r in res):
            return time.monotonic() - t0
        time.sleep(0.25)
    return None


def main() -> int:
    report: dict = {"run": RUN}
    written: dict[str, list[str]] = {"text": [], "image": [], "signatures": []}
    s3v = clients.s3vectors_client()
    try:
        # 1) kalibrace odhadu tokenů (inputTextTokenCount) na reálném textu
        sample = chunk_text(md_to_text(find("solom-rec", "4_Form_Ru")))[0].text
        raw = embeddings._invoke(embeddings.TEXT_MODEL, {"inputText": sample, "dimensions": 1024, "normalize": True})
        report["calibration"] = {"chars": len(sample), "tokens": raw["inputTextTokenCount"],
                                 "chars_per_token": round(len(sample) / raw["inputTextTokenCount"], 2)}

        # 2) tři textové dokumenty ve dvou případech; stejný typ (vinkulace) v obou případech
        docs = {
            "a": ("solom", f"wonderfulkb-test-embed-{RUN}-X", md_to_text(find("solom-rec", "3_Form_Vink")), "vinkulace_pojisteni"),
            "b": ("fiser", f"wonderfulkb-test-embed-{RUN}-Y", md_to_text(find("stavby-fiser", "3_Form_Vink")), "vinkulace_pojisteni"),
            "c": ("ruceni", f"wonderfulkb-test-embed-{RUN}-Y", md_to_text(find("solom-rec", "4_Form_Ru")), "ruceni"),
        }
        pngs = {"a": render_pdf("solom-rec", "3_Form_Vink"), "b": render_pdf("stavby-fiser", "3_Form_Vink"), "c": []}
        report["pdf_pages"] = {k: len(v) for k, v in pngs.items()}
        ids = {k: f"test-embed-{RUN}-{k}" for k in docs}

        write_ms = {}
        for k, (_, case, text, label) in docs.items():
            t0 = time.monotonic()
            res = write_document_vectors(case, ids[k], text, pngs[k], label=label)
            write_ms[k] = round((time.monotonic() - t0) * 1000)
            written["text"] += res["text"]
            written["image"] += res["image"]
        report["written"] = {i: len(k) for i, k in written.items()}
        report["write_ms_incl_embedding"] = write_ms

        # 3) zpoždění zápis → dotaz: hned po put_vectors vektor znovu přepsat (set_verified) a měřit viditelnost
        a0 = f"{ids['a']}#t0"
        vec_a = s3v.get_vectors(vectorBucketName=clients.VECTOR_BUCKET, indexName="wonderfulkb-text",
                                keys=[a0], returnData=True)["vectors"][0]["data"]["float32"]
        assert nearest_verified(vec_a, "text", 5, case_id=docs["a"][1]) == [], "před ověřením nesmí nic vrátit"
        lat = []
        for k in ("a", "b"):
            keys = [x for x in written["text"] if x.startswith(ids[k] + "#")]
            t0 = time.monotonic()
            set_verified("text", keys)
            probe_key = keys[0]
            probe_vec = s3v.get_vectors(vectorBucketName=clients.VECTOR_BUCKET, indexName="wonderfulkb-text",
                                        keys=[probe_key], returnData=True)["vectors"][0]["data"]["float32"]
            seen = wait_visible(probe_vec, "text", docs[k][1], probe_key)
            lat.append(round((time.monotonic() - t0) * 1000))
            report.setdefault("verified_visible_after_s", {})[k] = None if seen is None else round(seen, 3)
        report["write_to_query_total_ms"] = lat

        # 4) dotazy
        res_all = nearest_verified(vec_a, "text", 10)
        report["text_query_all_cases"] = [(r["key"].split("#")[0][-1], r["key"].split("#")[1], round(r["score"], 4), r["label"]) for r in res_all]
        res_x = nearest_verified(vec_a, "text", 10, case_id=docs["a"][1])
        report["text_query_case_X_only"] = [(r["key"].split("#")[0][-1], round(r["score"], 4)) for r in res_x]
        res_ex = nearest_verified(vec_a, "text", 10, exclude_document_id=ids["a"])
        report["text_query_excluding_a"] = [(r["key"].split("#")[0][-1], r["key"].split("#")[1], round(r["score"], 4)) for r in res_ex]
        assert all(not r["key"].startswith(ids["c"]) for r in res_all), "c není ověřený"
        assert res_all[0]["key"] == a0 and res_all[0]["score"] > 0.99
        assert {r["document_id"] for r in res_x} == {ids["a"]}
        assert res_ex[0]["document_id"] == ids["b"], "nejbližší ověřený dokument jiného případu je vinkulace b"

        # dotaz větou: najde ověřenou vinkulaci
        q = embed_text("Vinkulace pojistného plnění ve prospěch věřitele")
        report["text_query_by_sentence"] = [(r["key"].split("#")[0][-1], round(r["score"], 4)) for r in nearest_verified(q, "text", 5)]

        # 5) obraz: stránka 1 dokumentu a vs. stránky b; jen ověřené
        img_keys = {k: [x for x in written["image"] if x.startswith(ids[k] + "#")] for k in ("a", "b")}
        for k in ("a", "b"):
            set_verified("image", img_keys[k])
        vec_p = s3v.get_vectors(vectorBucketName=clients.VECTOR_BUCKET, indexName="wonderfulkb-image",
                                keys=[f"{ids['a']}#p1"], returnData=True)["vectors"][0]["data"]["float32"]
        res_i = nearest_verified(vec_p, "image", 10, exclude_document_id=ids["a"])
        report["image_query_page1_a_vs_others"] = [(r["key"].split("#")[0][-1], r["key"].split("#")[1], round(r["score"], 4)) for r in res_i]
        res_self = nearest_verified(vec_p, "image", 1)
        assert res_self[0]["key"] == f"{ids['a']}#p1" and res_self[0]["score"] > 0.99

        # 6) idempotence: zápis znovu nezvýší počet klíčů
        before = len(written["text"])
        again = write_document_vectors(docs["c"][1], ids["c"], docs["c"][2], [], label="ruceni")
        report["idempotent_same_keys"] = again["text"] == [x for x in written["text"] if x.startswith(ids["c"])]
        report["ok"] = True
    except Exception as exc:  # noqa: BLE001
        report["ok"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        # úklid: jen klíče, které jsme zapsali
        for index, keys in written.items():
            if keys:
                vectors.delete_vectors(index, keys, s3v=s3v)
        left = {}
        for index, keys in written.items():
            if keys:
                left[index] = len(s3v.get_vectors(vectorBucketName=clients.VECTOR_BUCKET,
                                                   indexName=vectors.index_name(index), keys=keys[:100])["vectors"])
        report["left_after_cleanup"] = left
        print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
