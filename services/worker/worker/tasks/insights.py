"""Celery tasks driving the insight cadences.

Each task is sync (Celery's runtime) and shells into the async generators via
`asyncio.run`. Each call builds its own engine inside the task's event loop —
same trick the ingest task uses to avoid asyncpg loop conflicts.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from celery import Task

from worker.celery_app import celery_app

log = logging.getLogger("worker.insights")


def _build_session_factory():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import get_settings

    engine = create_async_engine(get_settings().DATABASE_URL, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(
    name="worker.tasks.insights.scoped",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=10,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=2,
)
def run_scoped_task(self: Task, workspace_id: str, doc_ids: list[str]) -> dict:
    log.info(
        "insights.scoped.task.start",
        extra={"workspace_id": workspace_id, "docs": len(doc_ids), "attempt": self.request.retries + 1},
    )
    return asyncio.run(_scoped(UUID(workspace_id), [UUID(d) for d in doc_ids]))


async def _scoped(workspace_id: UUID, doc_ids: list[UUID]) -> dict:
    from app.insights.scoped import run_scoped

    engine, Session = _build_session_factory()
    try:
        async with Session() as session:
            return await run_scoped(
                session=session, workspace_id=workspace_id, doc_ids=doc_ids
            )
    finally:
        await engine.dispose()


@celery_app.task(name="worker.tasks.insights.coordinator")
def run_coordinator_task() -> dict:
    log.info("insights.coordinator.task.start")
    return asyncio.run(_coordinator())


async def _coordinator() -> dict:
    from app.insights.coordinator import run_coordinator_all_workspaces

    engine, Session = _build_session_factory()
    try:
        async with Session() as session:
            return await run_coordinator_all_workspaces(session=session)
    finally:
        await engine.dispose()


@celery_app.task(name="worker.tasks.insights.nightly")
def run_nightly_task() -> dict:
    log.info("insights.nightly.task.start")
    return asyncio.run(_nightly())


async def _nightly() -> dict:
    from app.insights.nightly import run_nightly_all_workspaces

    engine, Session = _build_session_factory()
    try:
        async with Session() as session:
            return await run_nightly_all_workspaces(session=session)
    finally:
        await engine.dispose()


@celery_app.task(
    name="worker.tasks.insights.manual",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=10,
    max_retries=1,
)
def run_manual_task(
    self: Task, workspace_id: str, scope: str, document_ids: list[str] | None = None
) -> dict:
    log.info(
        "insights.manual.task.start",
        extra={"workspace_id": workspace_id, "scope": scope},
    )
    return asyncio.run(
        _manual(
            UUID(workspace_id),
            scope,
            [UUID(d) for d in (document_ids or [])],
        )
    )


async def _manual(
    workspace_id: UUID, scope: str, document_ids: list[UUID]
) -> dict:
    from app.insights.nightly import run_manual

    engine, Session = _build_session_factory()
    try:
        async with Session() as session:
            return await run_manual(
                session=session,
                workspace_id=workspace_id,
                scope=scope,
                document_ids=document_ids,
            )
    finally:
        await engine.dispose()
