from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QueryFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_types: list[str] = Field(default_factory=list)
    document_ids: list[UUID] = Field(default_factory=list)
    date_from: datetime | None = None
    date_to: datetime | None = None


class QueryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    filters: QueryFilters = Field(default_factory=QueryFilters)
    use_query_rewrite: bool = True
    top_k: int = Field(default=8, ge=1, le=20)


class SourceOut(BaseModel):
    document_id: UUID
    title: str
    chunk_id: UUID
    snippet: str
    score: float
    page: int | None
    heading: str | None
    source_type: str
    chunk_index: int


class ConfidenceBreakdownOut(BaseModel):
    top_score: float
    score_gap: float
    diversity: float
    evidence_count: float


class QueryOut(BaseModel):
    answer: str
    sources: list[SourceOut]
    confidence: float
    breakdown: ConfidenceBreakdownOut
    reasoning: str
    cached: bool = False


class SearchResultOut(BaseModel):
    chunk_id: UUID
    document_id: UUID
    title: str
    snippet: str
    source_type: str
    heading: str | None
    page: int | None
    chunk_index: int
    score: float
    rerank_score: float | None
    vector_rank: int | None
    keyword_rank: int | None


class SearchOut(BaseModel):
    query: str
    rewrites: list[str]
    results: list[SearchResultOut]
    debug: dict
