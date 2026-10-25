"""Application settings, read from DOCBOT_* environment variables or a .env file (FR-050)."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RETRIEVERS = ("vector", "keyword")
GENERATORS = ("extractive", "ollama")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCBOT_", env_file=".env", extra="ignore")

    data_dir: Path = Path("./data")
    sample_dir: Path = Path("./sample_data")
    golden_path: Path = Path("./eval/golden.yaml")
    max_upload_mb: int = Field(default=20, ge=1)
    max_pdf_mb: int = Field(default=1, ge=1)
    chunk_size: int = Field(default=800, ge=100)
    chunk_overlap: int = Field(default=100, ge=0)
    retriever: str = "vector"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    top_k: int = Field(default=4, ge=1, le=10)
    min_score_vector: float = 0.50
    min_score_keyword: float = 1.0
    min_coverage: float = Field(default=0.55, ge=0.0, le=1.0)
    generator: str = "extractive"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    llm_timeout_s: float = Field(default=30, gt=0)
    api_url: str = "http://localhost:8000"

    @field_validator("retriever")
    @classmethod
    def _known_retriever(cls, value: str) -> str:
        if value not in RETRIEVERS:
            raise ValueError(
                f"Unknown retriever '{value}'. Valid options: {', '.join(RETRIEVERS)}. "
                "(Azure arrives in SPEC-002.)"
            )
        return value

    @field_validator("generator")
    @classmethod
    def _known_generator(cls, value: str) -> str:
        if value not in GENERATORS:
            raise ValueError(
                f"Unknown generator '{value}'. Valid options: {', '.join(GENERATORS)}. "
                "(Azure arrives in SPEC-002.)"
            )
        return value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def max_pdf_bytes(self) -> int:
        return self.max_pdf_mb * 1024 * 1024

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "docbot.db"
