"""Pytest fixtures.

Tests run against a SQLite in-memory database so the unit/smoke suite does
not require Postgres to be up. Step-01 only exercises auth + health, both
of which are dialect-agnostic. Integration tests in later steps target the
real Postgres container via DATABASE_URL.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Force an in-memory sqlite URL before settings + engine import.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CHROMA_URL", "http://localhost:8001")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("APP_ENV", "test")

from app.db import session as db_session_module  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def engine():
    e = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    db_session_module.engine = e
    db_session_module.SessionLocal = async_sessionmaker(e, expire_on_commit=False)
    yield e
    await e.dispose()


@pytest_asyncio.fixture
async def client(engine) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _disable_chroma(monkeypatch):
    """Skip the Chroma collection bootstrap during tests."""

    async def _noop(*_a, **_k):
        return None

    from app.ai import chroma_client

    monkeypatch.setattr(chroma_client, "ensure_collection", _noop)


@pytest.fixture(autouse=True)
def _stub_rate_limit(monkeypatch):
    """No real Redis in unit tests — rate-limit hits become no-ops."""
    from app.core import rate_limit

    async def _noop(self, key: str) -> None:  # noqa: ARG001
        return None

    monkeypatch.setattr(rate_limit.RateLimit, "hit", _noop)


@pytest_asyncio.fixture
async def signed_in(client):
    """Client that has signed up and carries the CSRF header on every request.
    Use this for any test that exercises a state-changing protected endpoint —
    the middleware requires the double-submit header once the access cookie is set.
    """
    r = await client.post(
        "/auth/signup", json={"email": "test@example.com", "password": "supersecret1"}
    )
    assert r.status_code == 201
    csrf = r.cookies.get("csrf_token")
    if csrf:
        client.headers["x-csrf-token"] = csrf
    return client
