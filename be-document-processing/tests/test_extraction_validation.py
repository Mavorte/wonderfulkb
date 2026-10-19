import pytest

from document_processing.extraction import normalize_value, verify_draft
from document_processing.models import Block, DraftField, Evidence, ExtractionDraft, Page
from document_processing.providers import parse_table
from document_processing.validation import validate_case


def page(text):
    return Page(page_number=1, status="completed", method="vision", width=595, height=842, text=text,
                blocks=[Block(block_id="p1-b1", text=text, bbox=[0.1, 0.1, 0.9, 0.2])])


def extract(text, raw, role=None, quote=None):
    draft = ExtractionDraft(document_type="loan_agreement", warnings=[], fields=[DraftField(
        key="entity.ico", role=role, raw_value=raw, status="extracted",
        evidence=[Evidence(page_number=1, block_id="p1-b1", quote=quote or text, bbox=[0, 0, 1, 1])])])
    return verify_draft(draft, [page(text)])


def test_hallucinated_value_is_not_accepted():
    field = extract("ICO 98007009", "98007106")["fields"][0]
    assert field["status"] == "ambiguous"
    assert field["normalized_value"] is None


def test_role_requires_its_own_source_evidence():
    field = extract("Dodavatel ICO 98007009", "98007009", role="borrower")["fields"][0]
    assert field["status"] == "ambiguous"


def test_model_cannot_invent_geometry_or_repair_ico():
    field = extract("Dluznik ICO 98007009", "98007009", role="borrower")["fields"][0]
    assert field["evidence"][0]["bbox"] == [0.1, 0.1, 0.9, 0.2]
    assert normalize_value("entity.ico", "98O07009") is None


def test_money_decimal_and_date_normalization():
    assert normalize_value("loan.principal", "1 736 000,00 Kč") == "1736000.00"
    assert normalize_value("loan.principal", "1,234") is None
    assert normalize_value("date.issued", "15. 01. 2026") == "2026-01-15"


def test_html_tables_preserve_merged_cell_positions():
    cells = parse_table('<table><tr><th rowspan="2">A</th><th>B</th></tr><tr><td>C</td></tr></table>')
    assert [(c.row, c.column, c.row_span, c.text) for c in cells] == [(0, 0, 2, "A"), (0, 1, 1, "B"), (1, 1, 1, "C")]


def test_client_mismatch_remains_a_finding():
    extraction = extract("Dluznik ICO 98007106", "98007106", role="borrower")
    result = {"document_id": "d1", "run_id": "r1", "extraction": extraction}
    report = validate_case({"case_id": "test", "metadata": {}}, {"client_id": "c1", "ico": "98007009"}, [result], [])
    assert report["findings"][0]["code"] == "BORROWER_ICO_MISMATCH"
    assert extraction["fields"][0]["normalized_value"] == "98007106"


def test_missing_guarantor_is_not_required_without_profile():
    report = validate_case({"case_id": "test", "metadata": {}}, {"client_id": "c1", "ico": "98007009"}, [], [])
    assert report["status"] == "incomplete"
    assert report["findings"] == []
    assert report["completeness_profile"] == "not_configured"
