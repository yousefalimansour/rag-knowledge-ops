"""Content-hash + version reconciliation.

Hashing strategy (deviates slightly from the step doc — documented here):

- For files, we hash the raw bytes. Two byte-identical uploads dedup; two
  PDFs with identical text but different binary metadata do not. Acceptable
  for the demo and orders of magnitude cheaper than extracting first.
- For Slack/Notion JSON, we hash a canonical JSON serialization of the
  payload (sorted keys, no whitespace) so the same logical export always
  produces the same hash.

If the same (workspace_id, content_hash) already exists, that's a duplicate —
we return the existing document and do *not* enqueue a job.

If the same (workspace_id, title) exists with a *different* content_hash,
that's a new version: bump `version = max(existing.version) + 1` and create
a fresh row.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document


def hash_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def hash_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def find_duplicate(
    *, session: AsyncSession, workspace_id: UUID, content_hash: str
) -> Document | None:
    return (
        await session.execute(
            select(Document).where(
                Document.workspace_id == workspace_id,
                Document.content_hash == content_hash,
            )
        )
    ).scalar_one_or_none()


async def next_version_for_title(
    *, session: AsyncSession, workspace_id: UUID, title: str
) -> int:
    current = (
        await session.execute(
            select(func.coalesce(func.max(Document.version), 0)).where(
                Document.workspace_id == workspace_id,
                Document.title == title,
            )
        )
    ).scalar_one()
    return int(current or 0) + 1
