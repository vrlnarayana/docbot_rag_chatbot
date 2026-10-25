"""Uploaded files on local disk, stored under generated names (Constitution IV.3)."""

import re
import uuid
from pathlib import Path

import anyio

_SAFE_EXT = re.compile(r"\.[a-z0-9]{1,5}")
_SAFE_NAME = re.compile(r"[0-9a-f]{32}\.[a-z0-9]{1,5}")


class LocalFileStore:
    def __init__(self, folder: Path) -> None:
        self._folder = folder

    async def save(self, data: bytes, extension: str) -> str:
        if not _SAFE_EXT.fullmatch(extension):
            raise ValueError("unsafe file extension")
        name = f"{uuid.uuid4().hex}{extension}"
        await anyio.Path(self._folder).mkdir(parents=True, exist_ok=True)
        await anyio.Path(self._folder / name).write_bytes(data)
        return name

    async def delete(self, stored_name: str) -> None:
        if not _SAFE_NAME.fullmatch(stored_name):
            raise ValueError("unsafe stored name")
        await anyio.Path(self._folder / stored_name).unlink(missing_ok=True)
