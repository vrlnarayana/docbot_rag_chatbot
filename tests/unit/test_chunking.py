import re

from app.core.chunking import chunk_pages, split_text
from app.core.models import Page


def sentences(n: int, prefix: str = "Sentence") -> str:
    return " ".join(f"{prefix} number {i} talks about brake discs." for i in range(n))


def test_fr_007_short_text_is_one_chunk() -> None:
    assert split_text("Front disc 276 mm.", 800, 100) == ["Front disc 276 mm."]


def test_fr_007_chunks_never_exceed_size() -> None:
    text = sentences(200)
    chunks = split_text(text, 800, 100)
    assert len(chunks) > 1
    assert all(len(c) <= 800 for c in chunks)


def test_fr_007_consecutive_chunks_overlap() -> None:
    chunks = split_text(sentences(200), 800, 100)
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        assert nxt[:40] in prev


def test_fr_007_no_text_is_lost() -> None:
    text = sentences(120)
    joined = " ".join(split_text(text, 800, 100))
    assert set(re.findall(r"\w+", text)) <= set(re.findall(r"\w+", joined))


def test_fr_007_prefers_paragraph_breaks() -> None:
    para1 = sentences(10, "First")  # under 800 chars
    para2 = sentences(10, "Second")
    chunks = split_text(f"{para1}\n\n{para2}", 800, 100)
    assert chunks[0] == para1


def test_fr_007_prefers_line_breaks_over_spaces() -> None:
    lines = "\n".join(f"Row {i} | Front | 276 mm | 3.5 mm" for i in range(60))
    chunks = split_text(lines, 800, 100)
    assert all(c.endswith("3.5 mm") for c in chunks)


def test_fr_007_never_crosses_pages_and_keeps_source() -> None:
    pages = [
        Page(number=1, text="Scope of the brake standard for Velo 125.", source="text"),
        Page(number=2, text="Tensile strength 240 MPa on the certificate.", source="ocr"),
    ]
    chunks = chunk_pages(pages, 800, 100)
    assert [(c.page, c.source) for c in chunks] == [(1, "text"), (2, "ocr")]
    assert "240 MPa" not in chunks[0].text


def test_fr_007_drops_tiny_chunks_unless_only_text() -> None:
    only = chunk_pages([Page(number=1, text="IP67", source="ocr")], 800, 100)
    assert [c.text for c in only] == ["IP67"]
    empty = chunk_pages([Page(number=1, text="   \n ", source="text")], 800, 100)
    assert empty == []
    long_page = sentences(40) + "\n\nEnd."
    chunks = chunk_pages([Page(number=1, text=long_page, source="text")], 800, 100)
    assert all(len(c.text) >= 20 for c in chunks)
