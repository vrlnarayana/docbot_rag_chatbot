import pytest

from app.core.answerability import AnswerabilityGate
from app.core.errors import NoDocuments
from app.core.models import GoldenCase
from app.core.services import EvaluationService, QAService
from tests.conftest import FakeGenerator
from tests.unit.test_qa_service import TEXTS, FakeRepo, FakeRetriever, rc

CASES = [
    GoldenCase(question="What is the minimum thickness of the front brake disc?",
               expected_file="file0.pdf", expected_page=1, expected_keywords=["3.5 MM"]),
    GoldenCase(question="What brake fluid is used?", expected_file="file1.pdf",
               expected_page=2, expected_keywords=["DOT 4", "missing keyword"]),
    GoldenCase(question="What is the top speed of the bike?", expect_refusal=True),
]


def service(chunks: int = 2) -> EvaluationService:
    gate = AnswerabilityGate()
    gate.refresh(TEXTS)
    qa = QAService(
        repository=FakeRepo(chunks),  # type: ignore[arg-type]
        retriever=FakeRetriever([rc(0), rc(1)]),
        generator=FakeGenerator(),
        gate=gate,
        min_coverage=0.55,
    )
    return EvaluationService(FakeRepo(chunks), qa)  # type: ignore[arg-type]


async def test_fr_040_reports_hit_fact_and_refusal_per_case() -> None:
    result = await service().run(CASES, top_k=4)
    first, second, refusal = result.results
    assert first.retrieved_files == ["file0.pdf", "file1.pdf"]
    assert (first.hit, first.fact_found, first.refused, first.refusal_correct) == (
        True, True, False, True)
    assert (second.hit, second.fact_found) == (True, False)  # all keywords must be present
    assert (refusal.expect_refusal, refusal.refused, refusal.refusal_correct) == (
        True, True, True)
    assert refusal.hit is False and refusal.fact_found is False


async def test_fr_041_summary_metrics_as_percentages() -> None:
    summary = (await service().run(CASES, top_k=3)).summary
    assert summary.cases == 3
    assert summary.hit_rate_at_k == 100.0
    assert summary.answer_accuracy == 50.0
    assert summary.refusal_accuracy == 100.0
    assert (summary.retriever, summary.generator, summary.top_k) == ("keyword", "fake", 3)


async def test_fr_040_empty_library_is_rejected() -> None:
    with pytest.raises(NoDocuments):
        await service(chunks=0).run(CASES, top_k=4)
