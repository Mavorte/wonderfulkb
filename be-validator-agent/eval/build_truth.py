"""Sestaví truth.yaml (a truth.json) z balíku 20 syntetických případů a z dokumentace repa.

Balík je nedůvěryhodná data: stahuje se do nové prázdné složky, tento skript z ní jen čte (JSON, PDF přes pypdf)
a nic z ní nespouští. Spouští se s `-I`:

    aws s3 cp s3://wonderfulkb-raw-document-storage/cases/synteticke_dokumenty_20_pripadu.zip NOVA_PRAZDNA/bundle.zip
    unzip -q NOVA_PRAZDNA/bundle.zip -d NOVA_PRAZDNA/x
    python -I build_truth.py --bundle NOVA_PRAZDNA/x/synteticke_dokumenty_20_pripadu --zip NOVA_PRAZDNA/bundle.zip

Potřebuje pypdf a PyYAML (např. `infra/validator-agent/pipeline/.venv`). Ruční kontrola původních dvou případů
(`originals_review.yaml`) se jen přilévá, skript ji nevytváří.
"""
import argparse
import glob
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import pypdf
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TAXONOMY = os.path.join(HERE, "..", "classify", "taxonomy.yaml")
# Vzorové dokumenty z hackathonového balíku nejsou v repu: WONDERFULKB_SAMPLES_DIR ukazuje na složku `vzorove-dokumenty`.
SAMPLES = os.environ.get("WONDERFULKB_SAMPLES_DIR", os.path.join(REPO, "vzorove-dokumenty"))

SOURCES = {
    "S_MANIFEST": "manifest.json v balíku (pole kind, pages, quality u každého ze 165 primárních PDF)",
    "S_ANNOT": "anotace/<případ>/<dokument>.json v balíku (marks = podpisy s page a signature_bbox v bodech PDF, "
               "fields = hodnoty polí); README balíku: razítka a podpisy jsou vektorové kresby, anotace jsou autoritativní",
    "S_BUNDLE_README": "README.md balíku a obou datových sad (korpus je záměrně bez vložených chyb, "
                       "expected_semantic_consistency=true u každého dokumentu)",
    "S_PDF": "samotné PDF (počet stran a velikost strany přes pypdf)",
    "S_TAXONOMY": "infra/validator-agent/classify/taxonomy.yaml (id štítků; popis štítků)",
    "S_PREFIX": "docs/dokumenty-a-skupiny.md + docs/vzorove-dokumenty/README.md (číselný prefix = skupina, tabulka souborů)",
    "S_SCENARE": "docs/scenare.md (šest obchodních scénářů)",
    "S_ZADANI": "docs/zadani-sgef.md (PP = předávací protokol, dodací list)",
    "S_REVIEW": "ruční vizuální kontrola PDF (originals_review.yaml), nezávislá na výstupu detektorů; "
                "neověřil ji druhý člověk",
}

