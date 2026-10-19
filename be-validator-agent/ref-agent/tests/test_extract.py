from refagent import extract


def test_amount_normalization_and_page():
    t = "úvod\n\fCena celkem bez DPH:\n4 034 900,00 CZK\n"
    ex = [{"kind": "after_label", "label": r"Cena\s+celkem\s+bez\s+DPH\s*:?", "window": 3,
           "token": r"(?<![\d.,])\d{1,3}(?:[  ]\d{3})+[,.]\d{2}(?![\d])"}]
    (v,) = extract.run_extractors(t, ex, "amount")
    assert v["value"] == "4034900.00" and v["page"] == 2 and "4 034 900,00" in v["quote"]


def test_serial_after_label_skips_dic_and_short_numbers():
    t = "Výrobní číslo:\nVýrobce: Rok\nDIČ: CZ26762855\n12345678\nDGR240020\n"
    ex = [{"kind": "after_label", "label": r"výrobní\s+číslo\s*:?", "window": 12,
           "token": r"(?<![\w/,.-])(?=[A-Z0-9-]*\d)[A-Z0-9-]{7,20}(?![\w/,.-])", "exclude": [r"^CZ\d{8,10}$", r"^\d{1,9}$"]}]
    assert [v["value"] for v in extract.run_extractors(t, ex)] == ["DGR240020"]


def test_blank_value_gives_nothing():
    t = "Výrobní číslo:\nR. v.:\nStav:\n"
    ex = [{"kind": "after_label", "label": r"výrobní\s+číslo\s*:?", "window": 12, "token": r"(?=[A-Z0-9-]*\d)[A-Z0-9-]{7,20}"}]
    assert extract.run_extractors(t, ex) == []


def test_label_value_does_not_cross_page_break():
    t = "Výrobní číslo\n\fSYNTETICKÝ DOKUMENT SYN-B01 / objednavka\nDalší text"
    ex = [{"kind": "after_label", "label": r"výrobní\s+číslo", "window": 12, "token": r"(?=[A-Z0-9-]*\d)[A-Z0-9-]{5,20}"}]
    assert extract.run_extractors(t, ex) == []
