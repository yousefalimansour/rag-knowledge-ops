from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import user_id_ctx
from app.core.middleware import ACCESS_COOKIE
from app.core.security import decode_token
from app.db.session import get_session
from app.models import User, UserWorkspace, Workspace


async def db_session() -> AsyncIterator[AsyncSession]:
    async for s in get_session():
        yield s


async def current_user(
    request: Request,
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE),
    session: AsyncSession = Depends(db_session),
) -> User:
    token = access_token
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        ) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from e

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        user_id = UUID(sub)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from e

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    user_id_ctx.set(str(user.id))
    return user


async def current_workspace(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
) -> Workspace:
    stmt = (
        select(Workspace)
        .join(UserWorkspace, UserWorkspace.workspace_id == Workspace.id)
        .where(UserWorkspace.user_id == user.id)
        .order_by(Workspace.created_at)
        .limit(1)
    )
    ws = (await session.execute(stmt)).scalar_one_or_none()
    if ws is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="No workspace for user"
        )
    return ws
