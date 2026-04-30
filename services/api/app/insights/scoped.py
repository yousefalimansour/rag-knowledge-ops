"""Post-ingest scoped insight generation.

For each newly-ingested doc, gather its chunks plus the most-similar chunks
from existing docs in the workspace, then run the LLM generator on that
slice. Cheap relative to a full audit; runs immediately after ingest.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed_one
from app.ai import chroma_client
from app.insights.generator import chunks_to_candidates, generate_from_candidates
from app.insights.repo import close_run, open_run
from app.models import Chunk, Document
from app.retrieval.types import RetrievalCandidate

log = logging.getLogger("api.insights.scoped")

MAX_CHUNKS_PER_DOC = 8
SIMILAR_PEERS = 6


async def run_scoped(
    *, session: AsyncSession, workspace_id: UUID, doc_ids: list[UUID]
) -> dict:
    scope = f"post_ingest:{','.join(str(d)[:8] for d in doc_ids)}"
    run = await open_run(
        session=session,
        workspace_id=workspace_id,
        scope=scope,
        trigger="post_ingest",
        source_doc_ids=[str(d) for d in doc_ids],
    )
    try:
        total_new = 0
        for doc_id in doc_ids:
            candidates = await _collect_candidates(
                session=session, workspace_id=workspace_id, doc_id=doc_id
            )
            if len(candidates) < 2:
                continue
            total_new += await generate_from_candidates(
                session=session,
                run=run,
                workspace_id=workspace_id,
                candidates=candidates,
            )

        await close_run(session=session, run=run, status="succeeded")
        log.info(
            "insights.scoped.complete",
            extra={"run_id": str(run.id), "generated": total_new, "skipped": run.insights_skipped},
        )
        return {
            "run_id": str(run.id),
            "generated": total_new,
            "skipped": run.insights_skipped,
        }
    except Exception as e:  # noqa: BLE001
        log.exception("insights.scoped.failed")
        await close_run(session=session, run=run, status="failed", error=str(e))
        raise


async def _collect_candidates(
    *, session: AsyncSession, workspace_id: UUID, doc_id: UUID
) -> list[RetrievalCandidate]:
    """Doc's own chunks + top similar peers from other docs."""
    own = (
        await session.execute(
            select(Chunk, Document)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.document_id == doc_id)
            .order_by(Chunk.chunk_index)
            .limit(MAX_CHUNKS_PER_DOC)
        )
    ).all()
    own_candidates = chunks_to_candidates(list(own))
    if not own_candidates:
        return []

    # Use the doc's first chunk text as the anchor for similar-peer search.
    anchor_text = own_candidates[0].text
    try:
        anchor_vec = embed_one(anchor_text, task_type="RETRIEVAL_DOCUMENT")
    except Exception as e:  # noqa: BLE001
        log.warning("insights.scoped.embed_failed", extra={"error": str(e)[:120]})
        return own_candidates

    coll = chroma_client.get_collection()
    res = coll.query(
        query_embeddings=[anchor_vec],
        n_results=SIMILAR_PEERS + MAX_CHUNKS_PER_DOC,
        where={"workspace_id": {"$eq": str(workspace_id)}},
    )
    peer_ids = (res.get("ids") or [[]])[0]
    own_chunk_ids = {str(c.chunk_id) for c in own_candidates}
    peer_uuids = [
        UUID(x) for x in peer_ids if x not in own_chunk_ids
    ][:SIMILAR_PEERS]
    if not peer_uuids:
        return own_candidates

    peers = (
        await session.execute(
            select(Chunk, Document)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.id.in_(peer_uuids))
        )
    ).all()
    return own_candidates + chunks_to_candidates(list(peers))
