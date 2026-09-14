"""Structured logging with a request id on every line.

One JSON object per line so a log file can be read by a person and by a tool.
The request id is set by `RequestIdMiddleware` and follows the request through
every log line it produces, which is what the 500 handler hands the client.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_STANDARD = set(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
) | {"asctime", "message", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def safe_extra(**fields) -> dict:
    """Rename any field that would collide with a LogRecord attribute.

    `logging` raises when an `extra` key shadows one of its own (`created`,
    `module`, `message`, ...). A log line must never be the reason a background
    job dies, so the collision is renamed rather than raised.
    """
    return {
        (f"field_{key}" if key in _STANDARD else key): value
        for key, value in fields.items()
    }


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # Access logs duplicate our own request logging.
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False
