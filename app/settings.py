"""Application settings, read from DOCBOT_* environment variables or a .env file (FR-050)."""

from pathlib import Path
from typing import Self

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RETRIEVERS = ("vector", "keyword")
GENERATORS = ("extractive", "ollama", "openai", "anthropic")
EMBEDDERS = ("fastembed", "openai")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCBOT_", env_file=".env", extra="ignore", populate_by_name=True
    )

    data_dir: Path = Path("./data")
    sample_dir: Path = Path("./sample_data")
    golden_path: Path = Path("./eval/golden.yaml")
    max_upload_mb: int = Field(default=20, ge=1)
    max_pdf_mb: int = Field(default=1, ge=1)
    chunk_size: int = Field(default=800, ge=100)
    chunk_overlap: int = Field(default=100, ge=0)
    retriever: str = "vector"
    embedder: str = "fastembed"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    openai_embed_model: str = "text-embedding-3-small"
    top_k: int = Field(default=4, ge=1, le=10)
    min_score_vector: float = 0.50
    min_score_keyword: float = 1.0
    min_coverage: float = Field(default=0.55, ge=0.0, le=1.0)
    generator: str = "extractive"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    llm_timeout_s: float = Field(default=30, gt=0)
    # Optional cloud generators (constitution 1.1.0). Keys are secrets: never logged or returned.
    openai_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("DOCBOT_OPENAI_API_KEY", "OPENAI_API_KEY")
    )
    openai_model: str = "gpt-5-mini"
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("DOCBOT_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
    )
    anthropic_model: str = "claude-opus-5-5"
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

    @field_validator("embedder")
    @classmethod
    def _known_embedder(cls, value: str) -> str:
        if value not in EMBEDDERS:
            raise ValueError(
                f"Unknown embedder '{value}'. Valid options: {', '.join(EMBEDDERS)}."
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

    @model_validator(mode="after")
    def _cloud_key_present(self) -> Self:
        """FR-053: a cloud generator, or the OpenAI embedder, needs its API key."""
        key = self.openai_api_key
        has_openai_key = bool(key and key.get_secret_value().strip())
        if self.embedder == "openai" and not has_openai_key:
            raise ValueError(
                "DOCBOT_EMBEDDER=openai needs an API key. Set DOCBOT_OPENAI_API_KEY in .env "
                "(or OPENAI_API_KEY), or use DOCBOT_EMBEDDER=fastembed."
            )
        missing = {
            "openai": ("DOCBOT_OPENAI_API_KEY", self.openai_api_key),
            "anthropic": ("DOCBOT_ANTHROPIC_API_KEY", self.anthropic_api_key),
        }.get(self.generator)
        if missing and not (missing[1] and missing[1].get_secret_value().strip()):
            raise ValueError(
                f"DOCBOT_GENERATOR={self.generator} needs an API key. Set {missing[0]} "
                "in .env (or the provider's standard variable), or use DOCBOT_GENERATOR=extractive."
            )
        return self

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
