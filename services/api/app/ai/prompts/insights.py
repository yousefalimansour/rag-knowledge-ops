"""Prompts for the proactive intelligence generators.

The model is asked to produce a JSON array; missing-evidence cases yield `[]`.
We keep the prompt strict and small so a single Gemini-flash call covers a
batch of chunks.
"""

from __future__ import annotations

from app.retrieval.types import RetrievalCandidate

CONFLICT_REPEATED_SYSTEM = """You analyze a small batch of knowledge-base chunks and identify
either CONFLICTS or REPEATED-DECISION patterns across them. The output is a
strict JSON array. Each element is one finding:

[
  {
    "type": "conflict" | "repeated_decision",
    "title": "short one-line title (≤ 80 chars)",
    "summary": "2-3 sentence explanation; quote the conflicting/agreeing fragments briefly",
    "severity": "low" | "medium" | "high",
    "evidence_chunk_ids": ["<chunk_id>", "<chunk_id>", ...]
  }
]

Rules:
- A "conflict" requires at least TWO chunks from DIFFERENT documents that make contradictory factual claims about the same subject.
- A "repeated_decision" requires the same decision/policy stated in TWO OR MORE different documents (not just rephrased adjacent chunks of one doc).
- Do NOT invent: every cited chunk_id must appear in the input.
- If nothing qualifies, return [].
- Output the JSON array ONLY — no prose, no markdown fences.
"""


def build_conflict_repeated_prompt(candidates: list[RetrievalCandidate]) -> str:
    lines = ["CHUNKS:"]
    for c in candidates:
        snippet = c.text[:600].replace("\n", " ")
        head = f' heading="{c.heading}"' if c.heading else ""
        lines.append(f'<chunk id="{c.chunk_id}" doc="{c.document_id}" title="{c.title}"{head}>')
        lines.append(snippet)
        lines.append("</chunk>")
    lines.append("")
    lines.append("Output the JSON array now.")
    return "\n".join(lines)
