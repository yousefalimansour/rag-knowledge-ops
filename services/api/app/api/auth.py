from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import current_user, current_workspace, db_session
from app.core.middleware import ACCESS_COOKIE, CSRF_COOKIE, issue_csrf_token
from app.core.rate_limit import RateLimit, client_ip
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User, UserWorkspace, Workspace
from app.schemas.auth import AuthEnvelope, LoginIn, SignupIn, UserOut, WorkspaceOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _login_limiter() -> RateLimit:
    return RateLimit(
        name="login",
        capacity=get_settings().LOGIN_RATE_LIMIT_PER_15MIN,
        window_seconds=15 * 60,
    )


def _set_auth_cookies(response: Response, *, user_id: str) -> None:
    settings = get_settings()
    access = create_access_token(subject=user_id)
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access,
        max_age=settings.ACCESS_TOKEN_TTL_MIN * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE,
        value=issue_csrf_token(),
        max_age=settings.ACCESS_TOKEN_TTL_MIN * 60,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    for k in (ACCESS_COOKIE, CSRF_COOKIE):
        response.delete_cookie(key=k, domain=settings.COOKIE_DOMAIN, path="/")


@router.post("/signup", response_model=AuthEnvelope, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: SignupIn,
    response: Response,
    session: AsyncSession = Depends(db_session),
) -> AuthEnvelope:
    existing = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    await session.flush()

    workspace = Workspace(
        name=payload.workspace_name or f"{payload.email.split('@')[0]}'s workspace",
        owner_user_id=user.id,
    )
    session.add(workspace)
    await session.flush()

    session.add(UserWorkspace(user_id=user.id, workspace_id=workspace.id, role="owner"))
    await session.commit()
    await session.refresh(user)
    await session.refresh(workspace)

    _set_auth_cookies(response, user_id=str(user.id))
    return AuthEnvelope(
        user=UserOut.model_validate(user), workspace=WorkspaceOut.model_validate(workspace)
    )


@router.post("/login", response_model=AuthEnvelope)
async def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(db_session),
) -> AuthEnvelope:
    await _login_limiter().hit(client_ip(request))

    user = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    ws = (
        await session.execute(
            select(Workspace)
            .join(UserWorkspace, UserWorkspace.workspace_id == Workspace.id)
            .where(UserWorkspace.user_id == user.id)
            .order_by(Workspace.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if ws is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="No workspace for user"
        )

    _set_auth_cookies(response, user_id=str(user.id))
    return AuthEnvelope(
        user=UserOut.model_validate(user), workspace=WorkspaceOut.model_validate(ws)
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=FastAPIResponse,
    response_model=None,
)
async def logout(response: Response) -> None:
    _clear_auth_cookies(response)


@router.get("/me", response_model=AuthEnvelope)
async def me(
    user: User = Depends(current_user),
    workspace: Workspace = Depends(current_workspace),
) -> AuthEnvelope:
    return AuthEnvelope(
        user=UserOut.model_validate(user),
        workspace=WorkspaceOut.model_validate(workspace),
    )
