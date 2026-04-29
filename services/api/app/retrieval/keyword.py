"""Postgres lexical search.

Uses `to_tsquery` + `ts_rank` over the `chunks.content_tsv` column (the
`tsvector` generated in the 0002 migration). On SQLite (test env) the
column is missing; we fall back to a simple `ILIKE` over `chunks.text`.
"""

from __future__ import annotations

import logging
import re
from uuid import UUID

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Document
from app.retrieval.types import RetrievalCandidate, RetrievalFilters

log = logging.getLogger("api.retrieval.keyword")

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def _to_tsquery(question: str) -> str:
    """Build a Postgres tsquery from the user's question.

    Uses OR over the surviving terms after stop-style filtering — for a
    short demo corpus that's lenient enough to find matches without being
    too noisy. Two-character words are dropped to reduce match noise.
    """
    words = [w for w in _WORD_RE.findall(question.lower()) if len(w) > 2]
    return " | ".join(words) if words else question


async def keyword_search(
    *,
    session: AsyncSession,
    workspace_id: UUID,
    query: str,
    top_k: int = 20,
    filters: RetrievalFilters | None = None,
) -> list[RetrievalCandidate]:
    filters = filters or RetrievalFilters()
    is_postgres = session.bind.dialect.name == "postgresql"  # type: ignore[union-attr]

    if is_postgres:
        return await _postgres_search(
            session=session, workspace_id=workspace_id, query=query, top_k=top_k, filters=filters
        )
    return await _sqlite_fallback(
        session=session, workspace_id=workspace_id, query=query, top_k=top_k, filters=filters
    )


async def _postgres_search(
    *,
    session: AsyncSession,
    workspace_id: UUID,
    query: str,
    top_k: int,
    filters: RetrievalFilters,
) -> list[RetrievalCandidate]:
    tsq = _to_tsquery(query)
    sql_parts = [
        "SELECT c.id, c.text, c.heading, c.page_number, c.chunk_index, c.source_timestamp,",
        "       d.id AS document_id, d.title, d.source_type,",
        "       ts_rank(c.content_tsv, q) AS rank",
        "FROM chunks c",
        "JOIN documents d ON d.id = c.document_id,",
        "     to_tsquery('english', :tsq) q",
        "WHERE d.workspace_id = :wid AND c.content_tsv @@ q",
    ]
    params: dict[str, object] = {"tsq": tsq, "wid": str(workspace_id)}

    if filters.source_types:
        sql_parts.append("  AND d.source_type = ANY(:srcs)")
        params["srcs"] = list(filters.source_types)
    if filters.document_ids:
        sql_parts.append("  AND d.id = ANY(:dids)")
        params["dids"] = [str(x) for x in filters.document_ids]

    sql_parts.append("ORDER BY rank DESC")
    sql_parts.append("LIMIT :limit")
    params["limit"] = top_k

    stmt = text("\n".join(sql_parts))
    rows = (await session.execute(stmt, params)).all()
    out: list[RetrievalCandidate] = []
    for rank_idx, r in enumerate(rows):
        out.append(
            RetrievalCandidate(
                chunk_id=r.id if isinstance(r.id, UUID) else UUID(str(r.id)),
                document_id=r.document_id if isinstance(r.document_id, UUID) else UUID(str(r.document_id)),
                title=r.title,
                text=r.text,
                source_type=r.source_type,
                heading=r.heading,
                page_number=r.page_number,
                chunk_index=r.chunk_index,
                score=float(r.rank or 0.0),
                source_score=min(1.0, float(r.rank or 0.0)),
                keyword_rank=rank_idx,
                source_timestamp=r.source_timestamp,
            )
        )
    log.info("retrieval.keyword.done", extra={"hits": len(out), "tsq": tsq})
    return out


async def _sqlite_fallback(
    *,
    session: AsyncSession,
    workspace_id: UUID,
    query: str,
    top_k: int,
    filters: RetrievalFilters,
) -> list[RetrievalCandidate]:
    terms = [w for w in _WORD_RE.findall(query.lower()) if len(w) > 2]
    if not terms:
        return []

    stmt = select(Chunk, Document).join(Document, Document.id == Chunk.document_id).where(
        Document.workspace_id == workspace_id
    )
    if filters.source_types:
        stmt = stmt.where(Document.source_type.in_(filters.source_types))
    if filters.document_ids:
        stmt = stmt.where(Document.id.in_(filters.document_ids))

    rows = (await session.execute(stmt)).all()
    scored: list[tuple[float, Chunk, Document]] = []
    for chunk, doc in rows:
        body = chunk.text.lower()
        hits = sum(body.count(t) for t in terms)
        if hits:
            scored.append((float(hits), chunk, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[RetrievalCandidate] = []
    for rank_idx, (score, chunk, doc) in enumerate(scored[:top_k]):
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
                score=score,
                source_score=min(1.0, score / max(1.0, scored[0][0])),
                keyword_rank=rank_idx,
                source_timestamp=chunk.source_timestamp,
            )
        )
    return out
