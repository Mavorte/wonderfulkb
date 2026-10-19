"""Benchmark embedding modelů: leave-one-out nad vzorovými dokumenty (text i obraz).

Spuštění z `infra/validator-agent/` (potřebuje AWS přihlášení a `pypdfium2`, `pypdf`, `numpy`):

    WONDERFULKB_AWS_PROFILE=hackathon python -m embed.benchmark [--rpm 25] [--pages 2] [--out vysledky.json]

Co se měří (typ dokumentu = číselný prefix názvu souboru, např. `3_Form_Vinkulace_poj` → `3`;
prefix se používá jen k vyhodnocení, modely ho nevidí):
  * dokument → nejbližší jiný dokument (text: průměr vektorů prvních částí), jak často je stejného
    typu (top-1), MRR prvního souseda stejného typu a průměrný rozestup nejlepší shody vs. nejlepší
    neshody; zvlášť i jen napříč případy (Stavby Fišer ↔ Solom Rec);
  * totéž pro stránky (obraz; sousedé z téhož dokumentu se nepočítají);
  * dotaz větou → typ nejbližšího dokumentu (text);
  * latence jednoho volání a odhad ceny.
Vektory se cachují na disk (`--cache-dir`), opakované spuštění nevolá Bedrock.

Zdroje: textové výpisy `docs/vzorove-dokumenty/text/` (solom-rec, stavby-fiser) a PDF z S3
`cases/{solom-rec,stavby-fiser,unhappy_scenario}/original|…` (stránky vykresluje pypdfium2).
`unhappy_scenario` je upravená varianta případu Solom Rec, proto patří do jeho rodiny.
"""
from __future__ import annotations

import os
import argparse
import base64
import hashlib
import io
import json
import re
import statistics
import sys
import tempfile
import time
from pathlib import Path

import boto3
import numpy as np

from . import clients, embeddings
from .chunking import chunk_text

ROOT = Path(__file__).resolve().parents[3]
# Vzorové dokumenty z hackathonového balíku nejsou v repu: WONDERFULKB_SAMPLES_DIR ukazuje na složku `vzorove-dokumenty`.
TEXT_DIR = Path(os.environ.get("WONDERFULKB_SAMPLES_DIR", ROOT / "vzorove-dokumenty")) / "text"
RAW_BUCKET = "wonderfulkb-raw-document-storage"
S3_CASES = {  # případ -> prefix v bucketu
    "solom-rec": "cases/solom-rec/original/",
    "stavby-fiser": "cases/stavby-fiser/original/",
    "unhappy_scenario": "cases/unhappy_scenario/",
}
FAMILY = {"solom-rec": "solom", "unhappy_scenario": "solom", "stavby-fiser": "stavby"}
TEXT_CHUNKS_PER_DOC = 3

# Dotazy pro test vyhledávání větou: (dotaz, očekávaný typ)
QUERIES = [
    ("Vinkulace pojistného plnění ve prospěch věřitele", "3"),
    ("Zajišťovací převod vlastnického práva k předmětu financování", "2"),
    ("Ručitel se zavazuje uhradit dluh příjemce financování", "4"),
    ("Smlouva o úvěru mezi poskytovatelem a příjemcem financování", "0"),
    ("Protokol o předání a převzetí předmětu financování", "11"),
    ("Objednávka zařízení s technickou specifikací", "10"),
    ("Všeobecné obchodní podmínky ke smlouvě o úvěru", "01"),
    ("Dohoda o zaplacení kupní ceny dodavateli", "09"),
]

# Ceny USD za jednotku podle veřejných ceníků (agregátory, neověřeno u AWS, říjen 2026):
# Titan Text v2 0,02 $/1M tokenů; Titan Multimodal 0,00006 $/obrázek; Cohere v4 0,12 $/1M tokenů
# textu a 0,47 $/1M tokenů obrázku; Cohere multilingual v3 0,10 $/1M tokenů.
PRICE_PER_M_TOKENS = {"titan-text-v2": 0.02, "cohere-v4-text": 0.12, "cohere-v4-image": 0.47,
                      "cohere-multilingual-v3": 0.10}
PRICE_PER_TITAN_IMAGE = 0.00006

