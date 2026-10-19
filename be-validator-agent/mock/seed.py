"""Syntetická data pro mock Validator Agent API.

Texty dokumentů jsou skutečné výpisy z docs/vzorove-dokumenty/text (dva případy KB).
Vektory, podpisy a štítky jsou vygenerované deterministicky (stejný vstup = stejný výstup).
"""
import hashlib
import math
import os
import random
import re
import uuid
import zlib
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
# Vzorové dokumenty z hackathonového balíku nejsou v repu: WONDERFULKB_SAMPLES_DIR ukazuje na složku `vzorove-dokumenty`.
TEXT_DIR = os.environ.get(
    "TEXT_DIR", os.path.join(os.environ.get("WONDERFULKB_SAMPLES_DIR", "vzorove-dokumenty"), "text")
)
NS = uuid.UUID("5b1c0f3e-8d6a-4c7e-9a52-77aa00bb11cc")

TEXT_DIM = IMAGE_DIM = SIG_DIM = 1024  # dohodnuto s hlavní session: všechny indexy mají 1024 dimenzí
TEXT_MODEL = ("amazon.titan-embed-text-v2:0", "v2")
IMAGE_MODEL = ("cohere.embed-v4:0", "v4")
SIG_MODEL = ("wonderfulkb-signature-mock", "v0")

# Prefix názvu souboru -> štítek (taxonomy.yaml v repu není, štítky jsou odvozené ze skupin).
LABELS = [
    ("01_", "vop"),
    ("09_", "dohoda_o_zaplaceni_kupni_ceny"),
    ("0_", "smlouva_o_uveru"),
    ("2_", "zajistovaci_prevod_vlastnickeho_prava"),
    ("3_", "vinkulace_pojisteni"),
    ("4_", "ruceni"),
    ("10_", "objednavka"),
    ("11_", "predavaci_protokol"),
    ("14_", "uhrada_kupni_ceny"),
    ("99_", "data_ze_systemu"),
]
LABEL_NAMES = {
    "smlouva_o_uveru": "Smlouva o úvěru",
    "vop": "Všeobecné obchodní podmínky",
    "dohoda_o_zaplaceni_kupni_ceny": "Dohoda o zaplacení kupní ceny",
    "zajistovaci_prevod_vlastnickeho_prava": "Smlouva o zajišťovacím převodu vlastnického práva",
    "vinkulace_pojisteni": "Vinkulace pojistného plnění",
    "ruceni": "Smlouva o ručení",
    "objednavka": "Objednávka s technickou specifikací",
    "predavaci_protokol": "Protokol o předání a převzetí / potvrzení o přechodu vlastnictví",
    "uhrada_kupni_ceny": "Oznámení o provedení příkazu k úhradě kupní ceny",
    "data_ze_systemu": "Data ze systému (Kontrola smlouvy)",
}
# role podpisů podle typu dokumentu: (role, strana: "last"/číslo, bbox, role_evidence)
SIGNING = {
    "smlouva_o_uveru": [("provider", "Za poskytovatele"), ("borrower", "Za příjemce")],
    "zajistovaci_prevod_vlastnickeho_prava": [("borrower", "Za převodce"), ("provider", "Za nabyvatele")],
    "vinkulace_pojisteni": [("insurer", "Za pojistitele"), ("borrower", "Za pojistníka")],
    "ruceni": [("provider", "Za věřitele"), ("guarantor", "Za ručitele")],
    "dohoda_o_zaplaceni_kupni_ceny": [("buyer", "Za kupujícího"), ("supplier", "Za prodávajícího")],
    "predavaci_protokol": [("supplier", "Za dodavatele"), ("buyer", "Za odběratele")],
    "objednavka": [("buyer", "Za objednatele")],
    "vop": [("borrower", "Za příjemce")],
}

