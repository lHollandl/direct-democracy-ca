"""Typed application errors and the one handler that turns them into responses.

CLAUDE.md Law 12: errors are never swallowed and never exposed. Services raise
the exceptions below; `install_error_handlers` maps them to a status code and a
body `{"error": <code>, "message": <plain English>}`. Anything else is logged
server-side with the request id and returned as a generic 500.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for every error the application raises on purpose."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, extra: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.extra = extra or {}


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


class ExternalServiceDown(AppError):
    status_code = 503
    code = "external_service_down"


class Gone(AppError):
    """The thing existed but its window has closed — a data export past its
    `expires_at`, say (DATABASE.md §3.11)."""

    status_code = 410
    code = "gone"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        body: dict[str, Any] = {"error": exc.code, "message": exc.message}
        body.update(exc.extra)
        headers = {}
        if isinstance(exc, RateLimited):
            headers["Retry-After"] = str(exc.retry_after)
        log.info(
            "handled_error",
            extra={"error_code": exc.code, "path": request.url.path, "status": exc.status_code},
        )
        return JSONResponse(status_code=exc.status_code, content=body, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Plain language, no internal types, no stack trace (CLAUDE.md §8, Law 12).
        problems = []
        for err in exc.errors():
            field = ".".join(str(p) for p in err["loc"] if p not in ("body", "query", "path"))
            problems.append({"field": field or "request", "problem": err["msg"]})
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_failed",
                "message": "Some of what you sent could not be accepted.",
                "problems": problems,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "http_error", "message": str(exc.detail)},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        log.exception("unhandled_error", extra={"request_id": request_id, "path": request.url.path})
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal",
                "message": "Something went wrong on our side. Nothing you did caused it.",
                "request_id": request_id,
            },
        )