# kind v manifestu balíku -> štítek taxonomie. certainty: certain = typ je v taxonomii jmenovitě;
# probable = typ je v taxonomii zahrnut jen popisem (accept pak obsahuje i věrohodné alternativy);
# unmapped = taxonomie pro typ štítek nemá (z přesnosti se vylučuje, uvádí se zvlášť).
KIND_LABELS = {
    "uver": ("smlouva_o_uveru", "certain", "taxonomy: smlouva_o_uveru"),
    "vop": ("vop", "certain", "taxonomy: vop"),
    "dohoda": ("dohoda_o_zaplaceni_kupni_ceny", "certain", "taxonomy: dohoda_o_zaplaceni_kupni_ceny"),
    "objednavka": ("objednavka", "certain", "taxonomy: objednavka"),
    "objednavka_ts": ("objednavka", "certain",
                      "taxonomy: objednavka (popis: může obsahovat přiloženou technickou specifikaci)"),
    "predani": ("predavaci_protokol", "probable",
                "taxonomy: predavaci_protokol (název dokumentu v balíku bývá „Předávací certifikát“ / „Protokol“)"),
    "vlastnictvi": ("predavaci_protokol", "certain",
                    "taxonomy: predavaci_protokol zahrnuje „potvrzení o převodu vlastnictví“"),
    "zajisteni": ("zajistovaci_prevod_vlastnickeho_prava", "certain",
                  "taxonomy: zajistovaci_prevod_vlastnickeho_prava"),
    "vinkulace": ("vinkulace_pojisteni", "certain", "taxonomy: vinkulace_pojisteni"),
    "ruceni": ("ruceni", "certain", "taxonomy: ruceni"),
    "kontrola": ("data_ze_systemu", "certain", "taxonomy: data_ze_systemu („Kontrola smlouvy“)"),
    "uhrada": ("uhrada_kupni_ceny", "certain", "taxonomy: uhrada_kupni_ceny („Oznámení o provedení příkazu k úhradě“)"),
    "faktura": ("faktura", "certain", "taxonomy: faktura"),
    "specifikace": ("technicka_specifikace", "certain", "taxonomy: technicka_specifikace"),
    "nabidka": ("technicka_specifikace", "probable",
                "taxonomy: technicka_specifikace zahrnuje „cenovou nabídku“; v balíku „Cenová a technická nabídka“"),
    "dodaci_list": ("predavaci_protokol", "probable",
                    "docs/zadani-sgef.md: PP = předávací protokol, dodací list"),
    "cerpani": (None, "unmapped", "taxonomie nemá štítek pro „Potvrzení o čerpání úvěru“"),
    "splatky": (None, "unmapped", "taxonomie nemá štítek pro „Splátkový kalendář“"),
}
KIND_ACCEPT = {  # další přijatelné štítky u probable
    "predani": ["predavaci_protokol"],
    "nabidka": ["technicka_specifikace", "objednavka"],
    "dodaci_list": ["predavaci_protokol"],
}
# prefix názvu souboru u původních dvou případů (solom-rec, stavby-fiser)
PREFIX_LABELS = {
    "0": ("smlouva_o_uveru", "certain"),
    "01": ("vop", "certain"),
    "09": ("dohoda_o_zaplaceni_kupni_ceny", "certain"),
    "2": ("zajistovaci_prevod_vlastnickeho_prava", "certain"),
    "3": ("vinkulace_pojisteni", "certain"),
    "4": ("ruceni", "certain"),
    "10": ("objednavka", "probable"),   # 1x je „guláš variant“; v Stavby je objednávka + TS v jednom PDF
    "11": ("predavaci_protokol", "probable"),
    "14": ("uhrada_kupni_ceny", "certain"),
    "99": ("data_ze_systemu", "certain"),
}
PREFIX_ACCEPT = {"10": ["objednavka", "technicka_specifikace"], "11": ["predavaci_protokol"]}

ROLE_MAP = {  # role z anotací balíku (anglicky i česky) -> enum role v OpenAPI
    "provider": "provider", "Poskytovatel financování": "provider", "Poskytovatel – první podpis": "provider",
    "Poskytovatel – druhý podpis": "provider", "Věřitel – první zmocněnec": "provider",
    "Věřitel – druhý zmocněnec": "provider", "Druhý zmocněnec věřitele": "provider",
    "borrower": "borrower", "Příjemce financování": "borrower", "Pojistník": "borrower",
    "buyer": "buyer", "Objednatel": "buyer", "Kupující": "buyer", "Přebírající": "buyer", "Zákazník": "buyer",
    "supplier": "supplier", "Dodavatel": "supplier", "Prodávající": "supplier", "Předávající": "supplier",
    "Servis dodavatele": "supplier",
    "guarantor": "guarantor", "Ručitel": "guarantor",
    "insurer": "insurer", "Pojistitel": "insurer",
}

