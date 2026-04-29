"""End-to-end reasoning: retrieval → answer prompt → Gemini → validate citations
→ score confidence. The streaming variant produces an iterator of SSE-ready
events instead of a single JSON envelope.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import generate_stream, generate_text
from app.ai.prompts.answer import ANSWER_SYSTEM, REFUSAL_TEXT, build_answer_prompt
from app.retrieval.confidence import ConfidenceBreakdown, is_refusal, score
from app.retrieval.types import RetrievalCandidate, RetrievalFilters
from app.services.citations import validate_and_filter
from app.services.retrieval import retrieve

log = logging.getLogger("api.reasoning")


@dataclass(slots=True)
class AnswerResult:
    answer: str
    sources: list[RetrievalCandidate]
    confidence: ConfidenceBreakdown
    reasoning_summary: str
    debug: dict


async def answer_question(
    *,
    session: AsyncSession,
    workspace_id: UUID,
    question: str,
    filters: RetrievalFilters | None = None,
    use_query_rewrite: bool = True,
    top_k: int = 8,
) -> AnswerResult:
    candidates, debug = await retrieve(
        session=session,
        workspace_id=workspace_id,
        question=question,
        filters=filters,
        use_query_rewrite=use_query_rewrite,
        top_k=top_k,
    )
    confidence = score(candidates)

    if not candidates or is_refusal(confidence):
        return AnswerResult(
            answer=REFUSAL_TEXT,
            sources=[],
            confidence=confidence,
            reasoning_summary=_refusal_reasoning(debug, confidence),
            debug=debug,
        )

    prompt = build_answer_prompt(question, candidates)
    raw_answer = generate_text(prompt, system=ANSWER_SYSTEM, temperature=0.2, max_output_tokens=1024)

    clean, sources, citation_info = validate_and_filter(raw_answer, candidates)
    debug.update({"citations": citation_info})

    return AnswerResult(
        answer=clean,
        sources=sources,
        confidence=confidence,
        reasoning_summary=_reasoning_summary(debug, confidence),
        debug=debug,
    )


async def stream_answer(
    *,
    candidates: list[RetrievalCandidate],
    debug: dict,
    question: str,
) -> AsyncIterator[tuple[str, dict]]:
    """Yields SSE-ready (event_name, payload) tuples in this order:
    start → token+ → sources → confidence → done.

    Retrieval must be done by the caller before invoking this generator —
    that way the DB session can be closed before the token loop starts and
    the sync Gemini stream doesn't tangle with async SQLAlchemy state.
    """
    yield "start", {"question": question}

    confidence = score(candidates)

    if not candidates or is_refusal(confidence):
        yield "token", {"delta": REFUSAL_TEXT}
        yield "sources", {"sources": []}
        yield "confidence", {
            "confidence": confidence.composite,
            "reasoning": _refusal_reasoning(debug, confidence),
            "breakdown": _breakdown_dict(confidence),
        }
        yield "done", {"ok": True}
        return

    prompt = build_answer_prompt(question, candidates)

    chunks: list[str] = []
    for delta in generate_stream(
        prompt, system=ANSWER_SYSTEM, temperature=0.2, max_output_tokens=1024
    ):
        chunks.append(delta)
        yield "token", {"delta": delta}

    raw_answer = "".join(chunks)
    _, sources, citation_info = validate_and_filter(raw_answer, candidates)
    debug.update({"citations": citation_info})

    yield "sources", {"sources": [_source_dict(s) for s in sources]}
    yield "confidence", {
        "confidence": confidence.composite,
        "reasoning": _reasoning_summary(debug, confidence),
        "breakdown": _breakdown_dict(confidence),
    }
    yield "done", {"ok": True}


def _reasoning_summary(debug: dict, conf: ConfidenceBreakdown) -> str:
    bits: list[str] = []
    bits.append(
        f"Searched with {len(debug.get('rewrites', []))} query/queries, "
        f"merged {debug.get('fused', 0)} candidates, kept {debug.get('reranked', 0)} after rerank."
    )
    if debug.get("rerank_fallback"):
        bits.append("(rerank fallback — reranker errored, used fusion order)")
    bits.append(f"Confidence {conf.composite:.2f} (top {conf.top_score:.2f}, gap {conf.score_gap:.2f}).")
    return " ".join(bits)


def _refusal_reasoning(debug: dict, conf: ConfidenceBreakdown) -> str:
    return (
        "No chunks above the evidence threshold. "
        f"Top score {conf.top_score:.2f}, evidence count {conf.evidence_count:.2f}."
    )


def _breakdown_dict(b: ConfidenceBreakdown) -> dict:
    return {
        "top_score": b.top_score,
        "score_gap": b.score_gap,
        "diversity": b.diversity,
        "evidence_count": b.evidence_count,
    }


def _source_dict(c: RetrievalCandidate) -> dict:
    return {
        "document_id": str(c.document_id),
        "title": c.title,
        "chunk_id": str(c.chunk_id),
        "snippet": c.text[:280],
        "score": round(c.rerank_score if c.rerank_score is not None else c.score, 4),
        "page": c.page_number,
        "heading": c.heading,
        "source_type": c.source_type,
        "chunk_index": c.chunk_index,
    }
