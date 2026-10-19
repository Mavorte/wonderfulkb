"""Čisté metrické funkce evaluace (bez sítě a bez AWS), aby šly testovat samostatně."""
import math
import re
import unicodedata

# ---- obecné --------------------------------------------------------------


def wilson(k, n, z=1.96):
    """95% Wilsonův interval podílu k/n; (None, None) pro n = 0."""
    if n <= 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - m) / d), min(1.0, (c + m) / d)


def ratio(k, n):
    """Podíl jako slovník {k, n, value, ci95} (value None pro n = 0)."""
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "value": (k / n if n else None), "ci95": [lo, hi]}


def percentile(values, q):
    """Percentil metodou nejbližšího pořadí (q v 0 až 100); None pro prázdný seznam."""
    if not values:
        return None
    s = sorted(values)
    idx = max(0, min(len(s) - 1, math.ceil(q / 100 * len(s)) - 1))
    return s[idx]


def mean(values):
    return sum(values) / len(values) if values else None


def norm_text(s):
    """Malá písmena, bez diakritiky, jen alfanumerické znaky bez mezer (pro hledání hodnot v textu)."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    return re.sub(r"[^0-9a-z]+", "", s)


def norm_name(s):
    """Název souboru pro porovnání: bez diakritiky, malá písmena, nealfanumerické znaky jako `_`."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    return re.sub(r"[^0-9a-z]+", "_", s).strip("_")


def field_found(value, text_norm):
    """Hodnota pole (např. „98000110 / CZ98000110“) je v textu, když se najde její první část."""
    first = str(value).split(" / ")[0]
    n = norm_text(first)
    return bool(n) and n in text_norm


# ---- štítky a kalibrace ---------------------------------------------------

CONF_BINS = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.0001)]


def calibration(items):
    """items: [(confidence, correct: bool)]. Průměrná jistota u správných a špatných, koše, ECE, Brier."""
    ok = [c for c, y in items if y]
    bad = [c for c, y in items if not y]
    bins = []
    ece = 0.0
    n = len(items)
    for lo, hi in CONF_BINS:
        sel = [(c, y) for c, y in items if lo <= c < hi]
        if sel:
            acc = sum(1 for _, y in sel if y) / len(sel)
            conf = mean([c for c, _ in sel])
            ece += len(sel) / n * abs(acc - conf)
        else:
            acc = conf = None
        bins.append({"range": [lo, min(hi, 1.0)], "n": len(sel), "accuracy": acc, "mean_confidence": conf})
    brier = mean([(c - (1.0 if y else 0.0)) ** 2 for c, y in items])
    return {
        "n": n, "n_correct": len(ok), "n_wrong": len(bad),
        "mean_confidence_correct": mean(ok), "mean_confidence_wrong": mean(bad),
        "gap": (mean(ok) - mean(bad)) if ok and bad else None,
        "ece": ece if n else None, "brier": brier, "bins": bins,
    }


# ---- podpisy --------------------------------------------------------------


def _area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _inter(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def iou(a, b):
    i = _inter(a, b)
    u = _area(a) + _area(b) - i
    return i / u if u > 0 else 0.0


def _contained(a, b, min_in=0.8, max_ratio=4.0):
    """Menší box je z >= 80 % uvnitř většího a plochy se liší nejvýše 4×: těsný nález uvnitř zadané oblasti
    podpisu (nebo mírně větší box okolo ní) je nález na správném místě, i když IoU nevychází."""
    aa, ab = _area(a), _area(b)
    small, large = min(aa, ab), max(aa, ab)
    if small <= 0 or large / small > max_ratio:
        return False
    return _inter(a, b) / small >= min_in


def valid_bbox(b):
    return (isinstance(b, (list, tuple)) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b)
            and all(0 <= v <= 1 for v in b) and b[0] < b[2] and b[1] < b[3])


