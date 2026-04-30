"""LLM-driven generator for conflict + repeated_decision insights.

Takes a candidate set (a slice of the corpus) and asks Gemini to find any
findings of those types. The model returns a strict JSON array; malformed
output is logged and skipped — the run is still successful with 0 insights.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import generate_text
from app.ai.prompts.insights import (
    CONFLICT_REPEATED_SYSTEM,
    build_conflict_repeated_prompt,
)
from app.core.errors import LLMError
from app.insights.dedup import dedup_hash
from app.insights.repo import save_insight
from app.models import Chunk, Document, InsightRun
from app.notifications.dispatcher import notify_insight_created
from app.retrieval.types import RetrievalCandidate

log = logging.getLogger("api.insights.generator")

ALLOWED_TYPES = {"conflict", "repeated_decision"}
ALLOWED_SEVERITY = {"low", "medium", "high"}


async def generate_from_candidates(
    *,
    session: AsyncSession,
    run: InsightRun,
    workspace_id: UUID,
    candidates: list[RetrievalCandidate],
) -> int:
    """Returns the count of NEW insights persisted (not counting dedup skips)."""
    if len(candidates) < 2:
        return 0

    try:
        raw = generate_text(
            build_conflict_repeated_prompt(candidates),
            system=CONFLICT_REPEATED_SYSTEM,
            temperature=0.1,
            max_output_tokens=1500,
        )
    except LLMError as e:
        log.warning("insights.llm_failed", extra={"error": str(e)[:200]})
        return 0

    findings = _parse_findings(raw)
    if not findings:
        return 0

    by_id = {str(c.chunk_id): c for c in candidates}
    persisted = 0
    for f in findings:
        type_ = str(f.get("type", "")).strip()
        if type_ not in ALLOWED_TYPES:
            continue
        title = str(f.get("title", "")).strip()
        summary = str(f.get("summary", "")).strip()
        severity = str(f.get("severity", "medium")).strip().lower()
        if severity not in ALLOWED_SEVERITY:
            severity = "medium"
        evidence_ids = [str(x) for x in f.get("evidence_chunk_ids", []) if str(x) in by_id]
        # Conflict requires ≥2 chunks from ≥2 distinct documents.
        evidence_chunks = [by_id[i] for i in evidence_ids]
        distinct_docs = {c.document_id for c in evidence_chunks}
        if type_ == "conflict" and (len(evidence_chunks) < 2 or len(distinct_docs) < 2):
            continue
        if type_ == "repeated_decision" and len(distinct_docs) < 2:
            continue
        if not title or not summary or not evidence_chunks:
            continue

        insight = await save_insight(
            session=session,
            run=run,
            workspace_id=workspace_id,
            type_=type_,
            title=title,
            summary=summary,
            severity=severity,
            confidence=None,
            evidence=[
                {
                    "chunk_id": str(c.chunk_id),
                    "document_id": str(c.document_id),
                    "title": c.title,
                    "snippet": c.text[:280],
                    "heading": c.heading,
                    "page": c.page_number,
                }
                for c in evidence_chunks
            ],
            dedup_hash=dedup_hash(
                type_=type_, source_chunk_ids=evidence_ids, title=title
            ),
        )
        if insight is not None:
            await notify_insight_created(session=session, insight=insight)
            await session.commit()
            persisted += 1

    return persisted


def _parse_findings(raw: str) -> list[dict[str, Any]]:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?", "", s).strip()
        if s.endswith("```"):
            s = s[:-3].strip()
    if not s.startswith("["):
        m = re.search(r"\[.*\]", s, re.DOTALL)
        if m:
            s = m.group(0)
    try:
        data = json.loads(s)
    except json.JSONDecodeError as e:
        log.warning("insights.parse_failed", extra={"error": str(e)[:120]})
        return []
    if not isinstance(data, list):
        return []
    return [d for d in data if isinstance(d, dict)]


# Helper for converting Chunk/Document rows from DB to RetrievalCandidates.
def chunks_to_candidates(rows: list[tuple[Chunk, Document]]) -> list[RetrievalCandidate]:
    return [
        RetrievalCandidate(
            chunk_id=chunk.id,
            document_id=doc.id,
            title=doc.title,
            text=chunk.text,
            source_type=doc.source_type,
            heading=chunk.heading,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            source_timestamp=chunk.source_timestamp,
        )
        for chunk, doc in rows
    ]