TEXT_CANDIDATES = ["titan-text-v2", "cohere-v4-text", "cohere-multilingual-v3"]
IMAGE_CANDIDATES = ["titan-image-v1", "cohere-v4-image"]
BEDROCK_ID = {"titan-text-v2": "amazon.titan-embed-text-v2:0", "titan-image-v1": "amazon.titan-embed-image-v1",
              "cohere-v4-text": "eu.cohere.embed-v4:0", "cohere-v4-image": "eu.cohere.embed-v4:0",
              "cohere-multilingual-v3": "cohere.embed-multilingual-v3"}


def doc_type(name: str) -> str | None:
    m = re.match(r"(\d+)_", name)
    return m.group(1) if m else None


class Embedder:
    """Volá Bedrock s limiterem, retry a diskovou cache; měří latenci a spotřebu tokenů."""

    def __init__(self, cache_dir: Path, rpm: int):
        self.cache_path = cache_dir / "cache.json"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = json.loads(self.cache_path.read_text()) if self.cache_path.exists() else {}
        self.limiter = clients.RateLimiter(limit=rpm)
        self.bedrock = clients.bedrock_client()
        self.calls = 0

    def _save(self) -> None:
        self.cache_path.write_text(json.dumps(self.cache))

    def _call(self, cand: str, body: dict) -> tuple[dict, float, int | None]:
        def go():
            t0 = time.perf_counter()
            r = self.bedrock.invoke_model(modelId=BEDROCK_ID[cand], body=json.dumps(body),
                                          contentType="application/json", accept="application/json")
            dt = time.perf_counter() - t0
            hdr = r["ResponseMetadata"]["HTTPHeaders"].get("x-amzn-bedrock-input-token-count")
            return json.loads(r["body"].read()), dt, int(hdr) if hdr else None
        self.calls += 1
        if self.calls % 10 == 0:
            print(f"  … {self.calls} volání Bedrocku", file=sys.stderr, flush=True)
        return clients.call_with_retry(go, limiter=self.limiter)

    def texts(self, cand: str, texts: list[str], input_type: str = "search_document") -> list[np.ndarray]:
        keys = [f"{cand}|{input_type}|{hashlib.sha1(t.encode()).hexdigest()}" for t in texts]
        missing = [i for i, k in enumerate(keys) if k not in self.cache]
        if cand == "titan-text-v2":
            for i in missing:
                out, dt, _ = self._call(cand, {"inputText": texts[i], "dimensions": 1024, "normalize": True})
                self.cache[keys[i]] = {"v": out["embedding"], "ms": dt * 1000, "tok": out["inputTextTokenCount"], "n": 1}
        elif missing:  # Cohere: jedno volání pro všechny chybějící (≤96)
            batch = [texts[i] for i in missing]
            if cand == "cohere-v4-text":
                body = embeddings._cohere_text_body(batch, input_type)
            else:  # multilingual v3: max 512 tokenů, delší se ořízne
                body = {"texts": batch, "input_type": input_type, "truncate": "END"}
            out, dt, tok = self._call(cand, body)
            vecs = embeddings._cohere_vectors(out)
            for j, i in enumerate(missing):
                self.cache[keys[i]] = {"v": vecs[j], "ms": dt * 1000, "tok": (tok or 0) / len(batch), "n": len(batch)}
        if missing:
            self._save()
        return [np.array(self.cache[k]["v"], dtype=np.float32) for k in keys]

    def image(self, cand: str, png: bytes) -> np.ndarray:
        prepared = embeddings.prepare_png(png)
        key = f"{cand}|image|{hashlib.sha1(prepared).hexdigest()}"
        if key not in self.cache:
            b64 = base64.b64encode(prepared).decode()
            if cand == "titan-image-v1":
                out, dt, tok = self._call(cand, {"inputImage": b64, "embeddingConfig": {"outputEmbeddingLength": 1024}})
                vec = out["embedding"]
            else:
                out, dt, tok = self._call(cand, {"input_type": "image", "images": [f"data:image/png;base64,{b64}"],
                                                 "embedding_types": ["float"], "output_dimension": 1024})
                vec = embeddings._cohere_vectors(out)[0]
            self.cache[key] = {"v": vec, "ms": dt * 1000, "tok": tok, "n": 1}
            self._save()
        return np.array(self.cache[key]["v"], dtype=np.float32)

    def stats(self, prefix: str) -> dict:
        rows = [v for k, v in self.cache.items() if k.startswith(prefix)]
        ms = [r["ms"] for r in rows]
        # latence se ukládá na volání; u dávek je to latence celé dávky
        calls = {(round(r["ms"], 3), r["n"]) for r in rows}
        lat = [m for m, _ in calls]
        toks = [r["tok"] for r in rows if r["tok"]]
        return {"calls": len(lat), "median_ms": round(statistics.median(lat)) if lat else None,
                "max_ms": round(max(lat)) if lat else None,
                "mean_tokens_per_item": round(statistics.mean(toks), 1) if toks else None}


