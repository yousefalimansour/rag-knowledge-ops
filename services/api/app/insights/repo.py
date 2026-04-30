"""Persistence helpers for insights + runs.

`open_run` / `close_run` bracket every generator invocation so failures are
surfaced in the run history regardless of which generator raised. `save_insight`
performs the dedup-hash check before insert and counts skipped duplicates on
the run record.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Insight, InsightRun

log = logging.getLogger("api.insights.repo")


async def open_run(
    *,
    session: AsyncSession,
    workspace_id: UUID,
    scope: str,
    trigger: str,
    source_doc_ids: list[str] | None = None,
) -> InsightRun:
    run = InsightRun(
        id=uuid4(),
        workspace_id=workspace_id,
        scope=scope,
        trigger=trigger,
        status="running",
        source_doc_ids=source_doc_ids or [],
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def close_run(
    *,
    session: AsyncSession,
    run: InsightRun,
    status: str,
    error: str | None = None,
    watermark_after: datetime | None = None,
) -> None:
    run.status = status
    run.error = (error or "")[:2000] if error else None
    run.finished_at = datetime.now(UTC)
    if watermark_after:
        run.watermark_after = watermark_after
    await session.commit()


async def save_insight(
    *,
    session: AsyncSession,
    run: InsightRun,
    workspace_id: UUID,
    type_: str,
    title: str,
    summary: str,
    severity: str,
    confidence: float | None,
    evidence: list[dict[str, Any]],
    dedup_hash: str,
) -> Insight | None:
    """Inserts a new insight. Returns None if dedup conflict (already exists).

    The unique index on `dedup_hash` makes the dedup race-free even when two
    runs touch the same key concurrently.
    """
    existing = (
        await session.execute(select(Insight).where(Insight.dedup_hash == dedup_hash))
    ).scalar_one_or_none()
    if existing is not None:
        run.insights_skipped += 1
        await session.commit()
        return None

    insight = Insight(
        id=uuid4(),
        workspace_id=workspace_id,
        type=type_,
        title=title[:500],
        summary=summary,
        severity=severity,
        confidence=confidence,
        evidence=evidence,
        dedup_hash=dedup_hash,
        state="active",
    )
    session.add(insight)
    try:
        await session.flush()
    except IntegrityError:
        # Race: another worker just persisted the same dedup_hash.
        await session.rollback()
        run.insights_skipped += 1
        await session.commit()
        return None

    run.insights_generated += 1
    await session.commit()
    await session.refresh(insight)
    return insight
