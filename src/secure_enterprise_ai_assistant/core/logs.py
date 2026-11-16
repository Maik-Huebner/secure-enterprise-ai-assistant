"""Structured JSON logging with a per-request correlation ID.

Logs are written to stderr only: the MCP stdio transport owns stdout. User query text is never
logged; callers log technical metadata such as length, intent, duration, and outcome.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, TextIO

LOGGER_NAMESPACE = "secure_enterprise_ai_assistant"

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

# Library default: stay silent until an entry point calls configure_logging().
logging.getLogger(LOGGER_NAMESPACE).addHandler(logging.NullHandler())

# Attributes every LogRecord has; anything else was passed via ``extra`` and is emitted as data.
_STANDARD_RECORD_FIELDS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys() | {"message", "asctime"}
)


def current_request_id() -> str | None:
    """Return the correlation ID bound to the current execution context, if any."""
    return _request_id.get()


@contextmanager
def request_context(request_id: str | None = None) -> Iterator[str]:
    """Bind a correlation ID for the duration of one request."""
    value = request_id or uuid.uuid4().hex
    token = _request_id.set(value)
    try:
        yield value
    finally:
        _request_id.reset(token)


class JsonFormatter(logging.Formatter):
    """Render one log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = current_request_id()
        if request_id is not None:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_FIELDS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            payload["error_type"] = record.exc_info[0].__name__
            payload["traceback"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class JsonStreamHandler(logging.StreamHandler[TextIO]):
    """Stream handler that always uses the JSON formatter."""

    def __init__(self, stream: TextIO) -> None:
        super().__init__(stream)
        self.setFormatter(JsonFormatter())


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    """Install one JSON handler (stderr by default) on the package logger."""
    logger = logging.getLogger(LOGGER_NAMESPACE)
    logger.setLevel(level.upper())
    logger.propagate = False
    for handler in [item for item in logger.handlers if isinstance(item, JsonStreamHandler)]:
        logger.removeHandler(handler)
    logger.addHandler(JsonStreamHandler(stream or sys.stderr))


def get_logger(name: str) -> logging.Logger:
    """Return a logger below the package namespace."""
    if name == LOGGER_NAMESPACE or name.startswith(f"{LOGGER_NAMESPACE}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_NAMESPACE}.{name}")
