"""Small deterministic fakes shared by tests."""

from app.core.text import tokenize

VOCAB = ["brake", "disc", "thickness", "tyre", "pressure", "rear", "oil", "vibration", "fluid"]


class BagOfWordsEmbedder:
    """Embeds text as counts over a tiny vocabulary: similar words, similar vectors."""

    model_name = "fake-bow"

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        vectors = []
        for text in texts:
            tokens = tokenize(text)
            vectors.append([float(tokens.count(w)) for w in VOCAB] + [0.1])
        return vectors


class FakeOpenAIEmbeddings:
    """Stands in for `openai.OpenAI().embeddings`: bag-of-words vectors, or a scripted error."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.inputs: list[str] = []

    def create(self, *, model: str, input: list[str]) -> object:  # noqa: A002 - SDK name
        from types import SimpleNamespace

        if self.error:
            raise self.error
        self.inputs.extend(input)
        vectors = BagOfWordsEmbedder().embed(input)
        return SimpleNamespace(
            data=[SimpleNamespace(index=i, embedding=v) for i, v in enumerate(vectors)]
        )
