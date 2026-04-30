"""In-app notifications inbox."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user, db_session
from app.models import Notification, User
from app.schemas.notifications import NotificationList, NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
async def list_notifications(
    unread: bool | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
) -> NotificationList:
    base = select(Notification).where(Notification.user_id == user.id)
    if unread is True:
        base = base.where(Notification.read_at.is_(None))
    elif unread is False:
        base = base.where(Notification.read_at.is_not(None))
    if cursor:
        try:
            cdt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid cursor") from e
        base = base.where(Notification.created_at < cdt)

    rows = (
        await session.execute(base.order_by(desc(Notification.created_at)).limit(limit + 1))
    ).scalars().all()
    next_cursor = None
    if len(rows) > limit:
        next_cursor = rows[limit - 1].created_at.isoformat()
        rows = rows[:limit]

    unread_count = (
        await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        )
    ).scalar_one()

    return NotificationList(
        items=[NotificationOut.model_validate(r) for r in rows],
        next_cursor=next_cursor,
        unread_count=int(unread_count or 0),
    )


@router.patch("/{notification_id}", response_model=NotificationOut)
async def mark_read(
    notification_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
) -> NotificationOut:
    notif = await session.get(Notification, notification_id)
    if notif is None or notif.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notif.read_at is None:
        notif.read_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(notif)
    return NotificationOut.model_validate(notif)


@router.post(
    "/mark-all-read",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=FastAPIResponse,
    response_model=None,
)
async def mark_all_read(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await session.commit()
