"""Request id, structured request logging, and the write rate limiter.

CLAUDE.md Law 13: every endpoint that creates or modifies data is rate limited.
ARCHITECTURE.md §5: a Redis token bucket keyed by user id, or by IP when the
caller is not signed in; 429 with `Retry-After`.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.clients import redis as redis_client
from backend.config.settings_env import get_env_settings
from backend.errors import Unauthorized
from backend.logging_config import request_id_var
from backend.services import security

log = logging.getLogger(__name__)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
WINDOW_SECONDS = 60

#: Endpoints a signed-out person must be able to reach even under load; they
#: are still limited, just by IP like everything else.
_EXEMPT_PATHS: set[str] = set()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """One id per request, on the request, in every log line, and in any 500."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        response.headers["X-Request-Id"] = request_id
        log.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "request_id": request_id,
            },
        )
        return response


class WriteRateLimitMiddleware(BaseHTTPMiddleware):
    """A fixed window of `RATE_LIMIT_WRITE_PER_MINUTE` writes per caller.

    If Redis is unreachable the limiter falls open with a logged warning: the
    platform staying up matters more than a local rate limit (ARCHITECTURE.md
    §8.4). That is recorded in the tracker's technical-debt list.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method not in WRITE_METHODS or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        env = get_env_settings()
        caller = _caller_key(request)
        key = f"ratelimit:write:{caller}"
        try:
            count = await redis_client.incr_with_expiry(key, WINDOW_SECONDS)
        except Exception:
            log.warning("rate_limit_falls_open_redis_unavailable", extra={"caller": caller})
            return await call_next(request)

        if count > env.RATE_LIMIT_WRITE_PER_MINUTE:
            retry_after = max(await redis_client.ttl(key), 1)
            log.info("rate_limited", extra={"caller": caller, "count": count})
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "message": (
                        "You are sending changes faster than the platform accepts them. "
                        f"Try again in {retry_after} seconds."
                    ),
                },
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)


def _caller_key(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        try:
            payload = security.decode_access_token(header[7:])
            return f"user:{payload['sub']}"
        except Unauthorized as exc:
            # Falls back to the IP bucket, which is the correct behavior for
            # an expired or malformed token — but logged, so a genuine fault
            # in decode_access_token does not silently degrade every
            # authenticated caller to a shared bucket unnoticed (Law 12;
            # audit demo-01 run 2).
            log.debug("rate_limit_caller_key_fell_back_to_ip", extra={"reason": exc.code})
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


def install_middleware(app) -> None:
    # Starlette runs middleware in reverse order of addition, so the request
    # context is outermost and every rate-limit rejection still carries an id.
    app.add_middleware(WriteRateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)
