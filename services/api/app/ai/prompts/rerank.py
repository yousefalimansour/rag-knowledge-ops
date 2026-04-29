"""Listwise reranking prompt.

Asks Gemini to score each candidate's relevance to the question on [0, 1].
Output is a JSON array of objects: [{"id": "...", "score": 0.x}].
"""

from __future__ import annotations

from app.retrieval.types import RetrievalCandidate

RERANK_SYSTEM = """You are a relevance judge. Given a user's question and a numbered list of
candidate text passages, score each passage's relevance to the question on a
scale from 0.0 (irrelevant) to 1.0 (perfectly answers the question).

Output ONLY a JSON array of objects, one per candidate, in the same order:
[{"id": "<id>", "score": 0.0}]

No commentary, no markdown.
"""


def build_rerank_prompt(question: str, candidates: list[RetrievalCandidate]) -> str:
    lines = [f'Question: "{question.strip()}"', "", "Candidates:"]
    for c in candidates:
        snippet = c.text[:400].replace("\n", " ")
        heading = f" ({c.heading})" if c.heading else ""
        lines.append(f"- id: {c.chunk_id}")
        lines.append(f'  title: "{c.title}"{heading}')
        lines.append(f'  text: "{snippet}"')
    lines.append("")
    lines.append("Output:")
    return "\n".join(lines)
