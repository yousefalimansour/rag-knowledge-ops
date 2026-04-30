"""Tests for the run + insight persistence helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import session as db_session_module
from app.insights.dedup import dedup_hash
from app.insights.repo import close_run, open_run, save_insight
from app.models import Insight, Workspace

pytestmark = pytest.mark.asyncio


async def _ensure_workspace(session) -> Workspace:
    """Make a stub workspace + user for tests that don't go via the API."""
    from app.models import User, UserWorkspace

    user = User(email=f"r+{uuid4().hex[:8]}@example.com", password_hash="x")
    session.add(user)
    await session.flush()
    ws = Workspace(name="t-ws", owner_user_id=user.id)
    session.add(ws)
    await session.flush()
    session.add(UserWorkspace(user_id=user.id, workspace_id=ws.id, role="owner"))
    await session.commit()
    await session.refresh(ws)
    return ws


async def test_save_insight_persists_and_increments_run_count(client, engine):
    async with db_session_module.SessionLocal() as session:
        ws = await _ensure_workspace(session)
        run = await open_run(
            session=session, workspace_id=ws.id, scope="manual:all", trigger="manual"
        )
        result = await save_insight(
            session=session,
            run=run,
            workspace_id=ws.id,
            type_="conflict",
            title="Policy disagreement",
            summary="Two docs disagree on the carry-over cap.",
            severity="high",
            confidence=0.9,
            evidence=[{"chunk_id": "00000000-0000-0000-0000-000000000001"}],
            dedup_hash=dedup_hash(
                type_="conflict",
                source_chunk_ids=["00000000-0000-0000-0000-000000000001"],
                title="Policy disagreement",
            ),
        )
        assert result is not None
        assert run.insights_generated == 1
        assert run.insights_skipped == 0


async def test_save_insight_with_existing_dedup_hash_skips(client, engine):
    async with db_session_module.SessionLocal() as session:
        ws = await _ensure_workspace(session)
        run = await open_run(
            session=session, workspace_id=ws.id, scope="manual:all", trigger="manual"
        )
        h = dedup_hash(
            type_="conflict",
            source_chunk_ids=["00000000-0000-0000-0000-000000000001"],
            title="dup",
        )
        first = await save_insight(
            session=session,
            run=run,
            workspace_id=ws.id,
            type_="conflict",
            title="dup",
            summary="",
            severity="medium",
            confidence=None,
            evidence=[],
            dedup_hash=h,
        )
        second = await save_insight(
            session=session,
            run=run,
            workspace_id=ws.id,
            type_="conflict",
            title="dup",
            summary="",
            severity="medium",
            confidence=None,
            evidence=[],
            dedup_hash=h,
        )
        assert first is not None
        assert second is None
        assert run.insights_generated == 1
        assert run.insights_skipped == 1


async def test_close_run_records_status_and_finished_at(client, engine):
    async with db_session_module.SessionLocal() as session:
        ws = await _ensure_workspace(session)
        run = await open_run(
            session=session, workspace_id=ws.id, scope="x", trigger="manual"
        )
        await close_run(session=session, run=run, status="failed", error="boom")
        await session.refresh(run)
        assert run.status == "failed"
        assert run.error == "boom"
        assert run.finished_at is not None


async def test_save_insight_with_no_evidence_still_persists(client, engine):
    async with db_session_module.SessionLocal() as session:
        ws = await _ensure_workspace(session)
        run = await open_run(
            session=session, workspace_id=ws.id, scope="x", trigger="nightly"
        )
        result = await save_insight(
            session=session,
            run=run,
            workspace_id=ws.id,
            type_="stale_document",
            title="Stale: handbook",
            summary="not updated in 120 days",
            severity="low",
            confidence=None,
            evidence=[],
            dedup_hash="zzz",
        )
        assert result is not None
        rows = (await session.execute(select(Insight))).scalars().all()
        assert any(r.title == "Stale: handbook" for r in rows)
