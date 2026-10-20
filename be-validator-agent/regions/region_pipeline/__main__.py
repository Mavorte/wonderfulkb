"""python -m region_pipeline a.pdf [b.pdf …] [--out-dir DIR] [--render] [--label rules|llm]
→ DIR/<název>.regions.json (+ PNG)."""
import argparse
import json
import sys
from pathlib import Path

from .labels import label_regions
from .render import render
from .segment import regions_for_pdf


def main(argv=None):
    ap = argparse.ArgumentParser(prog="region_pipeline")
    ap.add_argument("pdf", nargs="+")
    ap.add_argument("--out-dir", default="out")
    ap.add_argument("--render", action="store_true", help="vykreslit strany s obdélníky regionů do PNG")
    ap.add_argument("--print", action="store_true", help="vypsat regiony (id, kind, text) na stdout")
    ap.add_argument("--label", choices=["rules", "llm"], help="doplnit štítky: jen regexy, nebo model se zálohou")
    ap.add_argument("--doc-label", help="typ dokumentu z classify/taxonomy.yaml (stejný pro všechna PDF)")
    ap.add_argument("--backend", choices=["converse", "mantle"], help="backend modelu (výchozí REGIONS_BACKEND)")
    args = ap.parse_args(argv)
    backend = limiter = None
    if args.label == "llm":
        from .llm import default_limiter, make_backend
        backend, limiter = make_backend(args.backend), default_limiter()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for pdf in args.pdf:
        result = regions_for_pdf(pdf)
        result["title"] = Path(pdf).name
        if args.label:
            stats = label_regions(result, backend=backend, doc_label=args.doc_label, limiter=limiter)
            print(f"  štítky: {stats}")
        (out / f"{Path(pdf).stem}.regions.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
        kinds = {}
        for r in result["regions"]:
            kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        scans = [p["page"] for p in result["pages"] if p["source"] != "text_layer"]
        print(f"{Path(pdf).name}: {len(result['regions'])} regionů {kinds}" + (f", bez textové vrstvy s. {scans}" if scans else ""))
        if args.print:
            for r in result["regions"]:
                tag = r.get("label") or ""
                if r.get("party"):
                    tag += f"/{r['party']}"
                if r.get("refers_to"):
                    tag += f"→{','.join(r['refers_to'])}"
                print(f"  {r['region_id']:8} {r['kind']:11} {tag:32} {r['text'][:90]}")
        if args.render:
            render(pdf, result, out / "png")
    if backend is not None:
        print(f"model: {backend.name} {backend.model_id}, tokeny {backend.usage}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
