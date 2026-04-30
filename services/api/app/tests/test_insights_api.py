"""HTTP-level tests for the insights + notifications routers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db import session as db_session_module
from app.insights.dedup import dedup_hash
from app.models import Insight, Notification

pytestmark = pytest.mark.asyncio


async def _seed_workspace_and_get_id(signed_in) -> str:
    me = await signed_in.get("/auth/me")
    return me.json()["workspace"]["id"]


async def test_list_insights_returns_workspace_scoped_items(signed_in, engine):
    ws_id = await _seed_workspace_and_get_id(signed_in)

    async with db_session_module.SessionLocal() as session:
        from uuid import UUID

        for sev in ("low", "medium", "high"):
            session.add(
                Insight(
                    id=uuid4(),
                    workspace_id=UUID(ws_id),
                    type="conflict",
                    title=f"insight {sev}",
                    summary="…",
                    severity=sev,
                    confidence=None,
                    evidence=[],
                    dedup_hash=dedup_hash(type_="conflict", source_chunk_ids=[uuid4()], title=sev),
                    state="active",
                )
            )
        await session.commit()

    r = await signed_in.get("/api/insights")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 3

    r = await signed_in.get("/api/insights?severity=high")
    assert all(i["severity"] == "high" for i in r.json()["items"])


async def test_patch_insight_state_transitions(signed_in, engine, monkeypatch):
    monkeypatch.setattr(
        "app.api.insights._publish_manual", lambda **_kw: None
    )
    ws_id = await _seed_workspace_and_get_id(signed_in)

    async with db_session_module.SessionLocal() as session:
        from uuid import UUID

        ins = Insight(
            id=uuid4(),
            workspace_id=UUID(ws_id),
            type="conflict",
            title="t",
            summary="s",
            severity="medium",
            confidence=None,
            evidence=[],
            dedup_hash=dedup_hash(type_="conflict", source_chunk_ids=[uuid4()], title="t"),
            state="active",
        )
        session.add(ins)
        await session.commit()
        ins_id = str(ins.id)

    r = await signed_in.patch(f"/api/insights/{ins_id}", json={"state": "dismissed"})
    assert r.status_code == 200
    assert r.json()["state"] == "dismissed"

    r = await signed_in.patch(f"/api/insights/{ins_id}", json={"state": "active"})
    assert r.json()["state"] == "active"


async def test_manual_run_creates_queued_run_record(signed_in, engine, monkeypatch):
    enqueued: list[dict] = []
    monkeypatch.setattr(
        "app.api.insights._publish_manual",
        lambda **kw: enqueued.append(kw),
    )

    r = await signed_in.post("/api/insights/run", json={"scope": "all"})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert enqueued and enqueued[0]["scope"] == "all"

    runs = await signed_in.get("/api/insights/runs")
    items = runs.json()["items"]
    assert any(item["id"] == body["run_id"] for item in items)


async def test_unauth_insights_endpoints_return_401(client):
    for path in ["/api/insights", "/api/insights/runs"]:
        r = await client.get(path)
        assert r.status_code == 401


async def test_notifications_list_and_mark_read_cycle(signed_in, engine):
    ws_id = await _seed_workspace_and_get_id(signed_in)
    me = await signed_in.get("/auth/me")
    user_id = me.json()["user"]["id"]

    async with db_session_module.SessionLocal() as session:
        from uuid import UUID

        for i in range(3):
            session.add(
                Notification(
                    id=uuid4(),
                    user_id=UUID(user_id),
                    workspace_id=UUID(ws_id),
                    type="insight_created",
                    title=f"n{i}",
                    body="x",
                    severity="medium",
                    link_kind="insight",
                    link_id=uuid4(),
                    created_at=datetime.now(UTC) - timedelta(minutes=i),
                )
            )
        await session.commit()

    r = await signed_in.get("/api/notifications")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 3
    assert body["unread_count"] == 3

    first_id = body["items"][0]["id"]
    r = await signed_in.patch(f"/api/notifications/{first_id}")
    assert r.status_code == 200
    assert r.json()["read_at"] is not None

    r = await signed_in.get("/api/notifications")
    assert r.json()["unread_count"] == 2

    r = await signed_in.post("/api/notifications/mark-all-read")
    assert r.status_code == 204

    r = await signed_in.get("/api/notifications")
    assert r.json()["unread_count"] == 0
