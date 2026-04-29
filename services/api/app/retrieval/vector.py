"""Vector similarity search backed by Chroma.

Embeds the query (cached), queries Chroma with workspace + filter metadata,
and resolves chunk ids back to full RetrievalCandidate rows so downstream
stages don't need to re-query the DB.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import chroma_client
from app.ai.embeddings import embed_one
from app.models import Chunk, Document
from app.retrieval.types import RetrievalCandidate, RetrievalFilters

log = logging.getLogger("api.retrieval.vector")


def _build_where(*, workspace_id: UUID, filters: RetrievalFilters) -> dict:
    """Chroma metadata filter. Chroma expects $and / $or for compound clauses."""
    clauses: list[dict] = [{"workspace_id": {"$eq": str(workspace_id)}}]
    if filters.source_types:
        if len(filters.source_types) == 1:
            clauses.append({"source_type": {"$eq": filters.source_types[0]}})
        else:
            clauses.append({"source_type": {"$in": filters.source_types}})
    if filters.document_ids:
        ids = [str(x) for x in filters.document_ids]
        if len(ids) == 1:
            clauses.append({"document_id": {"$eq": ids[0]}})
        else:
            clauses.append({"document_id": {"$in": ids}})
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


async def vector_search(
    *,
    session: AsyncSession,
    workspace_id: UUID,
    query: str,
    top_k: int = 20,
    filters: RetrievalFilters | None = None,
) -> list[RetrievalCandidate]:
    filters = filters or RetrievalFilters()
    embedding = embed_one(query, task_type="RETRIEVAL_QUERY")

    coll = chroma_client.get_collection()
    where = _build_where(workspace_id=workspace_id, filters=filters)
    res = coll.query(
        query_embeddings=[embedding],
        n_results=top_k,
        where=where,
    )

    ids = (res.get("ids") or [[]])[0]
    distances = (res.get("distances") or [[]])[0]
    if not ids:
        return []

    chunk_ids = [UUID(x) for x in ids]
    chunks = (
        await session.execute(
            select(Chunk, Document)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.id.in_(chunk_ids))
        )
    ).all()
    by_id = {c.id: (c, d) for c, d in chunks}

    out: list[RetrievalCandidate] = []
    for rank, (chunk_id_str, dist) in enumerate(zip(ids, distances, strict=False)):
        cid = UUID(chunk_id_str)
        if cid not in by_id:
            # Chunk vector exists but row was deleted — skip.
            continue
        chunk, doc = by_id[cid]
        # Cosine distance → similarity in [0, 1]. Chroma uses 1 - cosine_sim.
        similarity = max(0.0, 1.0 - float(dist or 0.0))
        out.append(
            RetrievalCandidate(
                chunk_id=chunk.id,
                document_id=doc.id,
                title=doc.title,
                text=chunk.text,
                source_type=doc.source_type,
                heading=chunk.heading,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                score=similarity,
                source_score=similarity,
                vector_rank=rank,
                source_timestamp=chunk.source_timestamp,
            )
        )

    log.info("retrieval.vector.done", extra={"hits": len(out), "top_k": top_k})
    return out
