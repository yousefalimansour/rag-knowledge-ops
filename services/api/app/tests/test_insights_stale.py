"""Stale-document scanner — deterministic, no LLM.

Builds a workspace with two ready docs (one fresh, one 100 days old) and
asserts the scanner produces exactly one `stale_document` insight on the
old doc, idempotent on a second run.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.insights.stale import scan_stale_documents
from app.models import (
    Chunk,
    Document,
    Insight,
    InsightRun,
    User,
    UserWorkspace,
    Workspace,
)
from sqlalchemy import select


@pytest.fixture
async def seeded_workspace(engine):
    """Create a user + workspace + 2 documents (one fresh, one 100d old)."""
    from app.db.session import SessionLocal

    async with SessionLocal() as session:
        user = User(
            id=uuid4(),
            email="stale-test@example.com",
            password_hash="argon2id$noop",
        )
        session.add(user)
        ws = Workspace(id=uuid4(), name="stale-test-ws", owner_user_id=user.id)
        session.add(ws)
        session.add(UserWorkspace(user_id=user.id, workspace_id=ws.id, role="owner"))

        now = datetime.now(UTC)
        old_doc = Document(
            id=uuid4(),
            workspace_id=ws.id,
            title="ancient-policies",
            source_type="md",
            content_hash="hash-old-" + uuid4().hex[:10],
            version=1,
            status="ready",
            chunk_count=1,
            source_metadata={},
            storage_path="/tmp/old.md",
        )
        old_doc.updated_at = now - timedelta(days=100)
        session.add(old_doc)
        session.add(
            Chunk(
                id=uuid4(),
                document_id=old_doc.id,
                chunk_index=0,
                text="some old content",
                text_hash="text-old",
            )
        )

        fresh_doc = Document(
            id=uuid4(),
            workspace_id=ws.id,
            title="fresh-handbook",
            source_type="md",
            content_hash="hash-fresh-" + uuid4().hex[:10],
            version=1,
            status="ready",
            chunk_count=1,
            source_metadata={},
            storage_path="/tmp/fresh.md",
        )
        fresh_doc.updated_at = now - timedelta(days=10)
        session.add(fresh_doc)
        session.add(
            Chunk(
                id=uuid4(),
                document_id=fresh_doc.id,
                chunk_index=0,
                text="fresh content",
                text_hash="text-fresh",
            )
        )
        await session.commit()
        # Force-set updated_at again post-commit because TimestampMixin.onupdate
        # rewrites it on insert flush via server defaults on Postgres — on
        # SQLite our test backend it just uses Python defaults, so this stays.
        old_doc.updated_at = now - timedelta(days=100)
        await session.commit()
        return ws.id


async def test_stale_scan_flags_only_old_doc(seeded_workspace, monkeypatch):
    """One old doc → one stale_document insight; fresh doc untouched."""
    from app.db.session import SessionLocal

    # Bypass real notification dispatch — keeps the test focused on the scan.
    from app.insights import stale as stale_mod

    async def _noop(**_k):
        return None

    monkeypatch.setattr(stale_mod, "notify_insight_created", _noop)

    workspace_id = seeded_workspace
    async with SessionLocal() as session:
        run = InsightRun(
            id=uuid4(),
            workspace_id=workspace_id,
            scope="nightly",
            trigger="nightly",
            status="running",
            insights_generated=0,
            insights_skipped=0,
        )
        session.add(run)
        await session.commit()

        await scan_stale_documents(
            session=session, run=run, workspace_id=workspace_id
        )

        rows = (
            await session.execute(
                select(Insight).where(Insight.workspace_id == workspace_id)
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].type == "stale_document"
        assert "ancient-policies" in rows[0].title


async def test_stale_scan_is_idempotent(seeded_workspace, monkeypatch):
    """Re-running the scan must not duplicate insights — dedup_hash kicks in."""
    from app.db.session import SessionLocal
    from app.insights import stale as stale_mod

    async def _noop(**_k):
        return None

    monkeypatch.setattr(stale_mod, "notify_insight_created", _noop)

    workspace_id = seeded_workspace

    async with SessionLocal() as session:
        run1 = InsightRun(
            id=uuid4(),
            workspace_id=workspace_id,
            scope="nightly",
            trigger="nightly",
            status="running",
            insights_generated=0,
            insights_skipped=0,
        )
        session.add(run1)
        await session.commit()
        await scan_stale_documents(session=session, run=run1, workspace_id=workspace_id)

    async with SessionLocal() as session:
        run2 = InsightRun(
            id=uuid4(),
            workspace_id=workspace_id,
            scope="nightly",
            trigger="nightly",
            status="running",
            insights_generated=0,
            insights_skipped=0,
        )
        session.add(run2)
        await session.commit()
        await scan_stale_documents(session=session, run=run2, workspace_id=workspace_id)

        rows = (
            await session.execute(
                select(Insight).where(Insight.workspace_id == workspace_id)
            )
        ).scalars().all()
        assert len(rows) == 1, "second run must dedup the same insight"
