"""Structured JSON logging shared by api + worker.

The api sets its `service` field to `"api"`. The worker calls
`configure_logging(service="worker")` once at boot. `request_id` and `user_id`
are pulled from contextvars so any code path can attach them without threading
the value through every function signature.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from uuid import uuid4

from pythonjsonlogger import jsonlogger

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)


class ContextFilter(logging.Filter):
    def __init__(self, *, service: str = "api") -> None:
        super().__init__()
        self._service = service

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        record.user_id = user_id_ctx.get()
        record.service = self._service
        return True


def configure_logging(level: str = "INFO", *, service: str = "api") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s "
            "%(service)s %(request_id)s %(user_id)s",
            rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
        )
    )
    handler.addFilter(ContextFilter(service=service))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def new_request_id() -> str:
    return uuid4().hex


def set_request_id(rid: str | None) -> None:
    """Helper for places that need to push a request_id without entering a
    middleware context — used by the worker on each task to inherit from the
    publisher's headers.
    """
    request_id_ctx.set(rid)
