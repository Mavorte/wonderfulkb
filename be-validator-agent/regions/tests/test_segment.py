import pymupdf

from conftest import hline, text
from region_pipeline.segment import document_regions


def regions_of(doc, page=1):
    return [r for r in document_regions(doc)["regions"] if r["page"] == page]


def by_text(regions, needle):
    hits = [r for r in regions if needle in r["text"]]
    assert len(hits) == 1, (needle, [r["text"] for r in regions])
    return hits[0]


def a4(doc):
    return doc.new_page(width=595, height=842)


def test_close_lines_form_one_paragraph_and_gap_splits(new_doc):
    doc = new_doc()
    page = a4(doc)
    for i, line in enumerate(["První řádek prvního odstavce, který pokračuje", "druhým řádkem a končí tady."]):
        text(page, (70, 200 + i * 12), line)
    text(page, (70, 250), "Druhý odstavec je oddělený prázdným řádkem.")
    regions = regions_of(doc)
    first = by_text(regions, "První řádek")
    assert first["kind"] == "paragraph"
    assert first["text"] == "První řádek prvního odstavce, který pokračuje druhým řádkem a končí tady."
    assert by_text(regions, "Druhý odstavec")["region_id"] != first["region_id"]


def test_list_items_with_separate_marker_and_hanging_indent(new_doc):
    doc = new_doc()
    page = a4(doc)
    text(page, (70, 200), "Příjemce je povinen předložit tyto podklady:")
    text(page, (72, 214), "a)")
    text(page, (100, 214), "kopii daňového dokladu dodavatele obsahujícího detailní")
    text(page, (100, 226), "specifikaci předmětu financování,")
    text(page, (72, 240), "b)")
    text(page, (100, 240), "kopii kupní smlouvy nebo potvrzené objednávky,")
    text(page, (70, 254), "Poskytnutí úvěru je dále vázáno na podmínku úhrady.")
    regions = regions_of(doc)
    a = by_text(regions, "daňového dokladu")
    assert a["kind"] == "list_item"
    assert a["text"] == "a) kopii daňového dokladu dodavatele obsahujícího detailní specifikaci předmětu financování,"
    assert by_text(regions, "kupní smlouvy")["text"].startswith("b) ")
    # Odstavec za výčtem začíná vlevo od textu položky, do položky b) nepatří.
    assert by_text(regions, "Poskytnutí úvěru")["kind"] == "paragraph"


def test_two_columns_stay_apart(new_doc):
    doc = new_doc()
    page = a4(doc)
    for i, (left, right) in enumerate([("SG Finance s.r.o.", "SOLOM Rec s.r.o."),
                                       ("náměstí Junkových 2772/1", "nám. Svobody 527"),
                                       ("155 00 Praha 5", "739 61 Třinec")]):
        text(page, (80, 200 + i * 12), left)
        text(page, (302, 200 + i * 12), right)
    regions = regions_of(doc)
    left = by_text(regions, "SG Finance")
    assert left["text"] == "SG Finance s.r.o. náměstí Junkových 2772/1 155 00 Praha 5"
    assert by_text(regions, "SOLOM")["text"] == "SOLOM Rec s.r.o. nám. Svobody 527 739 61 Třinec"


def test_label_and_value_join(new_doc):
    doc = new_doc()
    page = a4(doc)
    text(page, (80, 200), "IČ:")
    text(page, (116, 200), "61061344")
    text(page, (80, 300), "Výrobní číslo:")
    text(page, (400, 300), "DGR240020")
    regions = regions_of(doc)
    ico = by_text(regions, "61061344")
    assert ico["text"] == "IČ: 61061344" and ico["kind"] == "paragraph"
    serial = by_text(regions, "DGR240020")
    # Hodnota daleko vpravo: řádek formuláře, samostatný region.
    assert serial["text"] == "Výrobní číslo: DGR240020" and serial["kind"] == "table_row"


