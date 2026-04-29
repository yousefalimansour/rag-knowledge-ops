from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_health_returns_envelope(client, monkeypatch):
    # Stub external checks so the test doesn't need redis/chroma running.
    from app.api import health

    async def _ok() -> str:
        return "ok"

    monkeypatch.setattr(health, "_check_db", _ok)
    monkeypatch.setattr(health, "_check_redis", _ok)
    monkeypatch.setattr(health, "_check_chroma", _ok)

    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["redis"] == "ok"
    assert body["chroma"] == "ok"
    assert body["gemini"] in {"ok", "unknown"}
