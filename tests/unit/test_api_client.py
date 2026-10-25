import ast
from pathlib import Path

import httpx
import pytest

from tests.ui_fakes import ANSWER, FakeApi, down_transport
from ui.api_client import ApiError, ApiUnavailable, DocBotClient


def test_fr_061_ask_goes_over_http() -> None:
    api = FakeApi()
    client = DocBotClient("http://api.test", transport=api.transport())
    assert client.ask("What is the minimum thickness?", top_k=3) == ANSWER
    [request] = api.requests
    assert request.url == "http://api.test/ask"
    assert request.read() == b'{"question":"What is the minimum thickness?","top_k":3}'


def test_upload_sends_multipart() -> None:
    api = FakeApi()
    DocBotClient("http://api.test", transport=api.transport()).upload("a.pdf", b"%PDF")
    assert b'filename="a.pdf"' in api.requests[0].read()


def test_fr_064_unreachable_api_raises_api_unavailable() -> None:
    client = DocBotClient("http://localhost:8000", transport=down_transport())
    with pytest.raises(ApiUnavailable) as exc:
        client.status()
    assert exc.value.url == "http://localhost:8000"


def test_api_errors_carry_the_server_message() -> None:
    api = FakeApi()
    api.routes[("POST", "/documents")] = (415, {"code": "unsupported_type",
                                               "message": "File type '.docx' is not supported."})
    client = DocBotClient("http://api.test", transport=api.transport())
    with pytest.raises(ApiError) as exc:
        client.upload("spec.docx", b"PK")
    assert exc.value.status == 415 and "not supported" in exc.value.message


def test_non_json_error_body_still_gives_a_message() -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="Bad Gateway")

    client = DocBotClient("http://api.test", transport=httpx.MockTransport(broken))
    with pytest.raises(ApiError) as exc:
        client.status()
    assert exc.value.status == 502 and exc.value.message


def test_fr_061_ui_imports_nothing_from_the_backend() -> None:
    banned = {"app", "sqlalchemy", "sqlite3", "aiosqlite", "fastembed", "rapidocr_onnxruntime"}
    ui = Path(__file__).resolve().parents[2] / "ui"
    for path in ui.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            assert not {n.split(".")[0] for n in names} & banned, (path.name, names)
