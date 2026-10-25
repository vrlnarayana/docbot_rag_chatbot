"""Optional OpenAI embeddings for the vector retriever (FR-055, constitution 1.2.0).

Every indexed chunk and every question is sent to OpenAI. Built once at startup with the
configured timeout and the SDK's retries (2, exponential backoff, transient errors only).
"""

import openai

from app.core.errors import EmbeddingUnavailable

BATCH_SIZE = 256  # well under the API's per-request input limit


class OpenAIEmbedder:
    def __init__(self, client: openai.OpenAI, model: str) -> None:
        self._client = client
        self._model = model
        # Stored with each vector, so switching models triggers re-embedding (plan §5).
        self.model_name = f"openai:{model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Blocking; callers run it in a worker thread."""
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            try:
                response = self._client.embeddings.create(model=self._model, input=batch)
            except openai.APIError as exc:
                raise EmbeddingUnavailable(self._describe(exc)) from exc
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend([float(x) for x in item.embedding] for item in ordered)
        return vectors

    def _describe(self, exc: openai.APIError) -> str:
        if isinstance(exc, openai.APIConnectionError):  # includes timeouts
            return "OpenAI not reachable — check the internet connection."
        if isinstance(exc, openai.AuthenticationError):
            return "OpenAI rejected the API key — check DOCBOT_OPENAI_API_KEY."
        if isinstance(exc, openai.NotFoundError):
            return f"OpenAI model '{self._model}' not found — check DOCBOT_OPENAI_EMBED_MODEL."
        if isinstance(exc, openai.APIStatusError):
            return f"OpenAI returned HTTP {exc.status_code}."
        return "OpenAI returned an unexpected error."

    def close(self) -> None:
        self._client.close()
