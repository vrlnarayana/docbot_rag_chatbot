import httpx
import pytest
from fastapi import FastAPI

from app.adapters.generator_extractive import ExtractiveGenerator
from app.core.models import AskResponse, ErrorResponse
from app.core.services import EMPTY_LIBRARY, REFUSAL
from tests.images import table_pdf, text_image

FORBIDDEN = ("stored_name", "sha256", "/files/", "Passages:", "prompt")


async def load_corpus(client: httpx.AsyncClient) -> None:
    # Like the real sample set: every document is a Demo Motors document, and each fact is
    # worded with the key terms of its question (plan §8).
    files = {
        "brake.pdf": table_pdf([["Demo Motors brake standard", "", ""],
                                ["Brake disc specifications", "", ""],
                                ["Position", "Disc diameter", "Minimum thickness"],
                                ["Front", "276 mm", "3.5 mm"], ["Rear", "220 mm", "4.0 mm"]]),
        "lamp.png": text_image(["Demo Motors LED headlamp 12 V", "High beam 13 W", "Low beam 9 W"]),
        "manual.md": b"# Demo Motors Velo 125 owner manual\n\nRecommended tyre pressure, solo "
                     b"rider: front 29 psi, rear 33 psi.\n\nEngine oil SAE 10W-30, capacity 1.0 L.",
        "ecn.txt": b"Demo Motors engineering change note DM-ECN-0457.\nNew rear sprocket size for "
                   b"the Velo 125: 43T (was 42T), effective 1 November 2026.",
    }
    for name, data in files.items():
        resp = await client.post("/documents", files={"file": (name, data)})
        assert resp.status_code == 201, resp.text


async def ask(client: httpx.AsyncClient, question: str, **extra: object) -> httpx.Response:
    return await client.post("/ask", json={"question": question, **extra})


@pytest.fixture
def extractive(app: FastAPI) -> None:
    container = app.state.container
    container.qa.generator = ExtractiveGenerator(container.ingestion.gate)


async def test_fr_018_empty_library(client: httpx.AsyncClient) -> None:
    resp = await ask(client, "What is the minimum thickness?")
    body = AskResponse.model_validate(resp.json())
    assert body.answer == EMPTY_LIBRARY and body.generator_used == "none"


async def test_fr_013_fr_014_cited_answer(client: httpx.AsyncClient) -> None:
    await load_corpus(client)
    resp = await ask(client, "What is the recommended rear tyre pressure?")
    assert resp.status_code == 200
    body = AskResponse.model_validate(resp.json())
    assert body.grounded and body.retriever == "keyword" and body.generator_used == "fake"
    assert body.citations[0].filename == "manual.md" and body.citations[0].page == 1
    for word in FORBIDDEN:
        assert word not in resp.text


@pytest.mark.usefixtures("extractive")
@pytest.mark.parametrize(
    ("question", "fact", "filename", "page"),
    [
        ("What is the minimum thickness of the front brake disc?", "3.5 mm", "brake.pdf", 1),
        ("What is the high beam wattage of the LED headlamp?", "13 W", "lamp.png", 1),
        ("What is the new rear sprocket size for the Velo 125?", "43T", "ecn.txt", 1),
        ("What is the recommended rear tyre pressure?", "33 psi", "manual.md", 1),
    ],
)
async def test_fr_013_extractive_answers_contain_the_fact(
    client: httpx.AsyncClient, question: str, fact: str, filename: str, page: int
) -> None:
    await load_corpus(client)
    body = AskResponse.model_validate((await ask(client, question)).json())
    assert fact.replace(" ", "") in body.answer.replace(" ", "")
    assert body.generator_used == "extractive"
    assert (body.citations[0].filename, body.citations[0].page) == (filename, page)


@pytest.mark.usefixtures("extractive")
@pytest.mark.parametrize(
    "question",
    ["What is the top speed of the Velo 125?", "Who is the CEO of Demo Motors?",
     "What is the warranty period for the battery?"],
)
async def test_fr_012_out_of_scope_questions_are_refused(
    client: httpx.AsyncClient, question: str
) -> None:
    await load_corpus(client)
    body = AskResponse.model_validate((await ask(client, question)).json())
    assert body.answer == REFUSAL
    assert (body.grounded, body.citations, body.generator_used) == (False, [], "none")


@pytest.mark.parametrize(
    "payload",
    [{"question": "hi"}, {"question": "x" * 1001}, {"question": "What is it?", "top_k": 0},
     {"question": "What is it?", "top_k": 11}, {"question": "What is it?", "history": []},
     {"question": 123}],
)
async def test_fr_010_invalid_requests_are_422(
    client: httpx.AsyncClient, payload: dict[str, object]
) -> None:
    resp = await client.post("/ask", json=payload)
    assert resp.status_code == 422
    assert ErrorResponse.model_validate(resp.json()).code == "validation_error"
