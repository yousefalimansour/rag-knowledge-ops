"""Celery signal handlers that propagate api → worker request_id.

The api process publishes tasks with `headers={'request_id': <id>}`.
On each task pickup, `task_prerun` reads that header and pushes it into the
worker's `request_id_ctx`. Subsequent log lines automatically carry it.
"""

from __future__ import annotations

import logging
from typing import Any

from celery.signals import (
    after_task_publish,
    setup_logging,
    task_postrun,
    task_prerun,
    worker_process_init,
)

from app.core.logging import configure_logging, request_id_ctx

log = logging.getLogger("worker.context")


@setup_logging.connect
def _setup_logging(**_kwargs) -> None:
    """Connecting to `setup_logging` tells Celery NOT to install its default
    plain-text root logger. We install our JSON formatter instead so the
    worker's log shape matches the api's.
    """
    configure_logging("INFO", service="worker")


@worker_process_init.connect
def _reconfigure_in_prefork_child(**_kwargs) -> None:
    """Each prefork child inherits parent loggers but POSIX `fork()` resets
    some handler state. Re-applying here is cheap and idempotent.
    """
    configure_logging("INFO", service="worker")


@after_task_publish.connect
def _attach_request_id_on_publish(
    sender: str | None = None,
    headers: dict | None = None,
    body: Any = None,
    **_kwargs,
) -> None:
    """Runs in the *publisher* (api) when a task is sent. Attach the current
    api request_id to the task's headers so the worker can pick it up.
    """
    rid = request_id_ctx.get()
    if rid and isinstance(headers, dict):
        headers.setdefault("request_id", rid)


@task_prerun.connect
def _set_request_id_from_headers(
    task_id: str | None = None,
    task: Any = None,
    **_kwargs,
) -> None:
    """Runs in the *worker* before each task body executes. Pull request_id
    from the task's request headers (where the api publisher put it) and
    set the contextvar so log lines below this point inherit it.
    """
    headers = getattr(getattr(task, "request", None), "headers", None) or {}
    rid = headers.get("request_id") if isinstance(headers, dict) else None
    if not rid:
        # Fall back to the task id so we always have *something* to correlate.
        rid = task_id
    request_id_ctx.set(rid)


@task_postrun.connect
def _clear_request_id(**_kwargs) -> None:
    request_id_ctx.set(None)