# ---------- data ----------

def md_to_text(path: Path) -> str:
    md = path.read_text(encoding="utf-8", errors="replace")
    return "\f".join(re.findall(r"## Strana \d+.*?```text\n(.*?)\n```", md, flags=re.S))


def load_pdfs(tmp: Path, pages: int):
    """Stáhne PDF z S3 do nové prázdné složky; vrací [(případ, název, [PNG], text z textové vrstvy)]."""
    import pypdf
    import pypdfium2 as pdfium
    s3 = boto3.Session(profile_name=clients._session().profile_name, region_name=clients.REGION).client("s3")
    out = []
    for case, prefix in S3_CASES.items():
        for obj in s3.list_objects_v2(Bucket=RAW_BUCKET, Prefix=prefix).get("Contents", []):
            name = obj["Key"].rsplit("/", 1)[-1]
            if not name.lower().endswith(".pdf") or doc_type(name) is None:
                continue
            dest = tmp / case / name
            dest.parent.mkdir(exist_ok=True)
            s3.download_file(RAW_BUCKET, obj["Key"], str(dest))
            pdf = pdfium.PdfDocument(str(dest))
            pngs = []
            for i in range(min(pages, len(pdf))):
                buf = io.BytesIO()
                pdf[i].render(scale=1.2).to_pil().save(buf, "PNG")
                pngs.append(buf.getvalue())
            text = "\f".join((p.extract_text() or "") for p in pypdf.PdfReader(str(dest)).pages)
            out.append((case, name, pngs, text))
    return out


# ---------- metriky ----------

def evaluate(items: list[dict], cross_family: bool = False) -> dict:
    """items: {id, doc, type, family, vec(normalizovaný)}; leave-one-out nad ostatními dokumenty."""
    hits, rr, margins, per_type = [], [], [], {}
    for q in items:
        cands = [c for c in items if c["doc"] != q["doc"] and (not cross_family or c["family"] != q["family"])]
        if not any(c["type"] == q["type"] for c in cands):
            continue  # typ nemá protějšek, nelze ohodnotit
        sims = np.array([float(q["vec"] @ c["vec"]) for c in cands])
        order = np.argsort(-sims)
        ranked = [cands[i] for i in order]
        first = next(i for i, c in enumerate(ranked) if c["type"] == q["type"])
        best_same = max(s for s, c in zip(sims, cands) if c["type"] == q["type"])
        others = [s for s, c in zip(sims, cands) if c["type"] != q["type"]]
        hit = first == 0
        hits.append(hit)
        rr.append(1 / (first + 1))
        if others:
            margins.append(float(best_same - max(others)))
        per_type.setdefault(q["type"], []).append(hit)
    n = len(hits)
    return {"n": n, "top1": round(sum(hits) / n, 3) if n else None, "mrr": round(statistics.mean(rr), 3) if rr else None,
            "margin": round(statistics.mean(margins), 3) if margins else None,
            "per_type_top1": {t: f"{sum(v)}/{len(v)}" for t, v in sorted(per_type.items())}}


