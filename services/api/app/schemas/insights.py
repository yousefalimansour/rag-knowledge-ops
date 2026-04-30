from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InsightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    type: str
    title: str
    summary: str
    severity: str
    confidence: float | None
    evidence: list[dict[str, Any]]
    state: str
    created_at: datetime
    updated_at: datetime


class InsightList(BaseModel):
    items: list[InsightOut]
    next_cursor: str | None


class InsightStatePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["active", "dismissed", "read"]


class InsightRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    scope: str
    trigger: str
    status: str
    error: str | None
    source_doc_ids: list[Any]
    insights_generated: int
    insights_skipped: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class InsightRunList(BaseModel):
    items: list[InsightRunOut]


class InsightRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: Literal["all", "documents", "type"]
    document_ids: list[UUID] = Field(default_factory=list)
    type: Literal["conflict", "repeated_decision", "stale_document"] | None = None


class InsightRunResult(BaseModel):
    run_id: UUID
    status: str
