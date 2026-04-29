"""Raw retrieval endpoint — no LLM step.

Useful for the Knowledge Search UI and for inspecting why a question got
the answer it did. Same pipeline as `/api/ai/query` minus the reasoning
prompt: rewrite → vector + keyword → fuse → rerank → return.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_workspace, db_session
from app.core.rate_limit import RateLimit, client_ip
from app.models import Workspace
from app.retrieval.types import RetrievalFilters
from app.schemas.ai import SearchOut, SearchResultOut
from app.services.retrieval import retrieve

log = logging.getLogger("api.search")
router = APIRouter(prefix="/api/search", tags=["search"])


def _search_limiter() -> RateLimit:
    return RateLimit(name="search", capacity=60, window_seconds=60)


@router.get("", response_model=SearchOut)
async def search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=2000),
    top_k: int = Query(default=10, ge=1, le=50),
    source_types: list[str] | None = Query(default=None),
    document_ids: list[UUID] | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    use_query_rewrite: bool = Query(default=True),
    workspace: Workspace = Depends(current_workspace),
    session: AsyncSession = Depends(db_session),
) -> SearchOut:
    await _search_limiter().hit(client_ip(request))

    filters = RetrievalFilters(
        source_types=source_types or [],
        document_ids=document_ids or [],
        date_from=date_from,
        date_to=date_to,
    )

    candidates, debug = await retrieve(
        session=session,
        workspace_id=workspace.id,
        question=q,
        filters=filters,
        use_query_rewrite=use_query_rewrite,
        top_k=top_k,
    )

    return SearchOut(
        query=q,
        rewrites=debug.get("rewrites", []),
        results=[
            SearchResultOut(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                title=c.title,
                snippet=c.text[:400],
                source_type=c.source_type,
                heading=c.heading,
                page=c.page_number,
                chunk_index=c.chunk_index,
                score=round(c.score, 4),
                rerank_score=round(c.rerank_score, 4) if c.rerank_score is not None else None,
                vector_rank=c.vector_rank,
                keyword_rank=c.keyword_rank,
            )
            for c in candidates
        ],
        debug=debug,
    )
