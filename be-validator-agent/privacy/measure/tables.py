"""Z results_*.json udělá tabulky pro report.md (markdown na stdout).

    python -I tables.py OUT_DIR/results_zones_v1.json [další.json ...] [--review visual_review.json]

Skupiny se nikdy nesloučí: `generic` (anotace balíku) a `original` (rukopis, ruční kontrola) mají samostatné tabulky.
Intervaly: Wilsonův 95% interval podílu.
"""
import argparse
import json
import math
import re
from collections import defaultdict
from statistics import mean, median


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 2
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def pct(x):
    return f"{100 * x:.1f} %"


def cell(k, n):
    if n == 0:
        return "–"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {pct(k / n)} ({pct(lo)} až {pct(hi)})"


def perc(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else float("nan")


def generic_tables(res, label):
    docs = [r for r in res if r["group"] == "generic" and "error" not in r]
    errs = [r for r in res if "error" in r]
    out = [f"#### {label}: skupina A (generic), pravdivé podpisy z anotací", ""]
    by_q = defaultdict(list)
    for r in docs:
        for s in r["sigs"]:
            if "error" not in s:
                by_q[r["quality"]].append((r, s))
    allp = [x for v in by_q.values() for x in v]
    out += ["| Vstup | dokumentů | podpisů (s inkoustem) | po redakci NEČITELNÉ (zbylo ≤ 10 % inkoustu) | zbylo čitelné | z toho zcela černě překryto (≥ 90 % boxu) |",
            "|---|---|---|---|---|---|"]
    for q in sorted(by_q, key=lambda q: -len(by_q[q])) + ["VŠECHNY"]:
        items = allp if q == "VŠECHNY" else by_q[q]
        ds = {r["file"] for r, _ in items}
        ok = [s for _, s in items if not s["no_ink"]]
        hid = sum(1 for s in ok if not s["readable"])
        blk = sum(1 for s in ok if s["cover_black"] >= 0.9)
        out.append(f"| {q} | {len(ds)} | {len(ok)} | {cell(hid, len(ok))} | {len(ok) - hid} | {cell(blk, len(ok))} |")
    noink = sum(1 for _, s in allp if s["no_ink"])
    out += ["", f"Podpisy v anotaci bez inkoustu v boxu (méně než 30 pixelů, nejde měřit): {noink}. Dokumenty s chybou: {len(errs)}.", ""]
    return out, allp


def leftovers(allp, limit=60):
    out = ["| soubor | strana | role | zbylo inkoustu | pokrytí černě | pokrytí maskou/zónou | typ |", "|---|---|---|---|---|---|---|"]
    rows = [(r, s) for r, s in allp if s["readable"]]
    rows.sort(key=lambda t: -t[1]["left_frac"])
    for r, s in rows[:limit]:
        out.append(f"| {r['file'][:48]} | {s['page']} | {s['role']} | {pct(s['left_frac'])} | {pct(s['cover_black'])} | {pct(s['cover_any'])} | {r['quality']} |")
    if len(rows) > limit:
        out.append(f"| … dalších {len(rows) - limit} | | | | | | |")
    return out


def collateral(res, label):
    out = [f"#### {label}: kolaterální změna", "", "| Skupina | PDF | strany | změna mimo oblasti: průměr / medián / 95. percentil / max (podíl pixelů strany) | plocha oblastí: průměr / 95. perc. / max (podíl strany) | z toho černé výplně (prům.) | velikost souboru ×(medián / max) | `verify_redacted` s problémem |", "|---|---|---|---|---|---|---|---|"]
    sets = [("generic, digital", lambda r: r["group"] == "generic" and r["quality"] == "digital"),
            ("generic, skeny a fotky", lambda r: r["group"] == "generic" and r["quality"] != "digital"),
            ("original (rukopis)", lambda r: r["group"] == "original")]
    for g, sel in sets:
        docs = [r for r in res if sel(r) and "error" not in r]
        if not docs:
            continue
        ch = [float(r["changed_outside"].get(str(p), r["changed_outside"].get(p, 0.0))) for r in docs for p in range(1, r["pages"] + 1)]
        ar = [a for r in docs for a in r["area_any"]]
        af = [a for r in docs for a in r["area_full"]]
        sz = [r["size_red"] / r["size_orig"] for r in docs]
        bad = sum(1 for r in docs if r["verify_problems"])
        out.append(f"| {g} | {len(docs)} | {len(ch)} | {pct(mean(ch))} / {pct(median(ch))} / {pct(perc(ch, .95))} / {pct(max(ch))} | "
                   f"{pct(mean(ar))} / {pct(perc(ar, .95))} / {pct(max(ar))} | {pct(mean(af))} | {median(sz):.2f} / {max(sz):.2f} | {bad} z {len(docs)} |")
    return out + [""]


def verify_list(res):
    out = []
    for r in res:
        if r.get("verify_problems"):
            out.append(f"- {r['file'][:60]}: " + "; ".join(sorted(set(r["verify_problems"]))[:3]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--review")
    ap.add_argument("--list", action="store_true", help="vypíše seznam podpisů, které zůstaly čitelné")
    a = ap.parse_args()
    groups = defaultdict(list)
    for f in a.files:
        groups[re.sub(r"\.shard\d+", "", f)].append(f)       # části souběžného běhu se sloučí
    for f, parts in groups.items():
        res = [r for part in parts for r in json.load(open(part))]
        label = f.rsplit("/", 1)[-1].replace("results_", "").replace(".json", "")
        out, allp = generic_tables(res, label)
        print("\n".join(out))
        print("\n".join(collateral(res, label)))
        if a.list:
            print("\n".join(leftovers(allp)), "\n")
        v = verify_list(res)
        print(f"`verify_redacted` s problémem: {len(v)} dokumentů\n" + "\n".join(v) + "\n")
        n_orig = [r for r in res if r["group"] == "original" and "error" not in r]
        print(f"skupina B: {len(n_orig)} PDF zpracováno, stran k prohlídce: {sum(len(set(r.get('truth_pages', []))) for r in n_orig)}\n")


if __name__ == "__main__":
    main()
