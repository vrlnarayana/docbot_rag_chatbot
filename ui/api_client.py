"""The UI's only way to reach DocBot: HTTP calls to the FastAPI service (FR-061).

Every page uses `client()` and shows `api_down_banner()` when the API is unreachable (FR-064).
"""

from typing import Any

import httpx
import streamlit as st
from pydantic_settings import BaseSettings, SettingsConfigDict

# Tests set this to an httpx.MockTransport; it is None when the app runs.
TRANSPORT: httpx.BaseTransport | None = None


class UiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCBOT_", env_file=".env", extra="ignore")

    api_url: str = "http://localhost:8000"


class ApiUnavailable(Exception):
    def __init__(self, url: str) -> None:
        super().__init__(f"API not reachable at {url}")
        self.url = url


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class DocBotClient:
    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = base_url
        # Uploads wait for indexing (OCR, embeddings), so allow plenty of time.
        self._http = httpx.Client(base_url=base_url, timeout=300, transport=transport)

    def _call(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.TransportError as exc:
            raise ApiUnavailable(self.base_url) from exc
        if response.status_code >= 400:
            try:
                message = str(response.json()["message"])
            except (ValueError, KeyError, TypeError):
                message = f"The API returned HTTP {response.status_code}."
            raise ApiError(response.status_code, message)
        return response.json()

    def status(self) -> dict[str, Any]:
        return dict(self._call("GET", "/status"))

    def ask(
        self, question: str, top_k: int, history: list[dict[str, str]] | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"question": question, "top_k": top_k}
        if history:
            body["history"] = history
        return dict(self._call("POST", "/ask", json=body))

    def documents(self) -> list[dict[str, Any]]:
        return list(self._call("GET", "/documents"))

    def chunks(self, document_id: str) -> list[dict[str, Any]]:
        return list(self._call("GET", f"/documents/{document_id}/chunks"))

    def upload(self, filename: str, data: bytes) -> dict[str, Any]:
        return dict(self._call("POST", "/documents", files={"file": (filename, data)}))

    def delete(self, document_id: str) -> dict[str, Any]:
        return dict(self._call("DELETE", f"/documents/{document_id}"))

    def load_samples(self) -> dict[str, Any]:
        return dict(self._call("POST", "/samples/load"))

    def run_eval(self, top_k: int) -> dict[str, Any]:
        return dict(self._call("POST", "/eval/run", json={"top_k": top_k}))


def client() -> DocBotClient:
    return DocBotClient(UiSettings().api_url, transport=TRANSPORT)


def api_down_banner(exc: ApiUnavailable) -> None:
    st.error(
        f"**DocBot API not reachable at {exc.url}.** Start it in another terminal with "
        "`uvicorn app.api.main:app --port 8000`, or set `DOCBOT_API_URL` in `.env`.",
        icon="🔌",
    )
