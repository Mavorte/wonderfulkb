#!/usr/bin/env python3
"""Projede texty z docs/vzorove-dokumenty/text/ a vypíše štítek, jistotu a shodu s očekávaným typem.

Očekávaný typ se odvozuje z číselného prefixu názvu souboru JEN pro vyhodnocení; klasifikátor název nedostane.

  python evaluate.py                    jedno volání modelu na dokument (štítek, popis, jistota), Haiku 4.5 přes Converse
  python evaluate.py --backend mantle   Qwen3 VL přes Mantle (qwen.qwen3-vl-235b-a22b-instruct, výhradně Frankfurt)
  python evaluate.py --rules-only       jen pravidla, bez AWS
  python evaluate.py --strip-head 600   bez nadpisu a úvodu (zátěžový test)
  AWS přihlášení z prostředí (AWS_PROFILE=hackathon), region eu-central-1.
"""
import os
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from classify import classify_document_detailed  # noqa: E402
from classify.llm import make_backend  # noqa: E402

# Vzorové dokumenty z hackathonového balíku nejsou v repu: WONDERFULKB_SAMPLES_DIR ukazuje na složku `vzorove-dokumenty`.
DEFAULT_DIR = Path(os.environ.get("WONDERFULKB_SAMPLES_DIR", "vzorove-dokumenty")) / "text"
# prefix názvu souboru -> očekávaný štítek (jen pro vyhodnocení)
EXPECTED = {"0": "smlouva_o_uveru", "01": "vop", "09": "dohoda_o_zaplaceni_kupni_ceny",
            "2": "zajistovaci_prevod_vlastnickeho_prava", "3": "vinkulace_pojisteni", "4": "ruceni",
            "10": "objednavka", "11": "predavaci_protokol", "14": "uhrada_kupni_ceny", "99": "data_ze_systemu"}


def parse_dump(md: str) -> tuple[str, int]:
    """Z markdown výpisu (## Strana N + blok ```text```) složí text se stranami oddělenými \\f."""
    parts = re.split(r"^## Strana \d+\s*$", md, flags=re.M)[1:]
    pages = []
    for part in parts:
        m = re.search(r"```text\n(.*?)\n```", part, flags=re.S)
        pages.append(m.group(1) if m else "")
    return "\f".join(pages), len(pages)


def expected_label(path: Path) -> str | None:
    m = re.match(r"(\d+)_", path.name)
    return EXPECTED.get(m.group(1)) if m else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--rules-only", action="store_true", help="nevolat Bedrock")
    ap.add_argument("--backend", choices=("converse", "mantle"), default=None, help="výchozí converse")
    ap.add_argument("--model", default=None, help="ID modelu (výchozí podle backendu)")
    ap.add_argument("--show-description", action="store_true", help="vypsat i popisy z modelu")
    ap.add_argument("--strip-head", type=int, default=0, metavar="N",
                    help="odříznout prvních N znaků (simuluje chybějící nadpis; zátěžový test pravidel)")
    ap.add_argument("--json", type=Path, help="uložit výsledky do JSON")
    args = ap.parse_args(argv)

    files = sorted(args.dir.glob("*/*.md"))
    if not files:
        print(f"Žádné texty v {args.dir}", file=sys.stderr)
        return 2
    rows = []
    for f in files:
        text, pages = parse_dump(f.read_text(encoding="utf-8"))
        text = text[args.strip_head:] if args.strip_head else text
        t0 = time.monotonic()
        backend = make_backend(model_id=args.model, backend=args.backend) if not args.rules_only else None
        r = classify_document_detailed(text, None, pages, use_llm=not args.rules_only, backend=backend)
        r["seconds"] = round(time.monotonic() - t0, 1)
        r.update(file=f"{f.parent.name}/{f.stem}", expected=expected_label(f), pages=pages,
                 chars=len(text.strip()))
        rows.append(r)

    print(f"{'soubor':58} {'očekávaný':38} {'predikce':38} {'jistota':>7} {'metoda':>6} {'s':>5}  shoda")
    for r in rows:
        ok = "ano" if r["label"] == r["expected"] else ("bez textu" if r["method"] == "none" and not r.get("error") else "NE")
        conf = "-" if r["confidence"] is None else f"{r['confidence']:.2f}"
        print(f"{r['file'][:58]:58} {str(r['expected']):38} {str(r['label']):38} {conf:>7} {r['method']:>6} {r['seconds']:>5}  {ok}")
        if args.show_description:
            print(f"    popis: {r['description']}")
    scored = [r for r in rows if r["method"] != "none" or r.get("error")]
    hits = sum(r["label"] == r["expected"] for r in scored)
    skipped = len(rows) - len(scored)
    by_method = {m: sum(1 for r in scored if r["method"] == m) for m in ("rules", "llm")}
    print(f"\nPřesnost: {hits}/{len(scored)} dokumentů s textem; bez textové vrstvy (sken) {skipped}; "
          f"rules {by_method['rules']}, llm {by_method['llm']}")
    calls = [r["seconds"] for r in rows if r["method"] == "llm"]
    if calls:
        print(f"Latence volání modelu: medián {sorted(calls)[len(calls) // 2]} s, max {max(calls)} s")
    agree = [r for r in scored if r["method"] == "llm" and r["rule_label"]]
    if agree:
        print(f"Pravidla a model se shodují u {sum(r['label'] == r['rule_label'] for r in agree)}/{len(agree)} "
              "dokumentů, kde pravidla rozhodla")
    tokens = sum(r.get("usage", {}).get("totalTokens", 0) for r in rows)
    if tokens:
        print(f"Tokeny modelu celkem: {tokens}")
    for r in rows:
        if r["label"] != r["expected"] and r["method"] != "none":
            print(f"  chyba: {r['file']} -> {r['label']} (kandidáti pravidel {r['candidates']}) {r.get('error', '')}")
    if args.json:
        args.json.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
