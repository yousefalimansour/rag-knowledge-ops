"""Reciprocal Rank Fusion.

RRF combines multiple ranked lists by summing 1/(k + rank). It's robust to
score-scale mismatches between vector similarity and keyword tf-idf scores
and well-behaved when one side returns nothing.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from app.retrieval.types import RetrievalCandidate

DEFAULT_K = 60


def rrf_fuse(
    *ranked_lists: Iterable[RetrievalCandidate],
    k: int = DEFAULT_K,
) -> list[RetrievalCandidate]:
    """Returns one merged list, sorted by RRF score descending.

    Each input list is treated as already-ranked (position 0 = best). The
    same chunk appearing in multiple lists gets summed contributions.

    Vector/keyword rank metadata is preserved on the returned candidate,
    populated from whichever list contributed it.
    """
    fused: dict[UUID, RetrievalCandidate] = {}
    for source_list in ranked_lists:
        for rank, cand in enumerate(source_list):
            existing = fused.get(cand.chunk_id)
            if existing is None:
                # Copy so we don't mutate the input candidate.
                merged = RetrievalCandidate(
                    chunk_id=cand.chunk_id,
                    document_id=cand.document_id,
                    title=cand.title,
                    text=cand.text,
                    source_type=cand.source_type,
                    heading=cand.heading,
                    page_number=cand.page_number,
                    chunk_index=cand.chunk_index,
                    score=0.0,
                    source_score=cand.source_score,
                    vector_rank=cand.vector_rank,
                    keyword_rank=cand.keyword_rank,
                    source_timestamp=cand.source_timestamp,
                )
                fused[cand.chunk_id] = merged
                existing = merged
            else:
                # Carry over rank metadata from whichever list provided it.
                if existing.vector_rank is None and cand.vector_rank is not None:
                    existing.vector_rank = cand.vector_rank
                if existing.keyword_rank is None and cand.keyword_rank is not None:
                    existing.keyword_rank = cand.keyword_rank
                if cand.source_score > existing.source_score:
                    existing.source_score = cand.source_score

            existing.score += 1.0 / (k + rank + 1)

    return sorted(fused.values(), key=lambda c: c.score, reverse=True)
