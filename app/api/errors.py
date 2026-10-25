"""Map domain errors to ErrorResponse. Clients never see stack traces or paths (NFR-006)."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import DocBotError
from app.core.models import ErrorResponse

logger = logging.getLogger("docbot.errors")

STATUS_BY_CODE = {
    "unsupported_type": 415,
    "too_large": 413,
    "length_required": 411,
    "no_text": 422,
    "extraction_failed": 422,
    "not_found": 404,
    "no_documents": 409,
    "no_golden": 409,
    "embedding_unavailable": 503,
}


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content=ErrorResponse(code=code, message=message).model_dump()
    )


def add_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DocBotError)
    async def domain_error(_request: Request, exc: DocBotError) -> JSONResponse:
        return _error(STATUS_BY_CODE.get(exc.code, 400), exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'] if p != 'body')}: {e['msg']}"
            for e in exc.errors()
        )
        return _error(422, "validation_error", problems or "Invalid request.")

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled error: %s", type(exc).__name__)
        return _error(500, "internal_error", "Something went wrong. Check the API logs.")