SCENARIOS = {
    "happy_path": {
        "number": 1, "source": "S_SCENARE",
        "expected_findings": [],
        "measurable_here": "Všechny dokumenty sady jsou k dispozici (completed/partial), každý očekávaný podpis nalezen, "
                           "žádný falešný nález.",
        "truth_for_bundle": "Všech 20 syntetických případů je obsahově konzistentních pozitivních příkladů "
                            "(S_BUNDLE_README), takže jim náleží scénář 1 a žádný nález.",
    },
    "chybi_dokument": {
        "number": 2, "source": "S_SCENARE",
        "measurable_here": "Sada dokumentů případu v API (seznam, štítky) proti seznamu dokumentů pravdy; chybějící "
                           "typ je nález. Vyžaduje mapping.json s uvedením odebraných souborů (removed_documents).",
    },
    "spatny_dokument": {
        "number": 3, "source": "S_SCENARE",
        "unmeasurable_reason": "Dokument je správného typu, ale s jiným obsahem (např. faktura za jiné zboží). "
                               "Štítek zůstane správný; rozpor se pozná až porovnáním s jinými dokumenty, což je "
                               "úloha validačního agenta, ne tří čtecích volání.",
    },
    "spatne_udaje": {
        "number": 4, "source": "S_SCENARE",
        "unmeasurable_reason": "Rozpor údajů napříč dokumenty (ID entit) vyhodnocuje validační agent z textu. "
                               "Měří se jen, zda text obsahuje anotované hodnoty polí (podmínka, ne nález).",
    },
    "chybi_podpis": {
        "number": 5, "source": "S_SCENARE",
        "measurable_here": "Volání 3 vrací méně podpisů než pravda základního případu; chybějící podpis se pozná podle "
                           "strany a role. Vyžaduje mapping.json s uvedením odebraných podpisů "
                           "(variant.removed_signatures).",
    },
    "nevytezi_se": {
        "number": 6, "source": "S_SCENARE",
        "measurable_here": "Horší kvalita vstupu (sken, fax, fotokopie): stav partial/failed, prázdný nebo neúplný "
                           "text, nízká jistota. Měří se po třídách kvality (quality v pravdě).",
    },
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def page_sizes(pdf_path):
    r = pypdf.PdfReader(pdf_path)
    return [(float(p.mediabox.width), float(p.mediabox.height)) for p in r.pages]


def norm_bbox(bb, size):
    w, h = size
    x0, y0, x1, y1 = bb
    clamp = lambda v: max(0.0, min(1.0, v))  # noqa: E731
    return [round(clamp(x0 / w), 4), round(clamp(y0 / h), 4), round(clamp(x1 / w), 4), round(clamp(y1 / h), 4)]


FIELD_PRIORITY = ["contract", "serial", "invoice", "order", "policy", "principal", "net", "gross", "total",
                  "entity_name", "supplier.name", "borrower.name", "provider.name", "borrower.ico", "asset"]


def pick_fields(fields, limit=10):
    flat = [x for y in fields for x in (y if isinstance(y, list) else [y])]
    out, seen = [], set()
    for key in FIELD_PRIORITY:
        for f in flat:
            v = str(f.get("value", "")).strip()
            if f.get("key") == key and len(v) >= 4 and (key, v) not in seen:
                seen.add((key, v))
                out.append({"key": key, "value": v})
                break
        if len(out) >= limit:
            break
    return out


def load_annotation(bundle, dataset, case, filename_stem):
    p = os.path.join(bundle, dataset, "anotace", case, filename_stem + ".json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def build_generic(bundle, taxonomy_ids):
    manifest = json.load(open(os.path.join(bundle, "manifest.json"), encoding="utf-8"))
    catalog = {}
    with open(os.path.join(bundle, "katalog.csv"), encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        for line in f:
            row = dict(zip(header, line.rstrip("\n").split(",")))
            catalog[row["case_id"]] = row
    cases = {}
    for m in sorted(manifest, key=lambda d: d["path"]):
        case = m["case_id"]
        dataset = m["path"].split("/")[0]
        filename = os.path.basename(m["path"])
        stem = os.path.splitext(filename)[0]
        ann = load_annotation(bundle, dataset, case, stem)
        pdf = os.path.join(bundle, m["path"])
        sizes = page_sizes(pdf)
        if len(sizes) != m["pages"]:
            raise SystemExit(f"{m['path']}: manifest {m['pages']} stran, PDF {len(sizes)}")
        label, cert, lsrc = KIND_LABELS[m["kind"]]
        if label is not None and label not in taxonomy_ids:
            raise SystemExit(f"štítek {label} není v taxonomy.yaml")
        reps = [p.get("representation") for p in ann.get("pages", [])] if isinstance(ann.get("pages"), list) else []
        image_only = [i + 1 for i, r in enumerate(reps) if r == "image_only"]
        if m["kind"] and (not reps or not image_only):
            text_layer = "digital"
        else:
            text_layer = "image_only" if len(image_only) == len(sizes) else "mixed"
        sigs = []
        for mk in ann["marks"]:
            bb = mk.get("signature_bbox")
            if not bb:
                continue
            page = mk["page"]
            sigs.append({
                "page": page,
                "bbox": norm_bbox(bb, sizes[page - 1]),
                "role": ROLE_MAP[mk["role"]],
                "role_raw": mk["role"],
                "identity": mk["signature_identity"][:12],
            })
        sigs.sort(key=lambda s: (s["page"], s["bbox"][0], s["bbox"][1]))
        doc = {
            "kind": m["kind"],
            "sha256": m["sha256"],
            "label": label,
            "label_certainty": cert,
            "accept": sorted(set(KIND_ACCEPT.get(m["kind"], [label] if label else []))),
            "page_count": m["pages"],
            "quality": m["quality"],
            "text_layer": text_layer,
            "image_only_pages": image_only,
            "signatures": {"status": "known", "items": sigs},
            "fields": pick_fields(ann.get("fields", [])),
            "sources": {"label": ["S_MANIFEST", "S_TAXONOMY"], "label_note": lsrc,
                        "page_count": ["S_MANIFEST", "S_PDF"], "quality": "S_MANIFEST",
                        "signatures": "S_ANNOT", "fields": "S_ANNOT"},
        }
        c = cases.setdefault(case, {
            "group": "generic", "dataset": dataset, "asset": catalog[case]["asset"],
            "scenario": "happy_path",
            "scenario_source": ["S_BUNDLE_README", "S_SCENARE"], "documents": {},
        })
        c["documents"][filename] = doc
    # skupiny shodných podpisů uvnitř případu (stejný signatář = stejný základ tahů, viz README balíku)
    for c in cases.values():
        by_id = {}
        for fn, d in c["documents"].items():
            for s in d["signatures"]["items"]:
                by_id.setdefault(s["identity"], set()).add(fn)
        for fn, d in c["documents"].items():
            for s in d["signatures"]["items"]:
                s["same_signer_in_other_docs"] = len(by_id[s["identity"]] - {fn})
    return cases


def prefix_of(name):
    return name.split("_")[0]


def build_originals(taxonomy_ids, review):
    cases = {}
    for slug in ("solom-rec", "stavby-fiser"):
        docs = {}
        for pdf in sorted(glob.glob(os.path.join(SAMPLES, slug, "*.pdf"))):
            fn = os.path.basename(pdf)
            pre = prefix_of(fn)
            label, cert = PREFIX_LABELS[pre]
            assert label in taxonomy_ids
            sizes = page_sizes(pdf)
            rv = (review or {}).get(slug, {}).get(fn)
            if rv:
                sig = {"status": "reviewed", "granularity": rv.get("granularity", "bbox"), "items": rv["items"],
                       "reviewed_pages": rv.get("reviewed_pages", "all"), "note": rv.get("note")}
                sig_src = "S_REVIEW"
            else:
                sig = {"status": "unknown", "items": []}
                sig_src = None
            docs[fn] = {
                "kind": pre, "sha256": sha256(pdf), "label": label, "label_certainty": cert,
                "accept": sorted(set(PREFIX_ACCEPT.get(pre, [label]))),
                "page_count": len(sizes),
                "quality": "original", "text_layer": "unknown", "image_only_pages": [],
                "signatures": sig, "fields": [],
                "sources": {"label": ["S_PREFIX", "S_TAXONOMY"], "page_count": "S_PDF", "signatures": sig_src,
                            "fields": None},
            }
        cases[slug] = {"group": "original", "dataset": "docs/vzorove-dokumenty", "asset": slug,
                       "scenario": "unknown",
                       "scenario_source": ["S_PREFIX"], "documents": docs}
    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True, help="rozbalená složka synteticke_dokumenty_20_pripadu")
    ap.add_argument("--zip", help="původní ZIP (zapíše se jeho SHA-256)")
    ap.add_argument("--review", default=os.path.join(HERE, "originals_review.yaml"))
    ap.add_argument("--out", default=HERE)
    a = ap.parse_args()
    tax = yaml.safe_load(open(TAXONOMY, encoding="utf-8"))
    ids = set(tax["labels"])
    review = yaml.safe_load(open(a.review, encoding="utf-8")) if os.path.exists(a.review) else {}
    cases = build_generic(a.bundle, ids)
    cases.update(build_originals(ids, (review or {}).get("cases")))
    truth = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bundle": {"s3_uri": "s3://wonderfulkb-raw-document-storage/cases/synteticke_dokumenty_20_pripadu.zip",
                       "zip_sha256": sha256(a.zip) if a.zip else None},
            "taxonomy_labels": sorted(ids),
            "bbox": "relativní souřadnice strany [x0, y0, x1, y1], počátek vlevo nahoře (jako v OpenAPI)",
            "groups": {"generic": "20 syntetických případů, generické vektorové podpisy",
                       "original": "solom-rec a stavby-fiser, lidské rukopisné podpisy"},
        },
        "sources": SOURCES,
        "label_map": {"generic_kind": {k: {"label": v[0], "certainty": v[1], "source": v[2]}
                                        for k, v in KIND_LABELS.items()},
                      "original_prefix": {k: {"label": v[0], "certainty": v[1]} for k, v in PREFIX_LABELS.items()}},
        "role_map": ROLE_MAP,
        "scenarios": SCENARIOS,
        "cases": cases,
    }
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "truth.yaml"), "w", encoding="utf-8") as f:
        f.write("# Pravda pro evaluate_e2e.py. Generuje build_truth.py, ručně neupravovat (ruční část je "
                "originals_review.yaml).\n# Každá hodnota má `sources` (klíče do `sources:` nahoře).\n")
        yaml.safe_dump(truth, f, allow_unicode=True, sort_keys=False, width=120)
    with open(os.path.join(a.out, "truth.json"), "w", encoding="utf-8") as f:
        json.dump(truth, f, ensure_ascii=False, indent=1)
    n_docs = sum(len(c["documents"]) for c in cases.values())
    n_sig = sum(len(d["signatures"]["items"]) for c in cases.values() if c["group"] == "generic"
                for d in c["documents"].values())
    print(f"případů {len(cases)}, dokumentů {n_docs}, podpisů v generických {n_sig}", file=sys.stderr)


if __name__ == "__main__":
    main()
