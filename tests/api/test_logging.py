import json
import logging

import httpx
import pytest
from fastapi import FastAPI

from app.api.logging import LOGGER_NAME, add_request_logging


@pytest.fixture
def tiny_app() -> FastAPI:
    app = FastAPI()
    add_request_logging(app)

    @app.post("/echo")
    async def echo(body: dict[str, str]) -> dict[str, str]:  # test-only route
        return body

    return app


async def test_one_structured_line_per_request(
    tiny_app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    transport = httpx.ASGITransport(app=tiny_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/echo", json={"text": "SECRET DOCUMENT TEXT"})

    records = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert len(records) == 1
    line = json.loads(records[0].getMessage())
    assert set(line) >= {"request_id", "method", "path", "status", "duration_ms"}
    assert line["status"] == 200
    assert line["path"] == "/echo"
    assert resp.headers["x-request-id"] == line["request_id"]
    assert "SECRET DOCUMENT TEXT" not in records[0].getMessage()
