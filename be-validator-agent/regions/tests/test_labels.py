import pytest

from region_pipeline import labels
from region_pipeline.labels import build_prompt, label_regions, label_with_rules, output_schema


def region(rid, text, kind="paragraph", page=1):
    return {"region_id": rid, "page": page, "kind": kind, "text": text, "bbox": [0.1, 0.1, 0.9, 0.2], "lines": []}


def doc(*regions):
    return {"version": 1, "pages": [], "regions": list(regions)}


SUPPLIER = [
    region("p1-r01", "PŘEDMĚT FINANCOVÁNÍ A DODAVATEL", kind="heading"),
    region("p1-r02", "Výrobní číslo | VV2600000005", kind="table_row"),
    region("p1-r03", "Dodavatel | Valdorin Stroje s.r.o.", kind="table_row"),
    region("p1-r04", "IČO dodavatele | 98000136", kind="table_row"),
    region("p1-r05", "Kupní cena bez DPH | 4 632 000,00 CZK", kind="table_row"),
]

PODKLADY = [
    region("p2-r01", "Příjemce financování je povinen před čerpáním úvěru předložit poskytovateli financování níže "
                     "uvedené podklady vztahující se ke smlouvě o úvěru:"),
    region("p2-r02", "a) kopii daňového dokladu dodavatele obsahujícího specifikaci předmětu,", kind="list_item"),
    region("p2-r03", "b) kopii kupní smlouvy nebo dodavatelem potvrzené objednávky,", kind="list_item"),
    region("p2-r04", "Smlouva č. 170170/25", kind="page_footer"),
    region("p2-r05", "c) kopii oboustranně podepsaného dokladu o předání a převzetí předmětu,", kind="list_item"),
]


class FakeBackend:
    name, model_id = "fake", "fake-1"

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []
        self.usage = {}

    def complete_json(self, system, user, schema, limiter=None):
        self.prompts.append(user)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_rules_party_carries_to_rows_below_and_stops_at_other_label():
    out = label_with_rules(SUPPLIER)
    assert out["p1-r03"] == {"label": "smluvni_strana", "label_source": "rules", "party": "supplier"}
    assert out["p1-r04"]["party"] == "supplier"
    assert out["p1-r02"]["label"] == "predmet"
    assert out["p1-r05"]["label"] == "cena_platba" and "party" not in out["p1-r05"]


def test_rules_list_items_under_podklady_get_refers_to():
    out = label_with_rules(PODKLADY)
    assert out["p2-r01"]["label"] == "povinny_podklad"
    assert out["p2-r02"]["refers_to"] == ["faktura"]
    assert out["p2-r03"]["refers_to"] == ["objednavka"]
    # Zápatí mezi položkami výčet nepřeruší a samo je `jine`.
    assert out["p2-r04"]["label"] == "jine"
    assert out["p2-r05"] == {"label": "povinny_podklad", "label_source": "rules", "refers_to": ["predavaci_protokol"]}


def test_rules_long_sentence_starting_with_party_is_not_a_party():
    out = label_with_rules([region("p1-r01", "Příjemce financování je povinen splácet úvěr a úroky z poskytnutých "
                                             "plateb v souladu s podmínkami uvedenými ve smlouvě o úvěru a ve VOP.")])
    assert out["p1-r01"]["label"] != "smluvni_strana"


def test_llm_answer_is_validated_and_gaps_fall_back_to_rules():
    answer = {"regions": [
        {"id": "p1-r03", "label": "smluvni_strana", "party": "supplier", "summary": "Dodavatel stroje."},
        {"id": "p1-r04", "label": "neexistujici_stitek"},                       # mimo taxonomii → záloha
        {"id": "p1-r05", "label": "cena_platba", "party": "buyer", "refers_to": ["faktura"]},  # party/refers zahodit
        {"id": "p9-r99", "label": "jine"},                                      # cizí id
        {"id": "p1-r03", "label": "jine"},                                      # duplicita, platí první
    ]}
    result = doc(*SUPPLIER)
    stats = label_regions(result, backend=FakeBackend([answer]))
    by_id = {r["region_id"]: r for r in result["regions"]}
    assert by_id["p1-r03"]["label_source"] == "llm" and by_id["p1-r03"]["party"] == "supplier"
    assert by_id["p1-r03"]["summary"] == "Dodavatel stroje."
    assert by_id["p1-r04"]["label_source"] == "rules" and by_id["p1-r04"]["party"] == "supplier"
    assert by_id["p1-r05"]["label"] == "cena_platba" and "party" not in by_id["p1-r05"] and "refers_to" not in by_id["p1-r05"]
    assert stats == {"calls": 1, "llm": 2, "rules": 3, "errors": [], "missing": 3}