def test_table_rows_between_rules_even_when_drawn_per_cell(new_doc):
    doc = new_doc()
    page = a4(doc)
    rows = [("Dodavatel / prodávající", "Valdorin Stroje s.r.o."), ("IČO / DIČ", "98000136 / CZ98000136")]
    y = 200
    for label, value in rows:
        for x0, x1 in ((40, 218), (218, 555)):  # čára nakreslená po buňkách
            hline(page, y, x0, x1)
        text(page, (47, y + 14), label, size=8, bold=True)
        text(page, (225, y + 14), value, size=8.5)
        y += 21
    hline(page, y)
    regions = regions_of(doc)
    supplier = by_text(regions, "Valdorin")
    assert supplier["kind"] == "table_row"
    assert supplier["text"] == "Dodavatel / prodávající | Valdorin Stroje s.r.o."
    assert by_text(regions, "98000136")["text"] == "IČO / DIČ | 98000136 / CZ98000136"


def test_cell_rules_shorter_than_min_rule_are_merged(new_doc):
    doc = new_doc()
    page = a4(doc)
    cells = [(40, 140), (140, 240), (240, 340), (340, 440)]  # každá buňka ~17 % šířky strany
    for y in (200, 230):
        for x0, x1 in cells:
            hline(page, y, x0, x1)
    for (x0, _), label in zip(cells, ["Výše splátek", "Frekvence", "Splatnost", "Počet"]):
        text(page, (x0 + 5, 219), label, bold=True)
    row = by_text(regions_of(doc), "Frekvence")
    assert row["kind"] == "table_row"
    assert row["text"] == "Výše splátek | Frekvence | Splatnost | Počet"


def test_heading_but_not_bold_amount(new_doc):
    doc = new_doc()
    page = a4(doc)
    text(page, (70, 200), "PŘEDMĚT FINANCOVÁNÍ:", bold=True)
    text(page, (70, 230), "Demoliční nůžky Epiroc CC 3100")
    text(page, (70, 260), "1 620 000,00 CZK", bold=True)
    regions = regions_of(doc)
    assert by_text(regions, "PŘEDMĚT")["kind"] == "heading"
    assert by_text(regions, "1 620 000")["kind"] == "paragraph"


def test_repeated_header_and_footer(new_doc):
    doc = new_doc()
    for n in (1, 2):
        page = a4(doc)
        text(page, (40, 40), "Nerovex Finance s.r.o.")
        text(page, (70, 400), f"Obsah strany {n} je jiný na každé straně dokumentu.")
        text(page, (540, 815), f"{n} / 2", size=7)
    for n in (1, 2):
        regions = regions_of(doc, n)
        assert by_text(regions, "Nerovex")["kind"] == "page_header"
        assert by_text(regions, " / 2")["kind"] == "page_footer"
        assert by_text(regions, "Obsah strany")["kind"] == "paragraph"


def test_page_without_text_layer(new_doc):
    doc = new_doc()
    page = a4(doc)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), False)
    pix.clear_with(200)
    page.insert_image(page.rect, pixmap=pix)
    result = document_regions(doc)
    assert result["pages"] == [{"page": 1, "width": 595.0, "height": 842.0, "source": "no_text_layer"}]
    assert result["regions"] == []


def test_bbox_follows_rotation(new_doc):
    doc = new_doc()
    page = a4(doc)
    text(page, (40, 60), "Text v levém horním rohu nerotované strany")
    page.set_rotation(90)
    (region,) = regions_of(doc)
    x0, y0, x1, y1 = region["bbox"]
    # Po otočení o 90° doprava je levý horní roh vpravo nahoře a text běží shora dolů.
    assert x0 > 0.8 and y0 < 0.2 and (y1 - y0) > (x1 - x0)
    assert all(0 <= v <= 1 for v in region["bbox"])


def test_ids_order_and_line_offsets(new_doc):
    doc = new_doc()
    page = a4(doc)
    text(page, (70, 300), "Spodní odstavec.")
    text(page, (70, 200), "Horní odstavec, první řádek")
    text(page, (70, 212), "a jeho druhý řádek.")
    regions = regions_of(doc)
    assert [r["region_id"] for r in regions] == ["p1-r01", "p1-r02"]
    assert regions[0]["text"].startswith("Horní")
    for r in regions:
        for line in r["lines"]:
            assert r["text"][line["start"]:line["end"]].strip()
            assert r["bbox"][0] <= line["bbox"][0] and line["bbox"][2] <= r["bbox"][2]
    assert document_regions(doc) == document_regions(doc)
