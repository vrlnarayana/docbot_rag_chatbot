from pathlib import Path

import httpx
import pytest

from app.core.models import LoadSamplesResponse, SamplesResponse
from app.settings import Settings
from tests.unit.test_samples import FILES


async def test_fr_030_generate_endpoint_writes_files(
    client: httpx.AsyncClient, settings: Settings
) -> None:
    resp = await client.post("/samples/generate")
    assert resp.status_code == 200
    body = SamplesResponse.model_validate(resp.json())
    assert sorted(body.files) == sorted(FILES)
    assert all((settings.sample_dir / f).exists() for f in FILES)
    assert settings.golden_path.exists()
    assert str(settings.sample_dir) not in resp.text  # names only, no paths


async def test_fr_031_load_generates_if_missing_then_reports_duplicates(
    client: httpx.AsyncClient, settings: Settings
) -> None:
    assert not settings.sample_dir.exists()
    first = LoadSamplesResponse.model_validate((await client.post("/samples/load")).json())
    assert (first.indexed, first.duplicates, first.failed) == (8, 0, [])
    status = (await client.get("/status")).json()
    assert status["documents"] == 8

    again = LoadSamplesResponse.model_validate((await client.post("/samples/load")).json())
    assert (again.indexed, again.duplicates) == (0, 8)
    assert (await client.get("/status")).json()["documents"] == 8


async def test_fr_031_unreadable_file_is_reported_not_fatal(
    client: httpx.AsyncClient, settings: Settings
) -> None:
    await client.post("/samples/generate")
    (settings.sample_dir / "notes.docx").write_bytes(b"PK")
    body = LoadSamplesResponse.model_validate((await client.post("/samples/load")).json())
    assert body.indexed == 8
    assert [f.filename for f in body.failed] == ["notes.docx"]
    assert ".pdf" in body.failed[0].reason


def test_fr_030_generate_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from scripts import generate_samples

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOCBOT_SAMPLE_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("DOCBOT_GOLDEN_PATH", str(tmp_path / "eval" / "golden.yaml"))
    assert generate_samples.main() == 0
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == sorted(FILES)
    assert (tmp_path / "eval" / "golden.yaml").exists()
