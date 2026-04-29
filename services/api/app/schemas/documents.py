from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    title: str
    source_type: str
    original_filename: str | None
    content_hash: str
    version: int
    status: str
    chunk_count: int
    error: str | None
    source_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None


class ChunkPreview(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    chunk_index: int
    text: str
    heading: str | None
    page_number: int | None


class DocumentDetail(BaseModel):
    document: DocumentOut
    chunks_preview: list[ChunkPreview]


class DocumentList(BaseModel):
    items: list[DocumentOut]
    next_cursor: str | None
