"""Smoke + scheduled-stub tasks.

Real ingestion lands in step 02; real insight tasks in step 05.
The stubs here exist so beat starts cleanly and `celery inspect ping`
proves the broker wiring works.
"""

from __future__ import annotations

import logging

from worker.celery_app import celery_app

log = logging.getLogger("worker.ping")


@celery_app.task(name="worker.tasks.ping.ping")
def ping() -> str:
    log.info("worker.ping")
    return "pong"


@celery_app.task(name="worker.tasks.ping.coordinator_stub")
def coordinator_stub() -> str:
    log.info("worker.coordinator_stub.tick")
    return "coordinator-stub-ok"


@celery_app.task(name="worker.tasks.ping.nightly_audit_stub")
def nightly_audit_stub() -> str:
    log.info("worker.nightly_audit_stub.tick")
    return "nightly-stub-ok"