# (složka, soubor, popis kdo/co, verified, status override, pages_failed override)
CASES = {
    "stavby-fiser": {
        "client": "Stavby Fišer a.s.",
        "docs": {
            "0_F_Smlouva.pdf": dict(verified=True),
            "2_Form_Zajišťovací převod vl. práva.pdf": dict(verified=True),
            "3_Form_Vinkulace_poj.pdf": {},
            "10_Podklady k výplatě _Objednávka + TS.pdf": dict(partial=[4, 5, 6, 7, 8, 9]),
            "11_Protokol_Potvrzení o přechodu vlastnictví.pdf": dict(
                copy_from=("0_F_Smlouva.pdf", "borrower")
            ),
            "14_Podklady k výplatě_Úhrada KC.pdf": {},
            "99_KK_systAPI.pdf": dict(verified=True),
        },
    },
    "solom-rec": {
        "client": "Solom Rec s.r.o.",
        "docs": {
            "0_Form_Smlouva.pdf": dict(verified=True),
            "01_Form_VOP.pdf": {},
            "09_Form_Dohoda o zaplacení kupní ceny.pdf": {},
            "2_Form_Zajišťovací převod vl. práva.pdf": dict(verified=True),
            "3_Form_Vinkulace_poj.pdf": {},
            "4_Form_Ručení.pdf": {},
            "10_Podklady k výlatě_objednávka.pdf": dict(no_confidence=True),
            "11_Podklady k výplatě _ Protokol.pdf": dict(status="processing"),
            "99_KK_systAPI.pdf": dict(verified=True),
        },
    },
}
# Referenční korpus ověřených dokumentů pro `neighbors` (syntetické, krátké).
REF_CASE = "ref-corpus"
REF_COMPANIES = ["Alfa Stroje a.s.", "Beta Logistika s.r.o.", "Gama Agro s.r.o."]


def case_uuid(slug):
    return str(uuid.uuid5(NS, "case/" + slug))


def doc_uuid(slug, name):
    return str(uuid.uuid5(NS, f"doc/{slug}/{name}"))


def label_of(filename):
    for prefix, label in LABELS:
        if filename.startswith(prefix):
            return label
    return "ostatni"


def read_pages(slug, filename):
    """Vrátí seznam textů stran z markdown výpisu (prázdný řetězec = sken bez textu)."""
    path = os.path.join(TEXT_DIR, slug, os.path.splitext(filename)[0] + ".md")
    try:
        src = open(path, encoding="utf-8").read()
    except OSError:
        return None
    parts = re.split(r"^## Strana \d+\s*$", src, flags=re.M)[1:]
    pages = []
    for p in parts:
        m = re.search(r"```text\n(.*?)\n```", p, flags=re.S)
        pages.append(m.group(1).strip() if m else "")
    return pages


# ---- vektory -------------------------------------------------------------

