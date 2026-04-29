"""Document listing + detail.

Replaces the step-01 placeholder router. Workspace-scoped at the dependency
layer, so cross-tenant reads are impossible by construction.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_workspace, db_session
from app.models import Chunk, Document, Workspace
from app.schemas.documents import (
    ChunkPreview,
    DocumentDetail,
    DocumentList,
    DocumentOut,
)

router = APIRouter(prefix="/api/docs", tags=["documents"])


@router.get("", response_model=DocumentList)
async def list_documents(
    status_: str | None = Query(default=None, alias="status"),
    source_type: str | None = Query(default=None),
    q: str | None = Query(default=None, description="title prefix search"),
    cursor: str | None = Query(default=None, description="ISO timestamp of last item created_at"),
    limit: int = Query(default=20, ge=1, le=100),
    workspace: Workspace = Depends(current_workspace),
    session: AsyncSession = Depends(db_session),
) -> DocumentList:
    stmt = select(Document).where(Document.workspace_id == workspace.id)
    if status_:
        stmt = stmt.where(Document.status == status_)
    if source_type:
        stmt = stmt.where(Document.source_type == source_type)
    if q:
        stmt = stmt.where(Document.title.ilike(f"%{q}%"))
    if cursor:
        from datetime import datetime

        try:
            cursor_dt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid cursor") from e
        stmt = stmt.where(Document.created_at < cursor_dt)

    stmt = stmt.order_by(Document.created_at.desc()).limit(limit + 1)
    rows = (await session.execute(stmt)).scalars().all()
    next_cursor = None
    if len(rows) > limit:
        next_cursor = rows[limit - 1].created_at.isoformat()
        rows = rows[:limit]

    return DocumentList(
        items=[DocumentOut.model_validate(r) for r in rows], next_cursor=next_cursor
    )


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: UUID,
    workspace: Workspace = Depends(current_workspace),
    session: AsyncSession = Depends(db_session),
) -> DocumentDetail:
    doc = await session.get(Document, document_id)
    if doc is None or doc.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    chunks = (
        await session.execute(
            select(Chunk)
            .where(Chunk.document_id == doc.id)
            .order_by(Chunk.chunk_index)
            .limit(5)
        )
    ).scalars().all()

    return DocumentDetail(
        document=DocumentOut.model_validate(doc),
        chunks_preview=[ChunkPreview.model_validate(c) for c in chunks],
    )