def match_signatures(truth, found, thr=0.3):
    """Spáruje očekávané podpisy s nalezenými.

    truth: [{page, bbox|None, role}], found: [{page, bbox|None, role, ...}]. Dvojice musí mít stejnou stranu a
    IoU >= thr, nebo menší box z >= 80 % uvnitř většího při poměru ploch do 4 (jedna ku jedné, hladově od
    nejvyššího IoU). Bez bbox (pravda na úrovni strany, nález bez bbox) se
    zbylé položky na téže straně spárují podle počtu. Nespárovaný nález je `duplicate_or_merged`, když se
    překrývá s nějakým očekávaným podpisem (nejčastěji jeden box přes dva podpisy, nebo dva boxy na jednom),
    jinak `spurious` (falešný nález). `covered` = očekávaný podpis, jehož plocha je z >= 50 % uvnitř nějakého
    nalezeného boxu (mírnější kritérium než IoU, odlišuje „našel se, ale box je sloučený / příliš velký“).
    """
    cand = []
    for ti, t in enumerate(truth):
        for fi, f in enumerate(found):
            if t["page"] != f.get("page") or not valid_bbox(t.get("bbox")) or not valid_bbox(f.get("bbox")):
                continue
            v = iou(t["bbox"], f["bbox"])
            if v >= thr or _contained(t["bbox"], f["bbox"]):
                cand.append((v, ti, fi))
    cand.sort(reverse=True)
    t_used, f_used, pairs = set(), set(), []
    for v, ti, fi in cand:
        if ti in t_used or fi in f_used:
            continue
        t_used.add(ti)
        f_used.add(fi)
        pairs.append((ti, fi, v))
    # úroveň strany pro položky bez použitelného bbox
    for ti, t in enumerate(truth):
        if ti in t_used:
            continue
        for fi, f in enumerate(found):
            if fi in f_used or t["page"] != f.get("page"):
                continue
            if not (valid_bbox(t.get("bbox")) and valid_bbox(f.get("bbox"))):
                t_used.add(ti)
                f_used.add(fi)
                pairs.append((ti, fi, None))
                break
    spurious, dup = [], []
    for fi, f in enumerate(found):
        if fi in f_used:
            continue
        overl = False
        for t in truth:
            if t["page"] == f.get("page") and valid_bbox(t.get("bbox")) and valid_bbox(f.get("bbox")):
                if _inter(t["bbox"], f["bbox"]) / max(_area(f["bbox"]), 1e-9) >= 0.3 or \
                        _inter(t["bbox"], f["bbox"]) / max(_area(t["bbox"]), 1e-9) >= 0.3:
                    overl = True
                    break
        (dup if overl else spurious).append(fi)
    covered = set(t_used)
    for ti, t in enumerate(truth):
        if ti in covered or not valid_bbox(t.get("bbox")):
            continue
        for f in found:
            if f.get("page") == t["page"] and valid_bbox(f.get("bbox")) and \
                    _inter(t["bbox"], f["bbox"]) / max(_area(t["bbox"]), 1e-9) >= 0.5:
                covered.add(ti)
                break
    return {"pairs": pairs, "missed": [i for i in range(len(truth)) if i not in t_used],
            "spurious": spurious, "duplicate_or_merged": dup, "covered": sorted(covered)}


LENIENT = {"buyer": "borrower"}  # kupující a dlužník bývá táž strana; jiný typ dokumentu = jiný název role


def role_match(truth_role, found_role):
    """('exact'|'lenient'|'unknown'|'wrong')."""
    if found_role in (None, "unknown"):
        return "unknown"
    if found_role == truth_role:
        return "exact"
    if LENIENT.get(found_role, found_role) == LENIENT.get(truth_role, truth_role):
        return "lenient"
    return "wrong"


def apply_removed(truth_sigs, removed):
    """Odebere z očekávaných podpisů ty, které varianta dokumentu záměrně odstranila.

    removed: [{page, role?, index?}]. Odebírá se první dosud neodebraný podpis na straně (a s rolí, je-li uvedena).
    """
    left = list(truth_sigs)
    gone = []
    for r in removed or []:
        for i, s in enumerate(left):
            if s["page"] == r.get("page") and (not r.get("role") or s.get("role") == r["role"]):
                gone.append(left.pop(i))
                break
    return left, gone
