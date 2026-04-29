"""Listwise reranker.

Takes the fused top-N candidates and asks Gemini to score each on [0, 1].
On any LLM failure, returns the input order unchanged so retrieval quality
degrades gracefully rather than collapsing.
"""

from __future__ import annotations

import json
import logging
import re

from app.ai.llm import generate_text
from app.ai.prompts.rerank import RERANK_SYSTEM, build_rerank_prompt
from app.core.errors import LLMError
from app.retrieval.types import RetrievalCandidate

log = logging.getLogger("api.retrieval.rerank")

DEFAULT_RERANK_INPUT = 20
DEFAULT_RERANK_OUTPUT = 8


def rerank(
    question: str,
    candidates: list[RetrievalCandidate],
    *,
    top_k_in: int = DEFAULT_RERANK_INPUT,
    top_k_out: int = DEFAULT_RERANK_OUTPUT,
) -> tuple[list[RetrievalCandidate], bool]:
    """Returns (reranked_candidates, used_llm).

    `used_llm=False` indicates we returned the input order unchanged
    (because either there was nothing to rerank or the LLM call failed).
    """
    if not candidates:
        return [], False

    pool = candidates[:top_k_in]

    try:
        raw = generate_text(
            build_rerank_prompt(question, pool),
            system=RERANK_SYSTEM,
            temperature=0.0,
            max_output_tokens=1024,
        )
    except LLMError as e:
        log.warning("rerank.llm_failed", extra={"error": str(e)[:200]})
        return pool[:top_k_out], False

    scores = _parse_scores(raw)
    if not scores:
        log.warning("rerank.unparseable_output")
        return pool[:top_k_out], False

    by_id = {str(c.chunk_id): c for c in pool}
    annotated: list[RetrievalCandidate] = []
    for entry in scores:
        cand = by_id.get(entry["id"])
        if cand is None:
            continue
        cand.rerank_score = float(entry["score"])
        annotated.append(cand)

    # Any candidates the model omitted keep their fused score with rerank_score=None,
    # so downstream code still has them as a fallback.
    seen = {str(c.chunk_id) for c in annotated}
    for c in pool:
        if str(c.chunk_id) not in seen:
            annotated.append(c)

    annotated.sort(key=lambda c: c.rerank_score if c.rerank_score is not None else -1, reverse=True)
    return annotated[:top_k_out], True


def _parse_scores(raw: str) -> list[dict]:
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
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        cid = item.get("id")
        score = item.get("score")
        if not isinstance(cid, str):
            continue
        try:
            score = float(score)
        except (TypeError, ValueError):
            continue
        out.append({"id": cid, "score": max(0.0, min(1.0, score))})
    return out
