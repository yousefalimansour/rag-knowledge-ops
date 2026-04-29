from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    workspace_id: UUID
    status: str
    stage: str | None
    error: str | None
    attempts: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class JobEnqueueResult(BaseModel):
    id: UUID
    document_id: UUID
    status: str
    deduplicated: bool = False


class FilesIngestResult(BaseModel):
    jobs: list[JobEnqueueResult]


class SourceIngestResult(BaseModel):
    job: JobEnqueueResult
