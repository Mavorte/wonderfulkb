"""Vyčítání hodnot z textu dokumentu (číslo smlouvy, výrobní číslo, částky) s odkazem na stranu a citaci.

Text je nedůvěryhodný vstup: tady se jen prochází regulárními výrazy, nikdy se nevykonává ani nepředává jako instrukce.
Strany v textu odděluje znak \\f.
"""
import re
from decimal import Decimal, InvalidOperation

FLAGS = {"i": re.I, "m": re.M, "s": re.S}


def page_of(text, offset):
    return text.count("\f", 0, offset) + 1


def quote_at(text, start, end, limit=160):
    """Řádek (nebo okolí) kolem nálezu, zkrácený a se sjednocenými mezerami."""
    ls = text.rfind("\n", 0, start) + 1
    le = text.find("\n", end)
    le = len(text) if le < 0 else le
    line = re.sub(r"\s+", " ", text[ls:le]).strip()
    if len(line) < 12:   # řádek je jen hodnota: přidej předchozí řádek (popisek)
        ps = text.rfind("\n", 0, max(ls - 1, 0)) + 1
        line = re.sub(r"\s+", " ", text[ps:le]).strip()
    return line[:limit]


def normalize(raw, value_type):
    if value_type == "amount":
        s = re.sub(r"[\s ]", "", raw).replace(",", ".")
        try:
            return str(Decimal(s).quantize(Decimal("0.01")))
        except InvalidOperation:
            return None
    return re.sub(r"[\s-]", "", raw).upper()


def _flags(spec):
    f = 0
    for ch in spec or "":
        f |= FLAGS.get(ch, 0)
    return f


def run_extractors(text, extractors, value_type="id", limit=160):
    """Vrátí seznam {value, raw, page, quote} v pořadí v textu (bez duplicit hodnota+strana)."""
    found = []
    for ex in extractors:
        kind = ex.get("kind")
        if kind == "regex":
            for m in re.finditer(ex["pattern"], text, _flags(ex.get("flags"))):
                s, e = m.span("v") if "v" in m.re.groupindex else m.span()
                found.append((s, e, m.group("v") if "v" in m.re.groupindex else m.group(0)))
        elif kind == "after_label":
            found.extend(_after_label(text, ex))
        else:
            raise ValueError(f"Neznámý extraktor: {kind}")
    out, seen = [], set()
    for s, e, raw in sorted(found):
        val = normalize(raw, value_type)
        if val is None or (val, page_of(text, s)) in seen:
            continue
        seen.add((val, page_of(text, s)))
        out.append({"value": val, "raw": raw.strip(), "page": page_of(text, s), "quote": quote_at(text, s, e, limit)})
    return out


def _after_label(text, ex):
    label = re.compile(ex["label"], _flags(ex.get("flags", "i")))
    token = re.compile(ex["token"])
    exclude = [re.compile(x) for x in ex.get("exclude", [])]
    window = ex.get("window", 10)
    out = []
    for m in label.finditer(text):
        pos, hit = m.end(), None
        stop = text.find("\f", pos)                 # hodnota za popiskem na další straně (zápatí, hlavička) se nebere
        stop = len(text) if stop < 0 else stop
        # řádky od zbytku řádku s popiskem
        for _ in range(window + 1):
            nl = text.find("\n", pos, stop)
            line_end = stop if nl < 0 else nl
            for t in token.finditer(text[pos:line_end]):
                cand = t.group(0)
                if any(x.search(cand) for x in exclude):
                    continue
                hit = (pos + t.start(), pos + t.end(), cand)
                break
            if hit or nl < 0:
                break
            pos = nl + 1
        if hit:
            out.append(hit)
    return out