def test_llm_refers_to_filtered_to_document_labels_and_backfilled():
    answer = {"regions": [
        {"id": "p2-r02", "label": "povinny_podklad", "refers_to": ["faktura", "faktura", "neznamy_doklad"]},
        {"id": "p2-r03", "label": "povinny_podklad", "refers_to": []},
    ]}
    result = doc(*PODKLADY)
    label_regions(result, backend=FakeBackend([answer]))
    by_id = {r["region_id"]: r for r in result["regions"]}
    assert by_id["p2-r02"]["refers_to"] == ["faktura"]
    assert by_id["p2-r03"]["refers_to"] == ["objednavka"]  # prázdný seznam doplnila záloha


def test_failed_call_falls_back_and_is_reported():
    result = doc(*PODKLADY)
    stats = label_regions(result, backend=FakeBackend([RuntimeError("Throttled")]))
    assert all(r["label_source"] == "rules" for r in result["regions"])
    assert stats["errors"] == ["RuntimeError: Throttled"] and stats["llm"] == 0


def test_batches_carry_last_heading_and_skip_furniture(monkeypatch):
    monkeypatch.setattr(labels, "BATCH", 2)
    result = doc(*SUPPLIER, *PODKLADY)
    backend = FakeBackend([{"regions": []}] * 5)
    stats = label_regions(result, backend=backend)
    assert stats["calls"] == 5  # 9 regionů bez zápatí po dvou
    assert all("Smlouva č. 170170/25" not in p for p in backend.prompts)
    assert "Předchozí nadpis (kontext, neštítkuj): PŘEDMĚT FINANCOVÁNÍ A DODAVATEL" in backend.prompts[1]


def test_prompt_has_ids_and_text_but_no_coordinates():
    prompt = build_prompt(SUPPLIER, None, doc_label="smlouva_o_uveru")
    assert "[p1-r03] (table_row) Dodavatel | Valdorin Stroje s.r.o." in prompt
    assert "bbox" not in prompt and "0.1" not in prompt
    assert "[p1-r01] (heading) PŘEDMĚT" in prompt  # přes celou šířku: bez sloupce
    assert "Typ dokumentu: smlouva_o_uveru" in prompt


def test_sections_point_to_last_heading():
    result = doc(*SUPPLIER)
    label_regions(result)
    assert result["regions"][0]["section"] is None
    assert {r["section"] for r in result["regions"][1:]} == {"p1-r01"}


def test_schema_enums_match_taxonomies():
    props = output_schema()["properties"]["regions"]["items"]["properties"]
    assert "povinny_podklad" in props["label"]["enum"]
    assert "supplier" in props["party"]["enum"]
    assert "faktura" in props["refers_to"]["items"]["enum"] and "jine" not in props["refers_to"]["items"]["enum"]


@pytest.mark.parametrize("text, party", [("Dodavatel / prodávající | X", "supplier"), ("IČO dodavatele | 1", "supplier"),
                                         ("Příjemce financování / dlužník | Y", "borrower"), ("Sídlo | Z", None)])
def test_party_of(text, party):
    assert labels.party_of(text) == party


def test_prompt_marks_columns():
    left = dict(region("p1-r05", "SG Equipment Finance Czech Republic s.r.o."), bbox=[0.13, 0.2, 0.46, 0.21])
    right = dict(region("p1-r06", "SOLOM Rec s.r.o."), bbox=[0.51, 0.2, 0.64, 0.21])
    prompt = build_prompt([left, right], None)
    assert "[p1-r05] (paragraph, vlevo) SG Equipment" in prompt
    assert "[p1-r06] (paragraph, vpravo) SOLOM" in prompt


def test_reference_row_is_not_a_required_document():
    out = label_with_rules([region("p8-r05", "Smlouva o úvěru č. | 861005/26", kind="table_row", page=8)])
    assert out["p8-r05"] == {"label": "odkaz_na_dokument", "label_source": "rules", "refers_to": ["smlouva_o_uveru"]}


def test_required_documents_only_in_loan_documentation():
    answer = {"regions": [{"id": "p2-r02", "label": "povinny_podklad", "refers_to": ["faktura"]}]}
    result = doc(*PODKLADY)
    label_regions(result, backend=FakeBackend([answer]), doc_label="objednavka")
    assert all(r["label"] != "povinny_podklad" for r in result["regions"])
    result = doc(*PODKLADY)
    label_regions(result, backend=FakeBackend([answer]), doc_label="smlouva_o_uveru")
    assert {r["region_id"]: r["label_source"] for r in result["regions"]}["p2-r02"] == "llm"
