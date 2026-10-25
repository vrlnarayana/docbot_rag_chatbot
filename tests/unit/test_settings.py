from pathlib import Path

import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_fr_050_defaults_match_plan(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)  # no stray .env
    s = Settings()
    assert s.data_dir == Path("./data")
    assert s.max_upload_mb == 20
    assert (s.chunk_size, s.chunk_overlap) == (800, 100)
    assert s.retriever == "vector"
    assert s.generator == "extractive"
    assert s.top_k == 4
    assert s.min_score_vector == 0.50
    assert s.min_score_keyword == 1.0
    assert s.min_coverage == 0.55
    assert s.llm_timeout_s == 30
    assert s.embed_model == "BAAI/bge-small-en-v1.5"


def test_fr_050_reads_env_and_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("DOCBOT_TOP_K=7\n")
    monkeypatch.setenv("DOCBOT_RETRIEVER", "keyword")
    s = Settings()
    assert s.top_k == 7
    assert s.retriever == "keyword"


def test_fr_052_unknown_generator_fails_with_valid_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOCBOT_GENERATOR", "azure_openai")
    with pytest.raises(ValidationError) as exc:
        Settings()
    msg = str(exc.value)
    assert "Unknown generator 'azure_openai'" in msg
    assert "extractive, ollama" in msg
    assert "SPEC-002" in msg


def test_fr_052_unknown_retriever_fails_with_valid_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOCBOT_RETRIEVER", "azure_search")
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "Unknown retriever 'azure_search'" in str(exc.value)
    assert "vector, keyword" in str(exc.value)


def test_fr_010_top_k_bounds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOCBOT_TOP_K", "11")
    with pytest.raises(ValidationError):
        Settings()


def test_fr_003_pdf_limit_defaults_to_1_mb(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    s = Settings()
    assert s.max_pdf_mb == 1
    assert s.max_pdf_bytes == 1024 * 1024


def test_fr_019_cloud_generators_are_valid_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOCBOT_GENERATOR", "openai")
    monkeypatch.setenv("DOCBOT_OPENAI_API_KEY", "sk-test-123")
    s = Settings()
    assert s.generator == "openai"
    assert s.openai_api_key is not None
    assert s.openai_api_key.get_secret_value() == "sk-test-123"
    assert "sk-test-123" not in repr(s)


def test_fr_019_provider_standard_key_names_are_accepted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOCBOT_GENERATOR", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    s = Settings()
    assert s.anthropic_api_key is not None
    assert s.anthropic_api_key.get_secret_value() == "sk-ant-test"
    assert s.anthropic_model == "claude-opus-5-5"


@pytest.mark.parametrize(
    ("generator", "variable"),
    [("openai", "DOCBOT_OPENAI_API_KEY"), ("anthropic", "DOCBOT_ANTHROPIC_API_KEY")],
)
def test_fr_053_cloud_generator_without_key_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, generator: str, variable: str
) -> None:
    monkeypatch.chdir(tmp_path)
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DOCBOT_OPENAI_API_KEY",
                 "DOCBOT_ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DOCBOT_GENERATOR", generator)
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert variable in str(exc.value)


def test_fr_055_embedder_defaults_to_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    s = Settings()
    assert s.embedder == "fastembed"
    assert s.openai_embed_model == "text-embedding-3-small"


def test_fr_055_openai_embedder_with_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOCBOT_EMBEDDER", "openai")
    monkeypatch.setenv("DOCBOT_OPENAI_API_KEY", "sk-test")
    assert Settings().embedder == "openai"


def test_fr_053_openai_embedder_without_key_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    for name in ("OPENAI_API_KEY", "DOCBOT_OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DOCBOT_EMBEDDER", "openai")
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "DOCBOT_EMBEDDER=openai" in str(exc.value)
    assert "DOCBOT_OPENAI_API_KEY" in str(exc.value)


def test_fr_052_unknown_embedder_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOCBOT_EMBEDDER", "azure")
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "Unknown embedder 'azure'" in str(exc.value) and "fastembed, openai" in str(exc.value)
