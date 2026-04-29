"""Job status endpoints — including a polling-based SSE stream.

The SSE stream polls the workspace's recent jobs every second and emits a
delta whenever any job's (status, stage, attempts) tuple changes. Cheap, no
extra moving parts, good enough for an upload-status indicator.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_workspace, db_session
from app.db.session import SessionLocal
from app.models import IngestJob, Workspace
from app.schemas.jobs import JobOut

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

POLL_INTERVAL_SECONDS = 1.0
STREAM_LOOKBACK = timedelta(hours=24)
HEARTBEAT_EVERY = 15  # seconds


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: UUID,
    workspace: Workspace = Depends(current_workspace),
    session: AsyncSession = Depends(db_session),
) -> JobOut:
    job = await session.get(IngestJob, job_id)
    if job is None or job.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobOut.model_validate(job)


@router.get("/stream/sse")
async def stream_jobs(
    request: Request,
    workspace: Workspace = Depends(current_workspace),
):
    workspace_id = workspace.id
    return StreamingResponse(
        _job_event_stream(request, workspace_id=workspace_id),
        media_type="text/event-stream",
        headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
    )


async def _job_event_stream(request: Request, *, workspace_id: UUID):
    """Yield SSE events on (status, stage, attempts) deltas. The dependency
    layer already authed the caller; we open a fresh session here because
    the FastAPI request session would be closed by the time we yielded.
    """
    last_state: dict[str, tuple[str, str | None, int]] = {}
    last_heartbeat = asyncio.get_event_loop().time()

    while True:
        if await request.is_disconnected():
            return

        async with SessionLocal() as session:
            since = datetime.now(UTC) - STREAM_LOOKBACK
            rows = (
                await session.execute(
                    select(IngestJob)
                    .where(IngestJob.workspace_id == workspace_id)
                    .where(IngestJob.created_at >= since)
                    .order_by(IngestJob.created_at.desc())
                    .limit(50)
                )
            ).scalars().all()

        for job in rows:
            key = str(job.id)
            current = (job.status, job.stage, job.attempts)
            if last_state.get(key) != current:
                last_state[key] = current
                yield _sse_event("job", JobOut.model_validate(job).model_dump(mode="json"))

        now = asyncio.get_event_loop().time()
        if now - last_heartbeat >= HEARTBEAT_EVERY:
            last_heartbeat = now
            yield ": heartbeat\n\n"

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
