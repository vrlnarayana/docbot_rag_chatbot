from pathlib import Path

import pytest

from scripts import reset_demo


def make_data(root: Path) -> Path:
    data = root / "data"
    (data / "files").mkdir(parents=True)
    (data / "docbot.db").write_bytes(b"db")
    (data / "files" / "a.pdf").write_bytes(b"x")
    return data


def test_fr_023_reset_requires_typing_reset(tmp_path: Path) -> None:
    data = make_data(tmp_path)
    assert reset_demo.reset(data, ask=lambda _prompt: "reset") == 1  # case matters
    assert data.exists()
    assert reset_demo.reset(data, ask=lambda _prompt: "RESET") == 0
    assert not data.exists()


def test_reset_with_nothing_to_delete(tmp_path: Path) -> None:
    assert reset_demo.reset(tmp_path / "data", ask=lambda _prompt: "RESET") == 0


@pytest.mark.parametrize("target", ["root", "home", "cwd_parent", "not_docbot"])
def test_reset_refuses_dangerous_folders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    stray = tmp_path / "photos"
    stray.mkdir()
    (stray / "holiday.jpg").write_bytes(b"x")
    folders = {"root": Path("/"), "home": Path.home(), "cwd_parent": tmp_path,
               "not_docbot": stray}
    asked: list[str] = []
    assert reset_demo.reset(folders[target], ask=lambda p: asked.append(p) or "RESET") == 2
    assert asked == []
    assert (stray / "holiday.jpg").exists()
