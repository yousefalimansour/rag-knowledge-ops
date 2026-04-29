"""Heuristic confidence scoring.

Output is in [0, 1]. A composite ≥ 0.25 is "answerable"; below that triggers
the refusal contract. The numbers here aren't ML-calibrated — they're a
defensible, reviewable signal mix for the demo.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.retrieval.types import RetrievalCandidate

REFUSAL_THRESHOLD = 0.25
TOP_SCORE_FLOOR = 0.30  # similarities below this contribute nothing


@dataclass(frozen=True, slots=True)
class ConfidenceBreakdown:
    top_score: float
    score_gap: float
    diversity: float
    evidence_count: float
    composite: float


def score(
    candidates: list[RetrievalCandidate],
    *,
    score_threshold: float = TOP_SCORE_FLOOR,
) -> ConfidenceBreakdown:
    if not candidates:
        return ConfidenceBreakdown(0.0, 0.0, 0.0, 0.0, 0.0)

    # Prefer rerank score if present. Otherwise use the original similarity
    # (vector cosine in [0,1]). The fusion (RRF) score is on a tiny scale
    # (≈ 1/61) and isn't appropriate for confidence thresholds.
    def s(c: RetrievalCandidate) -> float:
        if c.rerank_score is not None:
            return c.rerank_score
        return c.source_score if c.source_score > 0 else c.score

    top1 = s(candidates[0])
    top1_norm = max(0.0, min(1.0, (top1 - score_threshold) / (1.0 - score_threshold))) if top1 > score_threshold else 0.0

    top2 = s(candidates[1]) if len(candidates) > 1 else 0.0
    gap = max(0.0, min(1.0, (top1 - top2) * 2))  # small gaps → low; larger gaps → up to 1

    above = [c for c in candidates if s(c) >= score_threshold]
    distinct_docs = len({c.document_id for c in above})
    # Diversity rewards 2-3 supporting docs; capped at 1 for ≥3 docs.
    diversity = min(1.0, distinct_docs / 3.0)

    # Evidence count: 0 for none, 1 for ≥3 supporting chunks, linear between.
    evidence_count = min(1.0, len(above) / 3.0)

    composite = (
        0.45 * top1_norm
        + 0.20 * gap
        + 0.20 * diversity
        + 0.15 * evidence_count
    )
    composite = round(max(0.0, min(1.0, composite)), 3)

    return ConfidenceBreakdown(
        top_score=round(top1, 3),
        score_gap=round(gap, 3),
        diversity=round(diversity, 3),
        evidence_count=round(evidence_count, 3),
        composite=composite,
    )


def is_refusal(breakdown: ConfidenceBreakdown) -> bool:
    return breakdown.composite < REFUSAL_THRESHOLD