def _rng(key):
    return random.Random(int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big"))


def _gauss(key, dim):
    r = _rng(key)
    return [r.gauss(0, 1) for _ in range(dim)]


def _norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _mix(parts):
    dim = len(parts[0][1])
    out = [0.0] * dim
    for w, v in parts:
        for i in range(dim):
            out[i] += w * v[i]
    return _norm(out)


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


def embed(kind, dim, label, doc_key, item_key):
    """Vektory stejného štítku jsou si podobné (~0,8), různé štítky téměř kolmé."""
    return _mix([
        (0.9, _norm(_gauss(f"{kind}/label/{label}", dim))),
        (0.3, _norm(_gauss(f"{kind}/doc/{doc_key}", dim))),
        (0.3, _norm(_gauss(f"{kind}/item/{doc_key}/{item_key}", dim))),
    ])


def _vec_meta(model, dim, values, with_values):
    d = {"model": model[0], "model_version": model[1], "dimension": dim}
    if with_values:
        d["values"] = [round(x, 6) for x in values]
    return d


# ---- PNG výřez podpisu (jen stdlib) -------------------------------------

def signature_png(seed, w=240, h=80):
    r = _rng("png/" + seed)
    img = [[255] * w for _ in range(h)]
    x, y = 12, h // 2
    for _ in range(260):
        x = min(w - 3, max(2, x + r.randint(0, 2) + (1 if r.random() < .2 else 0)))
        y = min(h - 3, max(2, y + r.randint(-6, 6)))
        for dx in (0, 1):
            for dy in (0, 1):
                img[y + dy][x + dx] = 20
    raw = b"".join(b"\x00" + bytes(row) for row in img)

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


# ---- sestavení datové sady ----------------------------------------------

class Store:
    def __init__(self):
        self.cases = {}      # case_id -> {slug, client, docs: [doc_id]}
        self.docs = {}       # (case_id, doc_id) -> dict
        self.sigs = {}       # signature_id -> dict
        self._build()

    def _add_doc(self, slug, client, name, pages, opts):
        cid, did = case_uuid(slug), doc_uuid(slug, name)
        label = label_of(name)
        verified = bool(opts.get("verified"))
        status = opts.get("status", "partial" if opts.get("partial") else "completed")
        pages = list(pages)
        for p in opts.get("partial", []):
            if p <= len(pages):
                pages[p - 1] = ""
        text = "\f".join(pages)
        r = _rng("conf/" + did)
        if verified:
            conf = 1.0
        elif opts.get("no_confidence") or label == "data_ze_systemu":
            conf = None
        else:
            conf = round(0.72 + r.random() * 0.27, 2)
        doc = dict(
            case_id=cid, document_id=did, title=name, slug=slug, label=label,
            label_status="verified" if verified else "predicted",
            description=f"{LABEL_NAMES.get(label, label)} – {client}",
            text=text, confidence=conf, page_count=len(pages),
            processing_status=status, verified=verified,
            pages_failed=list(opts.get("partial", [])),
        )
        self.docs[(cid, did)] = doc
        self.cases.setdefault(cid, dict(slug=slug, client=client, docs=[]))["docs"].append(did)
        return doc

    def _build(self):
        for slug, c in CASES.items():
            for name, opts in c["docs"].items():
                pages = read_pages(slug, name) or [""]
                self._add_doc(slug, c["client"], name, pages, opts)
        for company in REF_COMPANIES:
            for prefix, label in LABELS:
                if label in ("vop", "data_ze_systemu"):
                    continue
                name = f"{prefix}ref_{label}_{company.split()[0].lower()}.pdf"
                pages = [f"{LABEL_NAMES[label].upper()}\nstrana 1\nÚčastník: {company}\nSyntetický referenční dokument.",
                         "Podpisy stran.\n"]
                self._add_doc(REF_CASE, company, name, pages, dict(verified=True))
        self._build_signatures()
        self._build_vectors()

    def _build_signatures(self):
        by_key = {}
        for (cid, did), d in self.docs.items():
            if d["processing_status"] not in ("completed", "partial"):
                continue
            roles = SIGNING.get(d["label"], [])
            sigs = []
            for i, (role, evidence) in enumerate(roles):
                page = d["page_count"] if d["page_count"] > 0 else 1
                y = 0.62 + 0.12 * i
                sid = f"sig_{i + 1:02d}"
                full = f"{did}/{sid}"
                seed = f"{d['slug']}/{role}"
                s = dict(
                    signature_id=sid, page=page, bbox=[0.12, round(y, 2), 0.38, round(y + 0.08, 2)],
                    detector="textract", detection_score=round(11.9 + _rng(full).random() * 54, 1),
                    role=role, role_source="nearest_text", role_evidence=evidence,
                    phash=hashlib.sha256(("phash/" + seed + "/" + d["title"]).encode()).hexdigest()[:16],
                    _doc=(cid, did), _seed=seed, _full=full,
                )
                sigs.append(s)
                by_key[(d["slug"], d["title"], role)] = s
            d["_sigs"] = sigs
        # naplánovaná kopie: podpis příjemce ve smlouvě se objeví i v dalším dokumentu
        for (cid, did), d in self.docs.items():
            cf = CASES.get(d["slug"], {}).get("docs", {}).get(d["title"], {}).get("copy_from")
            if cf and d.get("_sigs"):
                src = by_key.get((d["slug"], cf[0], cf[1]))
                target = d["_sigs"][0]
                if src:
                    target["phash"] = src["phash"]
                    target["_seed"] = src["_seed"]
        for d in self.docs.values():
            for s in d.get("_sigs", []):
                self.sigs[s["_full"]] = s
                s["_vec"] = _norm(_gauss(f"sig/{d['slug']}/{s['_seed']}", SIG_DIM))

    def _build_vectors(self):
        for (cid, did), d in self.docs.items():
            if d["processing_status"] not in ("completed", "partial"):
                d["_text_vecs"], d["_doc_vec"] = [], None
                continue
            pages = d["text"].split("\f")
            chunks, i = [], 0
            while i < len(pages):
                chunks.append((i + 1, min(i + 2, len(pages))))
                i += 2
            d["_chunks"] = chunks
            d["_text_vecs"] = [embed("text", TEXT_DIM, d["label"], did, f"c{n}") for n in range(len(chunks))]
            d["_doc_vec"] = _norm([sum(col) for col in zip(*d["_text_vecs"])]) if chunks else None
        self.verified = [d for d in self.docs.values() if d["verified"] and d["_doc_vec"]]

    # ---- čtení pro API ----

    def get_doc(self, cid, did):
        return self.docs.get((cid, did))

    def image_vectors(self, d, with_values):
        return [dict(_vec_meta(IMAGE_MODEL, IMAGE_DIM,
                               embed("image", IMAGE_DIM, d["label"], d["document_id"], f"p{p}")
                               if with_values else None, with_values), page=p)
                for p in range(1, d["page_count"] + 1)]

    def text_vectors(self, d, with_values):
        return [dict(_vec_meta(TEXT_MODEL, TEXT_DIM, v, with_values),
                     chunk_id=f"c{n}", page_from=a, page_to=b)
                for n, ((a, b), v) in enumerate(zip(d.get("_chunks", []), d["_text_vecs"]))]

    def neighbors(self, d, n):
        if not d["_doc_vec"]:
            return []
        scored = [(cosine(d["_doc_vec"], o["_doc_vec"]), o) for o in self.verified
                  if o["document_id"] != d["document_id"]]
        scored.sort(key=lambda t: -t[0])
        return [dict(document_id=o["document_id"], label=o["label"], score=round(s, 4))
                for s, o in scored[:n]]

    def signatures(self, d, match_client, include_vectors):
        out = []
        for s in d.get("_sigs", []):
            item = dict(
                signature_id=s["signature_id"], page=s["page"], bbox=s["bbox"],
                detector=s["detector"], detection_score=s["detection_score"], role=s["role"],
                role_source=s["role_source"], role_evidence=s["role_evidence"],
                crop_url=None, phash=s["phash"],
            )
            # copy_suspicion: stejný phash v jiném dokumentu
            matches = [dict(signature_id=o["signature_id"], document_id=o["_doc"][1], score=1.0)
                       for o in self.sigs.values()
                       if o["phash"] == s["phash"] and o["_doc"] != s["_doc"]]
            item["copy_suspicion"] = dict(level="suspected" if matches else "none", matches=matches)
            item["vector"] = (dict(_vec_meta(SIG_MODEL, SIG_DIM, s["_vec"], True)) if include_vectors else None)
            if match_client:
                cands = [o for o in self.sigs.values()
                         if o["_doc"][0] == s["_doc"][0] and o["_doc"] != s["_doc"] and o["role"] == s["role"]]
                sims = sorted(((cosine(s["_vec"], o["_vec"]), o) for o in cands), key=lambda t: -t[0])[:3]
                item["similar_signatures"] = [
                    dict(signature_id=o["signature_id"], document_id=o["_doc"][1], score=round(sc, 4))
                    for sc, o in sims]
            out.append((item, s))
        return out
