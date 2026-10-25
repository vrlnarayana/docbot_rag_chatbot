from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest

from app.adapters.embedder_openai import BATCH_SIZE, OpenAIEmbedder
from app.core.errors import EmbeddingUnavailable

REQ = httpx.Request("POST", "https://api.openai.com/v1/embeddings")


class FakeEmbeddings:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error = error

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        # Return items out of order: the embedder must sort by index.
        items = [SimpleNamespace(index=i, embedding=[float(len(t)), float(i)])
                 for i, t in enumerate(kwargs["input"])]
        return SimpleNamespace(data=list(reversed(items)))


def embedder(fake: FakeEmbeddings) -> OpenAIEmbedder:
    client = SimpleNamespace(embeddings=fake)
    return OpenAIEmbedder(client, "text-embedding-3-small")  # type: ignore[arg-type]


def test_fr_055_embeds_in_input_order_with_the_configured_model() -> None:
    fake = FakeEmbeddings()
    vectors = embedder(fake).embed(["a", "bbb"])
    assert vectors == [[1.0, 0.0], [3.0, 1.0]]
    assert fake.calls[0]["model"] == "text-embedding-3-small"
    assert embedder(fake).model_name == "openai:text-embedding-3-small"


def test_fr_055_large_inputs_are_batched() -> None:
    fake = FakeEmbeddings()
    texts = [f"chunk {i}" for i in range(BATCH_SIZE + 5)]
    vectors = embedder(fake).embed(texts)
    assert len(vectors) == len(texts)
    assert [len(c["input"]) for c in fake.calls] == [BATCH_SIZE, 5]
    assert vectors[BATCH_SIZE][1] == 0.0  # indexes restart per batch, order is kept


def test_empty_input_makes_no_call() -> None:
    fake = FakeEmbeddings()
    assert embedder(fake).embed([]) == []
    assert fake.calls == []


@pytest.mark.parametrize(
    ("error", "hint"),
    [
        (openai.APIConnectionError(request=REQ), "not reachable"),
        (openai.AuthenticationError("bad", response=httpx.Response(401, request=REQ), body=None),
         "DOCBOT_OPENAI_API_KEY"),
        (openai.NotFoundError("no", response=httpx.Response(404, request=REQ), body=None),
         "DOCBOT_OPENAI_EMBED_MODEL"),
        (openai.RateLimitError("slow", response=httpx.Response(429, request=REQ), body=None),
         "HTTP 429"),
    ],
)
def test_fr_056_provider_errors_become_embedding_unavailable(
    error: Exception, hint: str
) -> None:
    with pytest.raises(EmbeddingUnavailable) as exc:
        embedder(FakeEmbeddings(error)).embed(["text"])
    assert exc.value.code == "embedding_unavailable"
    assert hint in exc.value.message and "sk-" not in exc.value.message
