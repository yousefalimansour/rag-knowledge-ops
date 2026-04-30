"""Cache helper tests with the redis client stubbed."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.core import cache as cache_mod


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.store[key] = value

    async def delete(self, *keys: str):
        for k in keys:
            self.store.pop(k, None)


@pytest.fixture
def fake_redis(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(cache_mod, "get_redis", lambda: fake)
    return fake


async def test_get_or_set_loader_runs_only_on_miss(fake_redis):
    calls = {"n": 0}

    async def loader():
        calls["n"] += 1
        return {"answer": 42}

    v1, hit1 = await cache_mod.get_or_set("k1", ttl=60, loader=loader)
    v2, hit2 = await cache_mod.get_or_set("k1", ttl=60, loader=loader)

    assert v1 == {"answer": 42}
    assert v2 == {"answer": 42}
    assert hit1 is False
    assert hit2 is True
    assert calls["n"] == 1


async def test_get_or_set_handles_redis_outage_gracefully(monkeypatch):
    """If Redis is unreachable, the loader still runs and the value still
    flows back to the caller — cache outage degrades to direct compute."""

    class _Broken:
        async def get(self, _key):
            raise RuntimeError("redis down")

        async def set(self, *_a, **_k):
            raise RuntimeError("redis down")

    monkeypatch.setattr(cache_mod, "get_redis", lambda: _Broken())
    called = {"n": 0}

    async def loader():
        called["n"] += 1
        return "value"

    v, hit = await cache_mod.get_or_set("k", ttl=60, loader=loader)
    assert v == "value"
    assert hit is False
    assert called["n"] == 1


def test_make_workspace_key_is_stable_and_isolates_workspaces():
    ws_a = UUID("00000000-0000-0000-0000-000000000001")
    ws_b = UUID("00000000-0000-0000-0000-000000000002")
    k1 = cache_mod.make_workspace_key("q", ws_a, "hello")
    k2 = cache_mod.make_workspace_key("q", ws_a, "hello")
    k3 = cache_mod.make_workspace_key("q", ws_b, "hello")
    assert k1 == k2
    assert k1 != k3
    # Prefix + workspace_id remain readable in the key for log-ability.
    assert k1.startswith(f"q:{ws_a}:")
