"""FastAPI app factory: `uvicorn app.api.main:app`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import ValidationError

from app.api.deps import build_container
from app.api.errors import add_error_handlers
from app.api.logging import add_request_logging
from app.api.routes import ask, documents, samples, status
from app.settings import Settings


def _load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        problems = "\n".join(f"  - {e['msg'].removeprefix('Value error, ')}" for e in exc.errors())
        raise SystemExit(f"DocBot cannot start: invalid configuration.\n{problems}") from None


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or _load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = await build_container(settings)
        app.state.container = container
        try:
            yield
        finally:
            await container.aclose()

    app = FastAPI(title="DocBot", version="0.1.0", lifespan=lifespan)
    add_request_logging(app)
    add_error_handlers(app)
    app.include_router(status.router)
    app.include_router(documents.router)
    app.include_router(ask.router)
    app.include_router(samples.router)
    return app


def __getattr__(name: str) -> FastAPI:
    # Built lazily so importing this module (e.g. in tests) does not read the environment.
    if name == "app":
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        return create_app()
    raise AttributeError(name)
