"""UI tests run the real Streamlit pages in-process against a fake API transport."""

import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

UI_DIR = Path(__file__).resolve().parents[2] / "ui"


@pytest.fixture
def api_client_module() -> Iterator[ModuleType]:
    # Pages import `api_client` as Streamlit does (ui/ on sys.path); share that module object.
    sys.path.insert(0, str(UI_DIR))
    import api_client

    yield api_client
    api_client.TRANSPORT = None
    sys.path.remove(str(UI_DIR))


def page(name: str) -> str:
    return str(UI_DIR / name)
