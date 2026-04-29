from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class RetrievalCandidate:
    """One chunk in the retrieval pipeline. Carries everything subsequent
    stages need without re-querying the DB.
    """

    chunk_id: UUID
    document_id: UUID
    title: str
    text: str
    source_type: str
    heading: str | None
    page_number: int | None
    chunk_index: int
    score: float = 0.0  # post-fusion (RRF) score — used for ranking
    source_score: float = 0.0  # original similarity / tf-idf, normalized to [0, 1]
    vector_rank: int | None = None
    keyword_rank: int | None = None
    rerank_score: float | None = None
    source_timestamp: datetime | None = None


@dataclass(slots=True)
class RetrievalFilters:
    source_types: list[str] = field(default_factory=list)
    document_ids: list[UUID] = field(default_factory=list)
    date_from: datetime | None = None
    date_to: datetime | None = None
