from app.core.answerability import AnswerabilityGate
from app.core.models import Chunk, GeneratedAnswer, RetrievedChunk
from app.core.services import EMPTY_LIBRARY, REFUSAL, QAService
from tests.conftest import FakeGenerator

TEXTS = [
    "Front | 276 mm | 3.5 mm minimum thickness of the front brake disc.",
    "Brake fluid DOT 4, replace every 2 years.",
]


def rc(i: int, score: float = 5.0) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=Chunk(id=f"c{i}", document_id=f"d{i}", page=i + 1, ordinal=i, source="text",
                    text=TEXTS[i]),
        filename=f"file{i}.pdf",
        score=score,
    )


class FakeRepo:
    def __init__(self, chunks: int) -> None:
        self.n = chunks

    async def counts(self) -> tuple[int, int]:
        return (1 if self.n else 0), self.n


class FakeRetriever:
    name = "keyword"
    min_score = 1.0

    def __init__(self, hits: list[RetrievedChunk]) -> None:
        self.hits = hits
        self.calls: list[tuple[str, int]] = []

    def refresh(self, chunks: object) -> None: ...

    def search(self, question: str, k: int) -> list[RetrievedChunk]:
        self.calls.append((question, k))
        return self.hits[:k]


class ScriptedGenerator:
    def __init__(self, text: str, cited: list[int], name: str = "ollama") -> None:
        self.name = name
        self.answer = GeneratedAnswer(text=text, cited=cited, grounded=True, generator_used=name)

    async def generate(self, question: str, chunks: list[RetrievedChunk]) -> GeneratedAnswer:
        return self.answer


def service(
    retriever: FakeRetriever, generator: object, chunks: int = 2, fallback: object = None
) -> QAService:
    gate = AnswerabilityGate()
    gate.refresh(TEXTS)
    return QAService(
        repository=FakeRepo(chunks),  # type: ignore[arg-type]
        retriever=retriever,
        generator=generator,  # type: ignore[arg-type]
        gate=gate,
        min_coverage=0.55,
        fallback=fallback,  # type: ignore[arg-type]
    )


Q = "What is the minimum thickness of the front brake disc?"


async def test_fr_018_empty_library_suggests_samples_without_retrieval() -> None:
    retriever, gen = FakeRetriever([rc(0)]), FakeGenerator()
    resp = await service(retriever, gen, chunks=0).ask(Q, 4)
    assert resp.answer == EMPTY_LIBRARY and "sample" in resp.answer.lower()
    assert resp.grounded is False and resp.citations == []
    assert resp.generator_used == "none"
    assert retriever.calls == [] and gen.calls == 0


async def test_fr_012_low_score_refuses_without_calling_generator() -> None:
    gen = FakeGenerator()
    resp = await service(FakeRetriever([rc(0, score=0.5)]), gen).ask(Q, 4)
    assert resp.answer == REFUSAL == "I couldn't find this in the uploaded documents."
    assert (resp.grounded, resp.citations, resp.generator_used) == (False, [], "none")
    assert gen.calls == 0


async def test_fr_012_no_hits_refuses() -> None:
    resp = await service(FakeRetriever([]), FakeGenerator()).ask(Q, 4)
    assert resp.answer == REFUSAL


async def test_fr_012_low_coverage_refuses_without_calling_generator() -> None:
    gen = FakeGenerator()
    resp = await service(FakeRetriever([rc(0)]), gen).ask("What is the top speed of the bike?", 4)
    assert resp.answer == REFUSAL and gen.calls == 0


async def test_fr_010_passes_top_k_to_retriever() -> None:
    retriever = FakeRetriever([rc(0), rc(1)])
    await service(retriever, FakeGenerator()).ask(Q, 7)
    assert retriever.calls == [(Q, 7)]


async def test_fr_013_fr_014_answer_with_full_citation() -> None:
    resp = await service(FakeRetriever([rc(0), rc(1)]), FakeGenerator()).ask(Q, 4)
    assert resp.grounded is True
    assert resp.generator_used == "fake" and resp.retriever == "keyword"
    [c] = resp.citations
    assert (c.n, c.chunk_id, c.document_id, c.filename, c.page) == (1, "c0", "d0", "file0.pdf", 1)
    assert c.score == 5.0 and c.passage == TEXTS[0]
    assert resp.latency_ms >= 0


async def test_fr_015_unknown_citations_are_discarded() -> None:
    gen = ScriptedGenerator("Thickness 3.5 mm [5], fluid DOT 4 [2].", cited=[5, 2])
    resp = await service(FakeRetriever([rc(0), rc(1)]), gen).ask(Q, 4)
    assert [c.chunk_id for c in resp.citations] == ["c1"]
    assert "[5]" not in resp.answer and "[1]" in resp.answer


async def test_fr_014_citations_numbered_by_first_use() -> None:
    gen = ScriptedGenerator("Fluid DOT 4 [2]. Thickness 3.5 mm [1].", cited=[1, 2])
    resp = await service(FakeRetriever([rc(0), rc(1)]), gen).ask(Q, 4)
    assert [(c.n, c.chunk_id) for c in resp.citations] == [(1, "c1"), (2, "c0")]
    assert resp.answer == "Fluid DOT 4 [1]. Thickness 3.5 mm [2]."


async def test_fr_016_no_valid_citations_falls_back_to_extractive() -> None:
    gen = ScriptedGenerator("Made up [9].", cited=[9])
    fallback = ScriptedGenerator("Front | 276 mm | 3.5 mm [1]", cited=[1], name="extractive")
    resp = await service(FakeRetriever([rc(0)]), gen, fallback=fallback).ask(Q, 4)
    assert resp.generator_used == "extractive"
    assert resp.fallback_reason and "citation" in resp.fallback_reason
    assert resp.grounded is True and len(resp.citations) == 1


async def test_sc_004_answer_without_valid_citations_is_a_refusal() -> None:
    gen = ScriptedGenerator("Made up [9].", cited=[9])
    resp = await service(FakeRetriever([rc(0)]), gen).ask(Q, 4)
    assert resp.answer == REFUSAL and resp.citations == [] and resp.grounded is False
