"""Celery app shared by the worker and beat services.

Tasks live under `worker.tasks.*`. The `app.*` package (FastAPI service) is
mounted on the same PYTHONPATH so workers can reuse models, settings, AI
clients, etc. — no duplication.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.core.logging import configure_logging

_settings = get_settings()


def _crontab_from_str(expr: str) -> crontab:
    minute, hour, day_of_month, month_of_year, day_of_week = expr.split()
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        day_of_week=day_of_week,
    )


celery_app = Celery(
    "kops",
    broker=_settings.REDIS_URL,
    backend=_settings.REDIS_URL,
    include=[
        "worker.context",  # signal handlers — must be imported so they register
        "worker.tasks.ping",
        "worker.tasks.ingest",
        "worker.tasks.insights",
    ],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=10,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

# Beat schedules — both cadences run real generators (step 05).
celery_app.conf.beat_schedule = {
    "insight-coordinator-30m": {
        "task": "worker.tasks.insights.coordinator",
        "schedule": _crontab_from_str(_settings.INSIGHT_COORDINATOR_CRON),
    },
    "insight-nightly-audit": {
        "task": "worker.tasks.insights.nightly",
        "schedule": _crontab_from_str(_settings.INSIGHT_NIGHTLY_AUDIT_CRON),
    },
}


@celery_app.on_after_configure.connect
def _on_configure(sender, **_kwargs):  # noqa: ARG001
    configure_logging("INFO", service="worker")
