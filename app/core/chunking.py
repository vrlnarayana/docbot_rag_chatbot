"""Page-aware chunking (FR-007, plan §7.3)."""

from typing import NamedTuple

from app.core.models import Page, Source

MIN_CHUNK_CHARS = 20
# In order of preference. Sentence ends keep their punctuation in the earlier chunk.
_SEPARATORS = ("\n\n", "\n", ". ", "? ", "! ", " ")


class PageChunk(NamedTuple):
    page: int
    source: Source
    text: str


def _cut_point(text: str, start: int, end: int, lowest: int) -> int:
    """Best place to end a chunk inside text[start:end], never before `lowest`."""
    window = text[start:end]
    for sep in _SEPARATORS:
        i = window.rfind(sep)
        if start + i > lowest:
            keep = 1 if sep.strip() else 0  # keep the '.', '?' or '!'
            return start + i + keep
    return end


def _next_start(text: str, start: int, end: int, overlap: int) -> int:
    """Step back by `overlap`, then forward to the start of a line or word."""
    nxt = max(end - overlap, start + 1)
    if nxt < end and not text[nxt - 1].isspace():
        for boundary in ("\n", " "):
            i = text.find(boundary, nxt, end)
            if i != -1:
                return i + 1
    return nxt


def split_text(text: str, size: int, overlap: int) -> list[str]:
    text = text.strip()
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            end = _cut_point(text, start, end, lowest=start + max(overlap, size // 4))
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = _next_start(text, start, end, overlap)
    return chunks


def chunk_pages(pages: list[Page], size: int, overlap: int) -> list[PageChunk]:
    result: list[PageChunk] = []
    for page in pages:
        pieces = split_text(page.text, size, overlap)
        if len(pieces) > 1:
            pieces = [p for p in pieces if len(p) >= MIN_CHUNK_CHARS]
        result.extend(PageChunk(page.number, page.source, p) for p in pieces)
    return result