def norm(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def cost_text(cand: str, mean_tokens: float | None) -> float | None:
    if mean_tokens is None:
        return None
    key = {"titan-text-v2": "titan-text-v2", "cohere-v4-text": "cohere-v4-text",
           "cohere-multilingual-v3": "cohere-multilingual-v3"}[cand]
    return mean_tokens * PRICE_PER_M_TOKENS[key] / 1e6


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rpm", type=int, default=25, help="max volání Bedrocku za minutu (tým má 50)")
    ap.add_argument("--pages", type=int, default=2, help="kolik prvních stránek každého PDF do obrazového testu")
    ap.add_argument("--cache-dir", type=Path, default=Path(tempfile.gettempdir()) / "wonderfulkb-embed-benchmark")
    ap.add_argument("--models", nargs="+", default=TEXT_CANDIDATES + IMAGE_CANDIDATES,
                    choices=TEXT_CANDIDATES + IMAGE_CANDIDATES, help="které kandidáty změřit")
    ap.add_argument("--out", type=Path, default=None, help="uložit výsledky jako JSON")
    args = ap.parse_args()

    emb = Embedder(args.cache_dir, args.rpm)
    with tempfile.TemporaryDirectory(prefix="embed-bench-") as d:
        pdfs = load_pdfs(Path(d), args.pages)

    # --- korpus textů: md výpisy (solom-rec, stavby-fiser) + text z PDF (unhappy_scenario) ---
    docs: list[dict] = []
    for sub in ("solom-rec", "stavby-fiser"):
        for p in sorted((TEXT_DIR / sub).glob("*.md")):
            if doc_type(p.name):
                docs.append({"id": f"{sub}/{p.name}", "case": sub, "type": doc_type(p.name), "text": md_to_text(p)})
    for case, name, _, text in pdfs:
        if case == "unhappy_scenario":
            docs.append({"id": f"{case}/{name}", "case": case, "type": doc_type(name), "text": text})
    skipped = [d["id"] for d in docs if len(d["text"].strip()) < 50]
    docs = [d for d in docs if len(d["text"].strip()) >= 50]
    for d in docs:
        d["chunks"] = [c.text for c in chunk_text(d["text"])[:TEXT_CHUNKS_PER_DOC]]

    report: dict = {"corpus": {"text_docs": len(docs), "text_skipped_empty": skipped,
                               "pdf_pages": sum(len(p[2]) for p in pdfs), "pdfs": len(pdfs),
                               "types": sorted({d["type"] for d in docs})},
                    "text": {}, "image": {}}

    # --- text ---
    for cand in TEXT_CANDIDATES:
        if cand not in args.models:
            continue
        print(f"text: {cand}", file=sys.stderr, flush=True)
        try:
            report["text"][cand] = bench_text(emb, cand, docs)
        except Exception as exc:  # noqa: BLE001  model nedostupný (např. Marketplace) nezastaví ostatní
            report["text"][cand] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    for cand in IMAGE_CANDIDATES:
        if cand not in args.models:
            continue
        print(f"obraz: {cand}", file=sys.stderr, flush=True)
        try:
            report["image"][cand] = bench_image(emb, cand, pdfs)
        except Exception as exc:  # noqa: BLE001
            report["image"][cand] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}

    report["bedrock_calls_this_run"] = emb.calls
    text = json.dumps(report, ensure_ascii=False, indent=1)
    print(text)
    if args.out:
        args.out.write_text(text)
    return 0


def bench_text(emb: Embedder, cand: str, docs: list[dict]) -> dict:
    items = []
    for d in docs:
        vecs = emb.texts(cand, d["chunks"])
        items.append({"id": d["id"], "doc": d["id"], "type": d["type"], "family": FAMILY[d["case"]],
                      "vec": norm(np.mean([norm(v) for v in vecs], axis=0))})
    qvecs = emb.texts(cand, [q for q, _ in QUERIES], input_type="search_query")
    q_ok = []
    for (q, want), qv in zip(QUERIES, qvecs):
        sims = [(float(norm(qv) @ it["vec"]), it["type"]) for it in items]
        q_ok.append(max(sims)[1] == want)
    st = emb.stats(f"{cand}|search_document")
    cost = cost_text(cand, st["mean_tokens_per_item"])
    return {"all": evaluate(items), "cross_case": evaluate(items, cross_family=True),
            "query_top1": f"{sum(q_ok)}/{len(q_ok)}", "latency": st,
            "usd_per_1k_chunks": None if cost is None else round(cost * 1000, 5)}


def bench_image(emb: Embedder, cand: str, pdfs: list) -> dict:
    items = []
    for case, name, pngs, _ in pdfs:
        for n, png in enumerate(pngs, start=1):
            items.append({"id": f"{case}/{name}#p{n}", "doc": f"{case}/{name}", "type": doc_type(name),
                          "family": FAMILY[case], "vec": norm(emb.image(cand, png))})
    st = emb.stats(f"{cand}|image")
    if cand == "titan-image-v1":
        usd = PRICE_PER_TITAN_IMAGE * 1000
    else:
        usd = (st["mean_tokens_per_item"] or 0) * PRICE_PER_M_TOKENS["cohere-v4-image"] / 1e6 * 1000
    return {"all": evaluate(items), "cross_case": evaluate(items, cross_family=True),
            "latency": st, "usd_per_1k_images": round(usd, 4) if usd else None}


if __name__ == "__main__":
    sys.exit(main())
