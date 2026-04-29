"""AI Q&A endpoints — synchronous + SSE streaming.

The streaming endpoint runs retrieval + rerank synchronously (cheap), then
streams Gemini's tokens. Refusals emit the same SSE envelope so the client
renders uniformly.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import current_workspace, db_session
from app.core.rate_limit import RateLimit, client_ip
from app.models import Workspace
from app.retrieval.types import RetrievalFilters
from app.schemas.ai import ConfidenceBreakdownOut, QueryIn, QueryOut, SourceOut
from app.services import query_cache
from app.services.reasoning import answer_question, stream_answer

log = logging.getLogger("api.ai")
router = APIRouter(prefix="/api/ai", tags=["ai"])


def _query_limiter() -> RateLimit:
    return RateLimit(
        name="ai_query",
        capacity=get_settings().QUERY_RATE_LIMIT_PER_MIN,
        window_seconds=60,
    )


def _to_filters(payload: QueryIn) -> RetrievalFilters:
    return RetrievalFilters(
        source_types=list(payload.filters.source_types),
        document_ids=list(payload.filters.document_ids),
        date_from=payload.filters.date_from,
        date_to=payload.filters.date_to,
    )


def _filters_dict(payload: QueryIn) -> dict[str, Any]:
    return payload.filters.model_dump(mode="json")


@router.post("/query", response_model=QueryOut)
async def query(
    payload: QueryIn,
    request: Request,
    workspace: Workspace = Depends(current_workspace),
    session: AsyncSession = Depends(db_session),
) -> QueryOut:
    await _query_limiter().hit(client_ip(request))

    cache_key = query_cache.make_key(
        workspace_id=workspace.id, question=payload.question, filters=_filters_dict(payload)
    )
    cached = await query_cache.get(cache_key)
    if cached is not None:
        cached["cached"] = True
        return QueryOut.model_validate(cached)

    try:
        result = await answer_question(
            session=session,
            workspace_id=workspace.id,
            question=payload.question,
            filters=_to_filters(payload),
            use_query_rewrite=payload.use_query_rewrite,
            top_k=payload.top_k,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("ai.query.failed")
        raise HTTPException(status_code=502, detail=f"AI query failed: {e}") from e

    out = QueryOut(
        answer=result.answer,
        sources=[_source_to_out(s) for s in result.sources],
        confidence=result.confidence.composite,
        breakdown=ConfidenceBreakdownOut(
            top_score=result.confidence.top_score,
            score_gap=result.confidence.score_gap,
            diversity=result.confidence.diversity,
            evidence_count=result.confidence.evidence_count,
        ),
        reasoning=result.reasoning_summary,
        cached=False,
    )
    await query_cache.put(cache_key, out.model_dump(mode="json"))
    return out


@router.post("/query/stream")
async def query_stream(
    payload: QueryIn,
    request: Request,
    workspace: Workspace = Depends(current_workspace),
    session: AsyncSession = Depends(db_session),
):
    """Retrieval finishes (with FastAPI's request-scoped session) BEFORE we
    construct the StreamingResponse. The token-only generator does no DB
    work, so its lifecycle can't tangle with SQLAlchemy state.
    """
    from app.services.retrieval import retrieve

    await _query_limiter().hit(client_ip(request))

    candidates, debug = await retrieve(
        session=session,
        workspace_id=workspace.id,
        question=payload.question,
        filters=_to_filters(payload),
        use_query_rewrite=payload.use_query_rewrite,
        top_k=payload.top_k,
    )

    return StreamingResponse(
        _sse_event_loop(request, candidates=candidates, debug=debug, question=payload.question),
        media_type="text/event-stream",
        headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
    )


async def _sse_event_loop(request: Request, *, candidates, debug: dict, question: str):
    """Pure-streaming generator: takes pre-retrieved candidates, drives Gemini,
    emits SSE events. No database work happens here.
    """

    def emit(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    try:
        async for event, data in stream_answer(
            candidates=candidates, debug=debug, question=question
        ):
            if await request.is_disconnected():
                log.info("ai.stream.client_disconnected")
                return
            yield emit(event, data)
    except Exception as e:  # noqa: BLE001
        log.exception("ai.stream.failed")
        yield emit("error", {"message": f"{e}"})
        yield emit("done", {"ok": False})


def _source_to_out(s) -> SourceOut:
    return SourceOut(
        document_id=s.document_id,
        title=s.title,
        chunk_id=s.chunk_id,
        snippet=s.text[:280],
        score=round(s.rerank_score if s.rerank_score is not None else s.score, 4),
        page=s.page_number,
        heading=s.heading,
        source_type=s.source_type,
        chunk_index=s.chunk_index,
    )
