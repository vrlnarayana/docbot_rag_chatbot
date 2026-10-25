"""End-to-end conversation on the generated sample corpus (FR-070, FR-071).

Keyword retriever and extractive generator, so follow-ups use the local rule (no LLM).
"""

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from app.adapters.samples import BRAKE
from app.api.main import create_app
from app.core.models import AskResponse
from app.settings import Settings

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def client(tmp_path_factory: pytest.TempPathFactory) -> AsyncIterator[httpx.AsyncClient]:
    root: Path = tmp_path_factory.mktemp("conv")
    settings = Settings(
        data_dir=root / "data", sample_dir=root / "sample_data",
        golden_path=root / "eval" / "golden.yaml", retriever="keyword",
        generator="extractive", _env_file=None,  # type: ignore[call-arg]
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://e2e") as c:
            assert (await c.post("/samples/load")).json()["indexed"] == 8
            yield c


async def ask(client: httpx.AsyncClient, question: str, previous: str | None = None
              ) -> AskResponse:
    body: dict[str, object] = {"question": question}
    if previous:
        body["history"] = [{"role": "user", "content": previous}]
    return AskResponse.model_validate((await client.post("/ask", json=body)).json())


async def test_fr_071_greeting(client: httpx.AsyncClient) -> None:
    reply = await ask(client, "hi")
    assert reply.small_talk and not reply.citations


async def test_fr_070_follow_up_is_answered_from_the_right_page(
    client: httpx.AsyncClient,
) -> None:
    first = "What brake fluid does the brake standard specify?"
    reply = await ask(client, "how often do you replace it?", previous=first)
    assert reply.standalone_question == f"{first} how often do you replace it?"
    assert reply.grounded and "2 years" in reply.answer
    assert (reply.citations[0].filename, reply.citations[0].page) == (BRAKE, 3)


@pytest.mark.parametrize(
    ("previous", "follow_up"),
    [
        ("What is the recommended rear tyre pressure?", "and who is the CEO?"),
        ("What is the high beam wattage of the LED headlamp?", "what about the battery warranty?"),
        ("What brake fluid does the brake standard specify?", "what about the top speed?"),
    ],
)
async def test_fr_070_out_of_scope_follow_ups_are_still_refused(
    client: httpx.AsyncClient, previous: str, follow_up: str
) -> None:
    reply = await ask(client, follow_up, previous=previous)
    assert reply.answer == "I couldn't find this in the uploaded documents."
    assert reply.citations == []
