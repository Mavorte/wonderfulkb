"""Builds the mock fixtures in functions/shared/fixtures/ from the case PDF bundles.

Usage (pypdf required, e.g. in a throwaway venv):
    python scripts/build_fixtures.py <kb-hackathon folder>

Each fixture holds the raw upstream records the mock layer serves: the case and
client (openapi-case-client.yaml) and the documents (documents API), each with
its signatures (documents API signatures endpoint). The 99_ system-data PDF is
not a client upload; its values are typed into the client records below. Pages
are joined with a form feed, like the documents API text. Scanned pages get
hand-written OCR text from fixture_extras.py.
"""
import hashlib
import json
import sys
from pathlib import Path

from pypdf import PdfReader

from fixture_extras import CONFIDENCE, OCR, SIGNATURES

OUT = Path(__file__).resolve().parent.parent / "functions" / "shared" / "fixtures"

# Filename prefix -> documents API label.
LABELS = {
    "0": "smlouva_o_uveru",
    "01": "vop",
    "09": "dohoda_o_zaplaceni_kupni_ceny",
    "10": "objednavka",
    "11": "predavaci_protokol",
    "14": "doklad_o_uhrade",
    "2": "zajistovaci_prevod",
    "3": "vinkulace_pojisteni",
    "4": "ruceni",
}

# Stavby Fišer uses different filenames for the same labels.
LABEL_OVERRIDES = {
    "0_F_Smlouva.pdf": "smlouva_o_uveru",
    "11_Protokol_Potvrzeni_o_prechodu_vlastnictvi.pdf": "predavaci_protokol",
}

# The VOP is ~20 pages of standard terms; only its signature page matters, so
# the fixture keeps the last two pages (the re-exported unhappy VOP puts the
# signature text on the second-to-last one) to keep tool output small.
SIGNATURE_PAGES_ONLY = {"vop"}

DIGITAL_CONFIDENCE = 0.98

SOLOM_REC_CLIENT = {
    "client_id": "6f1c2a4e-1b7d-4c8e-9a51-3d0e7f2b9c11",
    "ico": "04606812",
    "dic": "CZ04606812",
    "name": "SOLOM Rec s.r.o.",
    "legal_form": "s.r.o.",
    "address": "nám. Svobody 527, 739 61 Třinec - Lyžbice",
    "status": "active",
    "contacts": [{"name": "Jiří Labuda", "role": "jednatel", "email": "labuda@example.com", "preferred_channel": "email"}],
    "signatories": [{"name": "Jiří Labuda", "function": "jednatel", "authorized": True}],
    "kyc": {"status": "ok", "checked_at": "2026-05-28"},
    "source": "synthetic",
}

SOLOM_REC_METADATA = {
    "loan_number": "170170/25",
    "asset": "Demoliční nůžky Epiroc CC 3100 vč. příslušenství",
    "serial_number": "DGR240020",
}

STAVBY_FISER_CLIENT = {
    "client_id": "9a3d5e71-4c2b-4f8a-b6d0-7e1f2a3b4c55",
    "ico": "25317688",
    "dic": "CZ25317688",
    "name": "Stavby Fišer a.s.",
    "legal_form": "a.s.",
    "address": "Mlýnská 388/68, Trnitá, 602 00 Brno",
    "status": "active",
    "contacts": [{"name": "Vít Juryta", "role": "prokurista", "email": "juryta@example.com", "preferred_channel": "email"}],
    "signatories": [{"name": "Vít Juryta", "function": "prokurista", "authorized": True}],
    "kyc": {"status": "ok", "checked_at": "2026-05-28"},
    "source": "synthetic",
}

STAVBY_FISER_METADATA = {
    "loan_number": "17026014/25",
    "asset": "Tandemový válec BOMAG BW 154 vč. příslušenství",
    "serial_number": "101871101268",
}

FIXTURES = {
    "solom-rec": {"case_id": "mock-solom-rec", "folder": "solom_rec", "client": SOLOM_REC_CLIENT, "metadata": SOLOM_REC_METADATA},
    "unhappy": {"case_id": "mock-unhappy", "folder": "unhappy_scenario", "client": SOLOM_REC_CLIENT, "metadata": SOLOM_REC_METADATA},
    "stavby-fiser": {"case_id": "mock-stavby-fiser", "folder": "stavby_fiser", "client": STAVBY_FISER_CLIENT, "metadata": STAVBY_FISER_METADATA},
}


def label_for(filename: str) -> str:
    return LABEL_OVERRIDES.get(filename) or LABELS[filename.split("_", 1)[0]]


# documents API signatures endpoint format, from compact (page, role, evidence) entries.
def build_signatures(document_id: str, entries: list) -> list:
    return [
        {
            "signature_id": f"sig_{document_id}_{index + 1:02d}",
            "page": page,
            "bbox": None,
            "detector": "textract",
            "detection_score": 72.0,
            "role": role,
            "role_source": "nearest_text",
            "role_evidence": evidence,
            "crop_url": None,
            "phash": None,
            "copy_suspicion": {"level": "none", "matches": []},
            "similar_signatures": [],
        }
        for index, (page, role, evidence) in enumerate(entries)
    ]


def build_document(name: str, case_id: str, path: Path) -> dict:
    label = label_for(path.name)
    pages = [(page.extract_text() or "").strip() for page in PdfReader(path).pages]
    if label in SIGNATURE_PAGES_ONLY:
        pages = pages[-2:]
    for page, text in OCR.get((name, path.name), {}).items():
        pages[page - 1] = text
    document_id = hashlib.sha1(f"{case_id}/{path.name}".encode()).hexdigest()[:6]
    return {
        "document_id": document_id,
        "title": path.name,
        "label": label,
        "label_status": "predicted",
        "processing_status": "completed",
        "page_count": len(pages),
        "description": None,
        "text": "\f".join(pages),
        # Stand-in for the OCR confidence: digital PDFs read reliably, scans are set in fixture_extras.py.
        "confidence": CONFIDENCE.get((name, path.name), DIGITAL_CONFIDENCE),
        "pages_failed": [],
        "signatures": build_signatures(document_id, SIGNATURES.get((name, path.name), [])),
    }


def main(root: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, spec in FIXTURES.items():
        folder = root / spec["folder"]
        documents = [build_document(name, spec["case_id"], p) for p in sorted(folder.glob("*.pdf")) if not p.name.startswith("99_")]
        fixture = {
            "case": {
                "case_id": spec["case_id"],
                "client_id": spec["client"]["client_id"],
                "status": "open",
                "created_at": "2026-10-19T09:00:00Z",
                "metadata": spec["metadata"],
            },
            "client": spec["client"],
            "documents": documents,
        }
        target = OUT / f"{name}.json"
        target.write_text(json.dumps(fixture, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{target.name}: {len(documents)} documents, {target.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
