"""End-to-end retrieval orchestrator: rewrite → vector + keyword → fuse → rerank.

Returns a flat list of `RetrievalCandidate` ready for the reasoning step
(or for `/api/search` to surface raw).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session as db_session
from app.retrieval import keyword as kw
from app.retrieval import vector as vs
from app.retrieval.fusion import rrf_fuse
from app.retrieval.query_rewrite import rewrite_query
from app.retrieval.rerank import rerank
from app.retrieval.types import RetrievalCandidate, RetrievalFilters

log = logging.getLogger("api.services.retrieval")


async def retrieve(
    *,
    session: AsyncSession,
    workspace_id: UUID,
    question: str,
    filters: RetrievalFilters | None = None,
    use_query_rewrite: bool = True,
    use_rerank: bool = True,
    candidate_pool: int = 12,
    top_k: int = 8,
) -> tuple[list[RetrievalCandidate], dict]:
    """Returns (top_k candidates after rerank, debug breakdown).

    Vector + keyword searches for each query run in TRUE parallel by handing
    each `gather`d coroutine its own SQLAlchemy session — async SQLAlchemy
    forbids concurrent ops on a single session, but multiple sessions over
    the same engine pool are fine. Keeping the caller's session around for
    other work (commits, etc.) is preserved by not touching it here.

    Rerank is skipped when the fused list is already <= `top_k` because
    there is nothing for the LLM judge to reorder.
    """
    filters = filters or RetrievalFilters()
    started = time.monotonic()

    queries = rewrite_query(question) if use_query_rewrite else [question.strip()]
    if not queries:
        return [], {"rewrites": [], "vector_hits": 0, "keyword_hits": 0, "fused": 0, "reranked": 0, "rerank_fallback": False}

    # Resolve at call time so the test conftest's monkey-patched
    # SessionLocal (sqlite in-memory) is honored.
    SessionLocal = db_session.SessionLocal  # noqa: N806

    async def _vec(q: str) -> list[RetrievalCandidate]:
        async with SessionLocal() as s:
            return await vs.vector_search(
                session=s, workspace_id=workspace_id, query=q,
                top_k=candidate_pool, filters=filters,
            )

    async def _kw(q: str) -> list[RetrievalCandidate]:
        async with SessionLocal() as s:
            return await kw.keyword_search(
                session=s, workspace_id=workspace_id, query=q,
                top_k=candidate_pool, filters=filters,
            )

    coros: list[Awaitable[list[RetrievalCandidate]]] = []
    fns: list[Callable[[str], Awaitable[list[RetrievalCandidate]]]] = [_vec, _kw]
    for q in queries:
        for fn in fns:
            coros.append(fn(q))
    results = await asyncio.gather(*coros)

    vector_hits = sum(len(r) for r in results[::2])
    keyword_hits = sum(len(r) for r in results[1::2])

    fused = rrf_fuse(*results)
    if not fused:
        return [], {
            "rewrites": queries, "vector_hits": vector_hits, "keyword_hits": keyword_hits,
            "fused": 0, "reranked": 0, "rerank_fallback": False,
        }

    skip_rerank = (not use_rerank) or len(fused) <= top_k
    if skip_rerank:
        reranked, used_llm = fused[:top_k], False
    else:
        reranked, used_llm = rerank(question, fused, top_k_in=candidate_pool, top_k_out=top_k)

    log.info(
        "retrieval.done",
        extra={
            "queries": len(queries),
            "vector_hits": vector_hits,
            "keyword_hits": keyword_hits,
            "fused": len(fused),
            "reranked": len(reranked),
            "rerank_fallback": not used_llm,
            "rerank_skipped": skip_rerank and use_rerank,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        },
    )

    # Reference the caller's session so static analyzers don't flag it as
    # unused. We accept it for API compatibility but rely on per-call
    # sessions above for the actual reads.
    _ = session

    return reranked, {
        "rewrites": queries,
        "vector_hits": vector_hits,
        "keyword_hits": keyword_hits,
        "fused": len(fused),
        "reranked": len(reranked),
        "rerank_fallback": not used_llm,
    }
