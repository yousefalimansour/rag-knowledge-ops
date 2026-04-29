"""Citation parser + post-validator.

The model is instructed to cite as `[<chunk_id>]` where chunk_id is a UUID.
We:
- Extract every UUID-shaped citation from the answer text.
- Drop ones that don't match a candidate the model was actually shown
  (post-validator — guards against hallucinated ids).
- Surface the cited candidates in answer order so the UI can list them
  as "sources".
"""

from __future__ import annotations

import re
from uuid import UUID

from app.retrieval.types import RetrievalCandidate

UUID_RE = re.compile(
    r"\[([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\]"
)


def extract_cited_ids(answer: str) -> list[UUID]:
    """Returns ids in the order they first appear in the answer."""
    seen: set[str] = set()
    out: list[UUID] = []
    for m in UUID_RE.finditer(answer):
        sid = m.group(1).lower()
        if sid in seen:
            continue
        seen.add(sid)
        try:
            out.append(UUID(sid))
        except ValueError:
            continue
    return out


def validate_and_filter(
    answer: str, candidates: list[RetrievalCandidate]
) -> tuple[str, list[RetrievalCandidate], dict]:
    """Returns (clean_answer, cited_sources_in_order, info).

    - Bad citations (chunk ids not in `candidates`) are stripped from the
      answer text. Their existence is reported via info["dropped"].
    - The returned `cited_sources` are ordered by first-cite, with rerank/
      fusion score available on each for UI sorting if desired.
    """
    by_id: dict[UUID, RetrievalCandidate] = {c.chunk_id: c for c in candidates}
    cited_ids = extract_cited_ids(answer)

    valid: list[UUID] = []
    dropped: list[str] = []
    for cid in cited_ids:
        if cid in by_id:
            valid.append(cid)
        else:
            dropped.append(str(cid))

    clean_answer = answer
    for bad in dropped:
        clean_answer = re.sub(rf"\s*\[{re.escape(bad)}\]", "", clean_answer)

    sources = [by_id[cid] for cid in valid]
    return clean_answer, sources, {"cited": [str(x) for x in valid], "dropped": dropped}
