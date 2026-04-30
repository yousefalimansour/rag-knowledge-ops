"""Celery publisher used by the api process.

The api never imports the worker package (separate PYTHONPATH inside its
container), so the worker's `after_task_publish` signal handler isn't
registered here. Instead we attach the current request_id to the task
headers explicitly — the worker's `task_prerun` signal picks it up on the
other side.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.core.logging import request_id_ctx

log = logging.getLogger("api.publisher")


@lru_cache(maxsize=1)
def _celery_publisher():
    from celery import Celery

    return Celery(
        "kops-publisher",
        broker=get_settings().REDIS_URL,
        backend=get_settings().REDIS_URL,
    )


def publish(task_name: str, *args: Any, **kwargs: Any) -> None:
    """Send a task. Auto-attaches the current api request_id to message headers
    so the worker side can correlate logs back to the originating HTTP request.
    """
    rid = request_id_ctx.get()
    headers = {"request_id": rid} if rid else None
    try:
        _celery_publisher().send_task(
            task_name,
            args=list(args) if args else None,
            kwargs=kwargs or None,
            headers=headers,
        )
    except Exception as e:  # noqa: BLE001
        log.warning(
            "publisher.send_failed",
            extra={"task": task_name, "error": str(e)[:120]},
        )
