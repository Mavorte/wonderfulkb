"""Dělení textu na části vhodné pro Titan Text v2 (limit 8192 tokenů na vstup).

Hranice po odstavcích, pak po větách, až nakonec po slovech. Strany jsou v textu
odděleny `\\f`; každá část nese `page_from` a `page_to` (číslováno od 1).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Titan tokenizer není k dispozici; změřeno (inputTextTokenCount, viz README) vychází česky
# ~2,05 znaku na token. Pro odhad bereme konzervativních 2,0.
CHARS_PER_TOKEN = 2.0
MIN_TOKENS = 500
MAX_TOKENS = 800

_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+")
_PARA_SPLIT = re.compile(r"\n\s*\n")


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    page_from: int
    page_to: int

    @property
    def chunk_id(self) -> str:
        return f"c{self.index}"


def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 1


def _split_long(text: str, max_chars: int) -> list[str]:
    """Rozdělí příliš dlouhý odstavec po větách, dlouhou větu po slovech."""
    parts: list[str] = []
    cur = ""
    for sent in _SENTENCE_END.split(text):
        if len(sent) > max_chars:
            if cur:
                parts.append(cur)
                cur = ""
            words, w_cur = sent.split(), ""
            for w in words:
                while len(w) > max_chars:  # slovo delší než chunk (např. řetězec bez mezer)
                    if w_cur:
                        parts.append(w_cur)
                        w_cur = ""
                    parts.append(w[:max_chars])
                    w = w[max_chars:]
                if w_cur and len(w_cur) + 1 + len(w) > max_chars:
                    parts.append(w_cur)
                    w_cur = w
                else:
                    w_cur = f"{w_cur} {w}" if w_cur else w
            if w_cur:
                parts.append(w_cur)
        elif cur and len(cur) + 1 + len(sent) > max_chars:
            parts.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}" if cur else sent
    if cur:
        parts.append(cur)
    return parts


def split_pages(text: str) -> list[str]:
    pages = text.split("\f")
    # koncové `\f` na konci textu nevytváří další stranu
    while len(pages) > 1 and not pages[-1].strip():
        pages.pop()
    return pages


def chunk_text(text: str, min_tokens: int = MIN_TOKENS, max_tokens: int = MAX_TOKENS) -> list[Chunk]:
    """Vrátí části o ~`min_tokens` až `max_tokens` tokenech; prázdný text nedá žádnou část."""
    max_chars = int(max_tokens * CHARS_PER_TOKEN)
    min_chars = int(min_tokens * CHARS_PER_TOKEN)

    units: list[tuple[str, int]] = []  # (text, strana)
    for page_no, page in enumerate(split_pages(text), start=1):
        for para in _PARA_SPLIT.split(page):
            para = para.strip()
            if not para:
                continue
            if len(para) > max_chars:
                units.extend((p, page_no) for p in _split_long(para, max_chars))
            else:
                units.append((para, page_no))

    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_len = 0
    first_page = last_page = 0

    def flush() -> None:
        nonlocal buf, buf_len
        if buf:
            chunks.append(Chunk(len(chunks), "\n\n".join(buf), first_page, last_page))
        buf, buf_len = [], 0

    for unit, page_no in units:
        added = len(unit) + (2 if buf else 0)
        if buf and buf_len + added > max_chars:
            flush()
            added = len(unit)
        if not buf:
            first_page = page_no
        buf.append(unit)
        buf_len += added
        last_page = page_no
    flush()

    # krátký zbytek na konci připojit k předchozí části, pokud se vejde
    if len(chunks) >= 2 and len(chunks[-1].text) < min_chars // 2:
        prev, last = chunks[-2], chunks[-1]
        if len(prev.text) + 2 + len(last.text) <= max_chars:
            chunks[-2:] = [Chunk(prev.index, f"{prev.text}\n\n{last.text}", prev.page_from, last.page_to)]
    return chunks
