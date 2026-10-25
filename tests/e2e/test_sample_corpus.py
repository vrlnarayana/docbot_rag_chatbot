"""End-to-end: generated sample corpus → load → golden questions (Constitution V.3).

Keyword retriever and extractive generator: no model download, no LLM, no network.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from app.adapters.samples import CERT, GOLDEN, LAMP
from app.api.main import create_app
from app.core.models import AskResponse, ChunkOut
from app.settings import Settings

SC_005 = {  # the table, scanned-PDF and image questions
    "What is the minimum thickness of the front brake disc?",
    "What is the tensile strength on the Northwind Castings certificate?",
    "What is the high beam wattage of the LED headlamp?",
}


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def answers(tmp_path_factory: pytest.TempPathFactory) -> AsyncIterator[
    tuple[httpx.AsyncClient, dict[str, AskResponse]]
]:
    root: Path = tmp_path_factory.mktemp("e2e")
    settings = Settings(
        data_dir=root / "data", sample_dir=root / "sample_data",
        golden_path=root / "eval" / "golden.yaml", retriever="keyword",
        generator="extractive", _env_file=None,  # type: ignore[call-arg]
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://e2e") as client:
            loaded = (await client.post("/samples/load")).json()
            assert loaded == {"indexed": 8, "duplicates": 0, "failed": []}
            results = {}
            for case in GOLDEN:
                resp = await client.post("/ask", json={"question": case.question})
                results[case.question] = AskResponse.model_validate(resp.json())
            yield client, results


pytestmark = pytest.mark.asyncio(loop_scope="module")


async def test_sc_003_all_out_of_scope_questions_are_refused(
    answers: tuple[httpx.AsyncClient, dict[str, AskResponse]],
) -> None:
    _client, results = answers
    for case in GOLDEN:
        if case.expect_refusal:
            reply = results[case.question]
            assert reply.answer == "I couldn't find this in the uploaded documents.", case.question
            assert (reply.grounded, reply.citations) == (False, [])


async def test_sc_004_every_answer_cites_a_real_chunk(
    answers: tuple[httpx.AsyncClient, dict[str, AskResponse]],
) -> None:
    client, results = answers
    answered = [r for r in results.values() if r.grounded]
    assert len(answered) == 9
    for reply in answered:
        assert reply.citations, reply.answer
        for citation in reply.citations:
            resp = await client.get(f"/documents/{citation.document_id}/chunks")
            chunks = {c.id: c for c in map(ChunkOut.model_validate, resp.json())}
            assert citation.chunk_id in chunks
            assert chunks[citation.chunk_id].page == citation.page
            assert chunks[citation.chunk_id].text == citation.passage


async def test_sc_005_table_scan_and_image_questions(
    answers: tuple[httpx.AsyncClient, dict[str, AskResponse]],
) -> None:
    _client, results = answers
    for case in GOLDEN:
        if case.question not in SC_005:
            continue
        reply = results[case.question]
        for keyword in case.expected_keywords:
            assert keyword.lower() in reply.answer.lower(), (case.question, reply.answer)
        top = reply.citations[0]
        assert (top.filename, top.page) == (case.expected_file, case.expected_page)
    cited = {results[q].citations[0].filename for q in SC_005}
    assert {CERT, LAMP} <= cited  # facts only reachable through OCR


async def test_sc_002_answer_accuracy_on_answerable_questions(
    answers: tuple[httpx.AsyncClient, dict[str, AskResponse]],
) -> None:
    _client, results = answers
    answerable = [c for c in GOLDEN if not c.expect_refusal]
    correct = sum(
        all(k.lower() in results[c.question].answer.lower() for k in c.expected_keywords)
        for c in answerable
    )
    assert correct / len(answerable) >= 0.8
