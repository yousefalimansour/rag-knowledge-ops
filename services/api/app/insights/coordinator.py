"""Watermark-based coordinator (Celery Beat every 30 min).

Picks up every doc that's become `ready` since the last successful coordinator
run for the workspace, enqueues a scoped generation per batch, and bumps the
watermark forward. Bound by COORD_BATCH so a long-idle catch-up still finishes.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.insights.repo import close_run, open_run
from app.insights.scoped import run_scoped
from app.models import Document, InsightRun, Workspace

log = logging.getLogger("api.insights.coordinator")

COORD_BATCH = 25
LOOKBACK_FALLBACK = timedelta(days=2)


async def run_coordinator_all_workspaces(*, session: AsyncSession) -> dict:
    workspaces = (await session.execute(select(Workspace))).scalars().all()
    summary = {"workspaces": 0, "total_new": 0, "total_skipped": 0}
    for ws in workspaces:
        s = await run_coordinator_for_workspace(session=session, workspace_id=ws.id)
        summary["workspaces"] += 1
        summary["total_new"] += s.get("generated", 0)
        summary["total_skipped"] += s.get("skipped", 0)
    return summary


async def run_coordinator_for_workspace(
    *, session: AsyncSession, workspace_id: UUID
) -> dict:
    last_run = (
        await session.execute(
            select(InsightRun)
            .where(
                InsightRun.workspace_id == workspace_id,
                InsightRun.trigger == "coordinator",
                InsightRun.status == "succeeded",
            )
            .order_by(desc(InsightRun.finished_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    watermark = last_run.watermark_after if (last_run and last_run.watermark_after) else None
    if watermark is None:
        watermark = datetime.now(UTC) - LOOKBACK_FALLBACK

    candidates = (
        await session.execute(
            select(Document.id, Document.updated_at)
            .where(
                Document.workspace_id == workspace_id,
                Document.status == "ready",
                Document.updated_at > watermark,
            )
            .order_by(Document.updated_at)
            .limit(COORD_BATCH)
        )
    ).all()
    if not candidates:
        # Still record a run so the watermark can advance to "now" on idle systems.
        run = await open_run(
            session=session,
            workspace_id=workspace_id,
            scope="coordinator",
            trigger="coordinator",
            source_doc_ids=[],
        )
        await close_run(
            session=session, run=run, status="succeeded", watermark_after=watermark
        )
        return {"run_id": str(run.id), "generated": 0, "skipped": 0, "documents": 0}

    doc_ids = [row.id for row in candidates]
    new_watermark = max(row.updated_at for row in candidates)

    run = await open_run(
        session=session,
        workspace_id=workspace_id,
        scope=f"coordinator:{len(doc_ids)} docs",
        trigger="coordinator",
        source_doc_ids=[str(d) for d in doc_ids],
    )
    try:
        scoped_result = await run_scoped(
            session=session, workspace_id=workspace_id, doc_ids=doc_ids
        )
        # Roll the scoped run's counts up into the coordinator run for visibility.
        run.insights_generated += scoped_result.get("generated", 0)
        run.insights_skipped += scoped_result.get("skipped", 0)
        await close_run(
            session=session,
            run=run,
            status="succeeded",
            watermark_after=new_watermark,
        )
        return {
            "run_id": str(run.id),
            "generated": scoped_result.get("generated", 0),
            "skipped": scoped_result.get("skipped", 0),
            "documents": len(doc_ids),
        }
    except Exception as e:  # noqa: BLE001
        log.exception("insights.coordinator.failed")
        await close_run(session=session, run=run, status="failed", error=str(e))
        raise
