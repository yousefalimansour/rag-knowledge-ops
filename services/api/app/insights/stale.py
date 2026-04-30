"""Stale-document detection.

A purely deterministic scan — no LLM. A document is "stale" when:
- It is `ready` and has chunks
- Its `updated_at` is older than STALENESS_DAYS days

The dedup_hash is keyed by `('stale_document', [first chunk id], doc title)`
so a doc only produces one stale insight regardless of re-runs.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.insights.dedup import dedup_hash
from app.insights.repo import save_insight
from app.models import Chunk, Document, InsightRun
from app.notifications.dispatcher import notify_insight_created

log = logging.getLogger("api.insights.stale")

STALENESS_DAYS = 90


async def scan_stale_documents(
    *, session: AsyncSession, run: InsightRun, workspace_id: UUID
) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=STALENESS_DAYS)
    docs = (
        await session.execute(
            select(Document).where(
                Document.workspace_id == workspace_id,
                Document.status == "ready",
                Document.chunk_count > 0,
                Document.updated_at < cutoff,
            )
        )
    ).scalars().all()

    persisted = 0
    for doc in docs:
        first_chunk = (
            await session.execute(
                select(Chunk.id).where(Chunk.document_id == doc.id).order_by(Chunk.chunk_index).limit(1)
            )
        ).scalar_one_or_none()
        if first_chunk is None:
            continue

        title = f"Stale document: {doc.title}"
        days_old = (datetime.now(UTC) - doc.updated_at).days
        summary = (
            f"{doc.title} hasn't been updated in {days_old} days. "
            "If it's still relied on, consider reviewing it."
        )
        insight = await save_insight(
            session=session,
            run=run,
            workspace_id=workspace_id,
            type_="stale_document",
            title=title,
            summary=summary,
            severity="low",
            confidence=None,
            evidence=[
                {
                    "chunk_id": str(first_chunk),
                    "document_id": str(doc.id),
                    "title": doc.title,
                    "snippet": "",
                    "heading": None,
                    "page": None,
                }
            ],
            dedup_hash=dedup_hash(
                type_="stale_document",
                source_chunk_ids=[first_chunk],
                title=title,
            ),
        )
        if insight is not None:
            await notify_insight_created(session=session, insight=insight)
            await session.commit()
            persisted += 1

    return persisted
