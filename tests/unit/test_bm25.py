from app.adapters.retriever_bm25 import Bm25Retriever
from app.core.models import Chunk, IndexedChunk
from app.core.text import tokenize


def ic(i: int, text: str, filename: str = "f.txt") -> IndexedChunk:
    return IndexedChunk(
        chunk=Chunk(id=f"c{i}", document_id="d", page=1, ordinal=i, source="text", text=text),
        filename=filename,
    )


CORPUS = [
    ic(0, "Brake fluid DOT 4, replace every 2 years or 20,000 km."),
    ic(1, "Front | 276 mm | 3.5 mm minimum thickness of the front brake disc."),
    ic(2, "Recommended tyre pressure solo rider: front 29 psi, rear 33 psi."),
    ic(3, "Peak handlebar vibration 18.2 m/s2 at 6,500 rpm. Verdict PASS."),
    ic(4, "Engine oil SAE 10W-30, capacity 1.0 L."),
]


def test_tokenize_drops_question_words_and_plurals() -> None:
    assert tokenize("How many pistons does the front brake caliper have?") == [
        "piston", "front", "brake", "caliper",
    ]
    assert tokenize("What is the DOT 4 fluid?") == ["dot", "4", "fluid"]


def test_fr_011_keyword_retriever_ranks_matching_chunk_first() -> None:
    r = Bm25Retriever(min_score=1.0)
    r.refresh(CORPUS)
    hits = r.search("What is the recommended rear tyre pressure?", 4)
    assert hits[0].chunk.id == "c2"
    assert all(hits[0].score >= h.score for h in hits)
    assert hits[0].filename == "f.txt"


def test_fr_010_returns_at_most_k_with_positive_scores() -> None:
    r = Bm25Retriever(min_score=1.0)
    r.refresh(CORPUS)
    hits = r.search("front brake disc thickness", 2)
    assert len(hits) <= 2
    assert all(h.score > 0 for h in hits)


def test_no_match_and_empty_index_return_nothing() -> None:
    r = Bm25Retriever(min_score=1.0)
    assert r.search("anything at all", 4) == []
    r.refresh(CORPUS)
    assert r.search("zebra xylophone", 4) == []
    assert r.search("what is the", 4) == []


def test_refresh_replaces_index() -> None:
    r = Bm25Retriever(min_score=1.0)
    r.refresh(CORPUS)
    r.refresh(CORPUS[:2])
    assert all(h.chunk.id in {"c0", "c1"} for h in r.search("tyre pressure rear", 4))
