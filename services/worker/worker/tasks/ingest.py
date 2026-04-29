"""Celery task wrapping the async ingest orchestrator.

Each task call opens its own DB session via `app.db.session.SessionLocal`,
runs `app.services.ingest.ingest_document` to completion, and surfaces
failures to Celery's retry machinery (3 attempts, exponential backoff).
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from celery import Task

from app.services.ingest import ingest_document
from worker.celery_app import celery_app

log = logging.getLogger("worker.ingest")

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 10  # seconds → 10, 20, 40


@celery_app.task(
    name="worker.tasks.ingest.run",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=RETRY_BACKOFF_BASE,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=MAX_RETRIES,
)
def run_ingest(self: Task, job_id: str) -> dict:
    log.info("ingest.task.start", extra={"job_id": job_id, "attempt": self.request.retries + 1})
    return asyncio.run(_run(UUID(job_id)))


async def _run(job_id: UUID) -> dict:
    """Each Celery task call runs in a fresh event loop. The api process's
    long-lived engine has its asyncpg connection pool bound to a *different*
    loop, so reusing it here raises "Future attached to a different loop".
    Build a per-task engine, then dispose it.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import get_settings

    engine = create_async_engine(get_settings().DATABASE_URL, pool_pre_ping=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as session:
            return await ingest_document(session=session, job_id=job_id)
    finally:
        await engine.dispose()
