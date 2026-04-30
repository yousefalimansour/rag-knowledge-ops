from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    workspace_id: UUID
    type: str
    title: str
    body: str | None
    severity: str | None
    link_kind: str | None
    link_id: UUID | None
    read_at: datetime | None
    created_at: datetime


class NotificationList(BaseModel):
    items: list[NotificationOut]
    next_cursor: str | None
    unread_count: int
