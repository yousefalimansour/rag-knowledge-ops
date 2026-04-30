"""Notification dispatcher.

Owns the rules for *who* gets notified about *what*. The two callers right
now are the insight generators and the ingest task.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Insight, Notification, UserWorkspace

log = logging.getLogger("api.notifications.dispatcher")

NOTIFY_SEVERITY_THRESHOLD = {"medium", "high"}


async def notify_insight_created(
    *, session: AsyncSession, insight: Insight
) -> list[Notification]:
    """Fan-out to every member of the workspace for medium+ severity."""
    if insight.severity not in NOTIFY_SEVERITY_THRESHOLD:
        return []

    members = (
        await session.execute(
            select(UserWorkspace.user_id).where(
                UserWorkspace.workspace_id == insight.workspace_id
            )
        )
    ).scalars().all()
    if not members:
        return []

    out: list[Notification] = []
    for user_id in members:
        notif = Notification(
            id=uuid4(),
            user_id=user_id,
            workspace_id=insight.workspace_id,
            type="insight_created",
            title=insight.title,
            body=insight.summary[:500],
            severity=insight.severity,
            link_kind="insight",
            link_id=insight.id,
        )
        session.add(notif)
        out.append(notif)
    await session.flush()
    log.info(
        "notify.insight_created",
        extra={"insight_id": str(insight.id), "fanout": len(out)},
    )
    return out


async def notify_ingest_completed(
    *,
    session: AsyncSession,
    workspace_id: UUID,
    document_id: UUID,
    document_title: str,
    chunk_count: int,
    failed: bool = False,
    error: str | None = None,
) -> list[Notification]:
    members = (
        await session.execute(
            select(UserWorkspace.user_id).where(
                UserWorkspace.workspace_id == workspace_id
            )
        )
    ).scalars().all()
    if not members:
        return []

    out: list[Notification] = []
    for user_id in members:
        notif = Notification(
            id=uuid4(),
            user_id=user_id,
            workspace_id=workspace_id,
            type="ingest_failed" if failed else "ingest_completed",
            title=("Ingestion failed: " if failed else "Document ready: ") + document_title,
            body=(error or "")[:500] if failed else f"{chunk_count} chunks indexed.",
            severity="high" if failed else "info",
            link_kind="document",
            link_id=document_id,
        )
        session.add(notif)
        out.append(notif)
    await session.flush()
    return out
