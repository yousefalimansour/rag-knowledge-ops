"""Nightly audit (Celery Beat at 03:00).

Pulls every workspace's chunks (capped) and runs:
- conflict + repeated_decision generation in document-shaped batches
- stale-document scan

We deliberately don't pull in HDBSCAN for the demo — instead we use document
boundaries as natural clusters, with a configurable cap on chunks per
workspace to keep one big workspace from monopolizing the run.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.insights.generator import chunks_to_candidates, generate_from_candidates
from app.insights.repo import close_run, open_run
from app.insights.stale import scan_stale_documents
from app.models import Chunk, Document, Workspace

log = logging.getLogger("api.insights.nightly")

MAX_CHUNKS_PER_WORKSPACE = 60
MAX_CHUNKS_PER_BATCH = 18


async def run_nightly_all_workspaces(*, session: AsyncSession) -> dict:
    workspaces = (await session.execute(select(Workspace))).scalars().all()
    summary = {"workspaces": 0, "total_new": 0, "total_skipped": 0}
    for ws in workspaces:
        s = await run_nightly_for_workspace(session=session, workspace_id=ws.id)
        summary["workspaces"] += 1
        summary["total_new"] += s.get("generated", 0)
        summary["total_skipped"] += s.get("skipped", 0)
    return summary


async def run_nightly_for_workspace(
    *, session: AsyncSession, workspace_id: UUID
) -> dict:
    run = await open_run(
        session=session,
        workspace_id=workspace_id,
        scope="nightly",
        trigger="nightly",
        source_doc_ids=[],
    )
    try:
        # 1. conflict + repeated-decision over batches of recent chunks.
        rows = (
            await session.execute(
                select(Chunk, Document)
                .join(Document, Document.id == Chunk.document_id)
                .where(
                    Document.workspace_id == workspace_id,
                    Document.status == "ready",
                )
                .order_by(Document.updated_at.desc(), Chunk.chunk_index)
                .limit(MAX_CHUNKS_PER_WORKSPACE)
            )
        ).all()
        candidates = chunks_to_candidates(list(rows))
        new_count = 0
        for i in range(0, len(candidates), MAX_CHUNKS_PER_BATCH):
            batch = candidates[i : i + MAX_CHUNKS_PER_BATCH]
            new_count += await generate_from_candidates(
                session=session,
                run=run,
                workspace_id=workspace_id,
                candidates=batch,
            )

        # 2. stale documents (deterministic).
        new_count += await scan_stale_documents(
            session=session, run=run, workspace_id=workspace_id
        )

        await close_run(session=session, run=run, status="succeeded")
        return {
            "run_id": str(run.id),
            "generated": new_count,
            "skipped": run.insights_skipped,
        }
    except Exception as e:  # noqa: BLE001
        log.exception("insights.nightly.failed")
        await close_run(session=session, run=run, status="failed", error=str(e))
        raise


async def run_manual(
    *,
    session: AsyncSession,
    workspace_id: UUID,
    scope: str,
    document_ids: list[UUID] | None = None,
) -> dict:
    """`POST /api/insights/run` enters here. We treat scope='all' like a
    nightly audit on this workspace; scope='documents' as a scoped run.
    """
    if scope == "documents" and document_ids:
        from app.insights.scoped import run_scoped

        return await run_scoped(
            session=session, workspace_id=workspace_id, doc_ids=document_ids
        )
    return await run_nightly_for_workspace(session=session, workspace_id=workspace_id)
