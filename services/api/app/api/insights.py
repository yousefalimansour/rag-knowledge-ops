"""Insight + run endpoints.

Manual trigger (`POST /api/insights/run`) is rate-limited and creates a
queued run row immediately, then publishes a Celery task. The run is visible
in `GET /api/insights/runs` from that moment on.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_workspace, db_session
from app.core.rate_limit import RateLimit, client_ip
from app.models import Insight, InsightRun, Workspace
from app.schemas.insights import (
    InsightList,
    InsightOut,
    InsightRunList,
    InsightRunOut,
    InsightRunRequest,
    InsightRunResult,
    InsightStatePatch,
)

log = logging.getLogger("api.insights")
router = APIRouter(prefix="/api/insights", tags=["insights"])


def _manual_limiter() -> RateLimit:
    return RateLimit(name="insights_manual", capacity=2, window_seconds=60)


@router.get("", response_model=InsightList)
async def list_insights(
    type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    state: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    workspace: Workspace = Depends(current_workspace),
    session: AsyncSession = Depends(db_session),
) -> InsightList:
    stmt = select(Insight).where(Insight.workspace_id == workspace.id)
    if type:
        stmt = stmt.where(Insight.type == type)
    if severity:
        stmt = stmt.where(Insight.severity == severity)
    if state:
        stmt = stmt.where(Insight.state == state)
    if cursor:
        try:
            cdt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid cursor") from e
        stmt = stmt.where(Insight.created_at < cdt)

    stmt = stmt.order_by(desc(Insight.created_at)).limit(limit + 1)
    rows = (await session.execute(stmt)).scalars().all()
    next_cursor = None
    if len(rows) > limit:
        next_cursor = rows[limit - 1].created_at.isoformat()
        rows = rows[:limit]
    return InsightList(items=[InsightOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.get("/runs", response_model=InsightRunList)
async def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    workspace: Workspace = Depends(current_workspace),
    session: AsyncSession = Depends(db_session),
) -> InsightRunList:
    rows = (
        await session.execute(
            select(InsightRun)
            .where(InsightRun.workspace_id == workspace.id)
            .order_by(desc(InsightRun.created_at))
            .limit(limit)
        )
    ).scalars().all()
    return InsightRunList(items=[InsightRunOut.model_validate(r) for r in rows])


@router.post("/run", response_model=InsightRunResult, status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(
    payload: InsightRunRequest,
    request: Request,
    workspace: Workspace = Depends(current_workspace),
    session: AsyncSession = Depends(db_session),
) -> InsightRunResult:
    await _manual_limiter().hit(client_ip(request))

    if payload.scope == "documents" and not payload.document_ids:
        raise HTTPException(status_code=400, detail="document_ids required for scope=documents")

    # Persist a queued run row immediately so the user sees it in /runs.
    run = InsightRun(
        id=uuid4(),
        workspace_id=workspace.id,
        scope=f"manual:{payload.scope}",
        trigger="manual",
        status="queued",
        source_doc_ids=[str(d) for d in payload.document_ids],
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.commit()

    _publish_manual(
        workspace_id=workspace.id,
        scope=payload.scope,
        document_ids=[str(d) for d in payload.document_ids],
    )
    return InsightRunResult(run_id=run.id, status="queued")


@router.get("/{insight_id}", response_model=InsightOut)
async def get_insight(
    insight_id: UUID,
    workspace: Workspace = Depends(current_workspace),
    session: AsyncSession = Depends(db_session),
) -> InsightOut:
    ins = await session.get(Insight, insight_id)
    if ins is None or ins.workspace_id != workspace.id:
        raise HTTPException(status_code=404, detail="Insight not found")
    return InsightOut.model_validate(ins)


@router.patch("/{insight_id}", response_model=InsightOut)
async def patch_insight_state(
    insight_id: UUID,
    payload: InsightStatePatch,
    workspace: Workspace = Depends(current_workspace),
    session: AsyncSession = Depends(db_session),
) -> InsightOut:
    ins = await session.get(Insight, insight_id)
    if ins is None or ins.workspace_id != workspace.id:
        raise HTTPException(status_code=404, detail="Insight not found")
    ins.state = payload.state
    await session.commit()
    await session.refresh(ins)
    return InsightOut.model_validate(ins)


def _publish_manual(
    *, workspace_id: UUID, scope: str, document_ids: list[str]
) -> None:
    from app.core.publisher import publish

    publish(
        "worker.tasks.insights.manual",
        str(workspace_id),
        scope,
        document_ids,
    )
