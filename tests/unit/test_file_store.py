import re
from pathlib import Path

import pytest

from app.adapters.file_store import LocalFileStore


async def test_saves_under_generated_name_inside_folder(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path / "files")
    name = await store.save(b"hello", ".pdf")
    assert re.fullmatch(r"[0-9a-f]{32}\.pdf", name)
    assert (tmp_path / "files" / name).read_bytes() == b"hello"


@pytest.mark.parametrize("ext", ["../../evil", ".p/df", "/etc/passwd"])
async def test_rejects_unsafe_extensions(tmp_path: Path, ext: str) -> None:
    store = LocalFileStore(tmp_path / "files")
    with pytest.raises(ValueError):
        await store.save(b"x", ext)


async def test_fr_022_delete_removes_file(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path / "files")
    name = await store.save(b"x", ".txt")
    await store.delete(name)
    assert list((tmp_path / "files").iterdir()) == []
    await store.delete(name)  # idempotent


async def test_delete_refuses_names_outside_folder(tmp_path: Path) -> None:
    outside = tmp_path / "keep.txt"
    outside.write_text("keep")
    store = LocalFileStore(tmp_path / "files")
    with pytest.raises(ValueError):
        await store.delete("../keep.txt")
    assert outside.exists()
