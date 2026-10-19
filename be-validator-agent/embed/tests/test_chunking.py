from embed.chunking import CHARS_PER_TOKEN, MAX_TOKENS, MIN_TOKENS, chunk_text, estimate_tokens

MAX_CHARS = int(MAX_TOKENS * CHARS_PER_TOKEN)


def test_empty_text_has_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("  \n\f \n") == []


def test_short_text_single_chunk_with_pages():
    ch = chunk_text("Strana jedna.\fStrana dva.\fStrana tři.")
    assert len(ch) == 1
    assert (ch[0].page_from, ch[0].page_to, ch[0].chunk_id) == (1, 3, "c0")


def test_trailing_formfeed_does_not_add_page():
    ch = chunk_text("A.\fB.\f")
    assert ch[0].page_to == 2


def test_long_text_split_within_limit_on_boundaries():
    para = "Toto je věta číslo %d. " 
    pages = ["\n\n".join(" ".join((para % (p * 100 + i)) for i in range(8)) for _ in range(12))
             for p in range(4)]
    ch = chunk_text("\f".join(pages))
    assert len(ch) > 1
    assert [c.index for c in ch] == list(range(len(ch)))
    for c in ch:
        assert len(c.text) <= MAX_CHARS
        assert estimate_tokens(c.text) <= MAX_TOKENS + 1
        assert 1 <= c.page_from <= c.page_to <= 4
    for a, b in zip(ch, ch[1:]):
        assert b.page_from >= a.page_to
    assert all(len(c.text) >= MIN_TOKENS * CHARS_PER_TOKEN // 2 for c in ch[:-1])


def test_huge_paragraph_splits_on_sentences():
    text = " ".join(f"Věta {i} obsahuje několik slov navíc." for i in range(400))
    ch = chunk_text(text)
    assert len(ch) > 1
    assert all(len(c.text) <= MAX_CHARS for c in ch)
    assert all(c.text.rstrip().endswith(".") for c in ch)  # hranice po větě


def test_unbroken_string_is_hard_split():
    ch = chunk_text("x" * (MAX_CHARS * 3))
    assert len(ch) == 3 and all(len(c.text) <= MAX_CHARS for c in ch)


def test_no_text_lost():
    text = "\n\n".join(f"Odstavec {i}. " + "slovo " * 60 for i in range(60))
    joined = " ".join(c.text for c in chunk_text(text))
    assert all(f"Odstavec {i}." in joined for i in range(60))
