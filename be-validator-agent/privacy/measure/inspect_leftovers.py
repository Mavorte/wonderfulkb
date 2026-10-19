"""Ruční prohlídka: pro vybrané pravdivé podpisy uloží vedle sebe výřez originálu a zamaskované kopie.

    python -I inspect_leftovers.py DATA_DIR 'OUT/results_*.json' PNG_DIR [--max 12] [--min-left 0.1] [--file text]

Bere podpisy skupiny A, u nichž zbylo > `--min-left` inkoustu, seřazené podle zbytku. Výstup: PNG
`<soubor>__p<strana>__<i>.png` (vlevo originál, vpravo po redakci, okraj 6 % strany kolem pravdivého boxu,
červený rámeček = box z anotace). Zamaskovaná PDF se čtou z `OUT/pdf/` (měření s --keep-pdf).
"""
import argparse
import glob
import json
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("results", help="cesta nebo vzor (v uvozovkách)")
    ap.add_argument("out_dir")
    ap.add_argument("--max", type=int, default=12)
    ap.add_argument("--min-left", type=float, default=0.10)
    ap.add_argument("--file", help="podřetězec názvu souboru")
    a = ap.parse_args()
    files = sorted(glob.glob(a.results))
    res = [r for f in files for r in json.load(open(f))]
    pdfdir = Path(files[0]).parent / "pdf"
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = [(r, s) for r in res if r["group"] == "generic" and "error" not in r for s in r["sigs"]
            if s.get("left_frac") is not None and s["left_frac"] > a.min_left and (not a.file or a.file in r["file"])]
    rows.sort(key=lambda t: -t[1]["left_frac"])
    for r, s in rows[:a.max]:
        orig = pymupdf.open(Path(a.data_dir) / "generic" / r["file"])
        red = pymupdf.open(pdfdir / r["file"])
        x0, y0, x1, y1 = s["bbox"]
        m = 0.06
        ims = []
        for d in (orig, red):
            p = d[s["page"] - 1]
            W, H = p.rect.width, p.rect.height
            c = pymupdf.Rect(max(0, x0 - m) * W, max(0, y0 - m) * H, min(1, x1 + m) * W, min(1, y1 + m) * H)
            pix = p.get_pixmap(dpi=130, clip=c, alpha=False)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            ImageDraw.Draw(im).rectangle([(x0 * W - c.x0) / c.width * pix.width, (y0 * H - c.y0) / c.height * pix.height,
                                          (x1 * W - c.x0) / c.width * pix.width, (y1 * H - c.y0) / c.height * pix.height],
                                         outline=(255, 0, 0), width=1)
            ims.append(im)
        canvas = Image.new("RGB", (ims[0].width + ims[1].width + 10, max(i.height for i in ims)), (200, 200, 255))
        canvas.paste(ims[0], (0, 0))
        canvas.paste(ims[1], (ims[0].width + 10, 0))
        name = f"{r['file'][:-4]}__p{s['page']}__{s['i']}.png"
        canvas.save(out / name)
        print(name, f"zbylo {s['left_frac']:.0%}", r["quality"])


if __name__ == "__main__":
    main()
