"""End-to-end retrieval orchestrator: rewrite → vector + keyword → fuse → rerank.

Returns a flat list of `RetrievalCandidate` ready for the reasoning step
(or for `/api/search` to surface raw).
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

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
    candidate_pool: int = 20,
    top_k: int = 8,
) -> tuple[list[RetrievalCandidate], dict]:
    """Returns (top_k candidates after rerank, debug breakdown).

    The breakdown is small JSON-friendly dict: `{rewrites, vector_hits,
    keyword_hits, fused, reranked, rerank_fallback}` — useful for /api/search
    debugging and structured logging.
    """
    filters = filters or RetrievalFilters()

    queries = rewrite_query(question) if use_query_rewrite else [question.strip()]
    if not queries:
        return [], {"rewrites": [], "vector_hits": 0, "keyword_hits": 0, "fused": 0, "reranked": 0, "rerank_fallback": False}

    # Run searches sequentially on the shared session — async SQLAlchemy
    # forbids concurrent ops on a single session, and the DB calls are tiny
    # next to the LLM calls that dominate request latency.
    results: list[list] = []
    for q in queries:
        results.append(
            await vs.vector_search(
                session=session, workspace_id=workspace_id, query=q,
                top_k=candidate_pool, filters=filters,
            )
        )
        results.append(
            await kw.keyword_search(
                session=session, workspace_id=workspace_id, query=q,
                top_k=candidate_pool, filters=filters,
            )
        )

    vector_hits = sum(len(r) for r in results[::2])
    keyword_hits = sum(len(r) for r in results[1::2])

    fused = rrf_fuse(*results)
    if not fused:
        return [], {
            "rewrites": queries, "vector_hits": vector_hits, "keyword_hits": keyword_hits,
            "fused": 0, "reranked": 0, "rerank_fallback": False,
        }

    if use_rerank:
        reranked, used_llm = rerank(question, fused, top_k_in=candidate_pool, top_k_out=top_k)
    else:
        reranked, used_llm = fused[:top_k], False

    log.info(
        "retrieval.done",
        extra={
            "queries": len(queries),
            "vector_hits": vector_hits,
            "keyword_hits": keyword_hits,
            "fused": len(fused),
            "reranked": len(reranked),
            "rerank_fallback": not used_llm,
        },
    )

    return reranked, {
        "rewrites": queries,
        "vector_hits": vector_hits,
        "keyword_hits": keyword_hits,
        "fused": len(fused),
        "reranked": len(reranked),
        "rerank_fallback": not used_llm,
    }
