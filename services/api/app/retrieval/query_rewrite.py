"""Conversational-question → search-query rewriter.

Skip the LLM entirely when the question is short and already keyword-shaped
(no question marks, no filler words). Otherwise call Gemini with a tight
prompt that returns a JSON array of 1–3 short queries.
"""

from __future__ import annotations

import json
import logging
import re

from app.ai.llm import generate_text
from app.ai.prompts.rewrite import QUERY_REWRITE_SYSTEM, build_rewrite_prompt
from app.core.errors import LLMError

log = logging.getLogger("api.retrieval.rewrite")

_FILLER_RE = re.compile(
    r"\b(what|when|where|who|why|how|did|do|does|is|are|was|were|can|could|should|would)\b",
    re.IGNORECASE,
)
_QUESTION_MARK = "?"
_MIN_LEN_FOR_REWRITE = 12
_MIN_WORDS_FOR_REWRITE = 4


def needs_rewrite(question: str) -> bool:
    q = question.strip()
    if len(q) < _MIN_LEN_FOR_REWRITE:
        return False
    if _QUESTION_MARK in q:
        return True
    words = q.split()
    if len(words) < _MIN_WORDS_FOR_REWRITE:
        return False
    return bool(_FILLER_RE.search(q))


def rewrite_query(question: str, *, max_queries: int = 3) -> list[str]:
    """Returns a list of 1–3 search queries. The original is always first
    (so retrieval recall never regresses if the rewrite is bad).
    """
    base = [question.strip()] if question.strip() else []
    if not needs_rewrite(question):
        return base[:max_queries]

    try:
        raw = generate_text(
            build_rewrite_prompt(question),
            system=QUERY_REWRITE_SYSTEM,
            temperature=0.1,
            max_output_tokens=256,
        )
    except LLMError as e:
        log.warning("rewrite.llm_failed", extra={"error": str(e)[:200]})
        return base[:max_queries]

    extras = _parse_array(raw)
    if not extras:
        return base[:max_queries]

    seen: set[str] = set()
    out: list[str] = []
    for q in (*base, *extras):
        norm = q.strip()
        if norm and norm.lower() not in seen:
            seen.add(norm.lower())
            out.append(norm)
        if len(out) >= max_queries:
            break
    return out


def _parse_array(raw: str) -> list[str]:
    """Extract a JSON array of strings from the model's output, even if
    wrapped in ```json fences or surrounded by stray prose.
    """
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?", "", s).strip()
        if s.endswith("```"):
            s = s[:-3].strip()
    # Fall back to first '[ ... ]' substring.
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
    return [str(x).strip() for x in data if isinstance(x, (str,)) and x.strip()]
