"""Local embeddings with fastembed (ONNX, no PyTorch). The model is cached in data/models."""

from pathlib import Path


class FastEmbedEmbedder:
    def __init__(self, model_name: str, cache_dir: Path) -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        # Blocking: loads (and on first run downloads) the model. Built once at startup.
        self._model = TextEmbedding(model_name=model_name, cache_dir=str(cache_dir))

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(x) for x in vector] for vector in self._model.embed(texts)]
