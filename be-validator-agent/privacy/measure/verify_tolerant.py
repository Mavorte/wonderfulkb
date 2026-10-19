"""`verify_redacted` bez falešných poplachů na okrajích.

`verify_redacted` hlásí „text v oblasti full“, když `get_text("words", clip=oblast)` vrátí slovo, které oblast jen
škrtne (např. dolní 0,3 b. tištěného jména těsně pod podpisem; redakce text, který leží téměř celý mimo, nechává).
Takové úlomky nejsou podpis ani čitelný obsah oblasti. Tato obálka ponechá chybu jen tehdy, když aspoň
`MIN_OVERLAP` plochy slova leží uvnitř oblasti. Ostatní zjištění (obrázky, kresby, nečistá zóna) se nemění.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymupdf  # noqa: E402
from signature_privacy import verify_redacted  # noqa: E402
from signature_privacy.redact import PAD, _rect  # noqa: E402

MIN_OVERLAP = 0.3
TEXT_PROBLEM = "text v oblasti full"


def real_text_problems(redacted_pdf, regions):
    """Strany, kde v oblasti `full` zůstalo slovo, které v ní leží aspoň z 30 %."""
    bad = []
    doc = pymupdf.open(stream=redacted_pdf, filetype="pdf")
    try:
        for r in regions:
            if r.mode != "full":
                continue
            page = doc[r.page - 1]
            rect = _rect(page, r.bbox, PAD)
            for w in page.get_text("words", clip=rect):
                wr = pymupdf.Rect(w[:4])
                inter = wr & rect
                if wr.get_area() > 0 and inter.get_area() / wr.get_area() >= MIN_OVERLAP:
                    bad.append(r.page)
    finally:
        doc.close()
    return sorted(set(bad))


def verify_tolerant(original_pdf, redacted_pdf, regions):
    """(problémy po odfiltrování okrajových úlomků, počet odfiltrovaných hlášení)."""
    problems = verify_redacted(original_pdf, redacted_pdf, regions)
    text = [p for p in problems if p.endswith(TEXT_PROBLEM)]
    if not text:
        return problems, 0
    bad_pages = set(real_text_problems(redacted_pdf, regions))
    keep = [p for p in problems if not p.endswith(TEXT_PROBLEM) or int(p.split()[1].rstrip(":")) in bad_pages]
    return keep, len(problems) - len(keep)
