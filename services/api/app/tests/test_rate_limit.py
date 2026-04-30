"""Rate-limiter math.

The real `RateLimit.hit` talks to Redis through a pipeline. We swap a stub
client in via `get_redis` so the test stays unit-fast and exercises the
windowing + capacity logic, plus the 429 + Retry-After contract.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core import rate_limit

# Capture the real `.hit` before conftest's autouse fixture stubs it.
_REAL_HIT = rate_limit.RateLimit.hit


class _FakePipeline:
    def __init__(self, store: dict[str, int]) -> None:
        self.store = store
        self._ops: list[tuple[str, str, int]] = []

    def incr(self, key: str, amount: int) -> "_FakePipeline":
        self._ops.append(("incr", key, amount))
        return self

    def expire(self, key: str, seconds: int, nx: bool = False) -> "_FakePipeline":  # noqa: ARG002
        self._ops.append(("expire", key, seconds))
        return self

    async def execute(self) -> list[int]:
        results: list[int] = []
        for op, key, amount in self._ops:
            if op == "incr":
                self.store[key] = self.store.get(key, 0) + amount
                results.append(self.store[key])
            else:
                results.append(1)
        self._ops.clear()
        return results

    async def __aenter__(self) -> "_FakePipeline":
        return self

    async def __aexit__(self, *_a: object) -> None:
        return None


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    def pipeline(self, transaction: bool = False) -> _FakePipeline:  # noqa: ARG002
        return _FakePipeline(self.store)


@pytest.fixture(autouse=True)
def _patch_redis_and_time(monkeypatch):
    """Freeze time so all hits land in the same window, and inject the fake redis.
    Also reverts the global conftest stub that no-ops `.hit` for every other test."""
    fake = _FakeRedis()
    monkeypatch.setattr(rate_limit, "get_redis", lambda: fake)
    monkeypatch.setattr(rate_limit.time, "time", lambda: 1_000_000.0)
    monkeypatch.setattr(rate_limit.RateLimit, "hit", _REAL_HIT)
    return fake


async def test_under_capacity_allows_traffic():
    rl = rate_limit.RateLimit(name="test", capacity=3, window_seconds=60)
    for _ in range(3):
        await rl.hit("user-a")  # all three should pass


async def test_over_capacity_raises_429_with_retry_after():
    rl = rate_limit.RateLimit(name="test", capacity=2, window_seconds=60)
    await rl.hit("user-a")
    await rl.hit("user-a")
    with pytest.raises(HTTPException) as exc:
        await rl.hit("user-a")
    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "60"


async def test_keys_are_isolated_per_user():
    rl = rate_limit.RateLimit(name="test", capacity=1, window_seconds=60)
    await rl.hit("user-a")
    await rl.hit("user-b")  # different key — should not 429
    with pytest.raises(HTTPException):
        await rl.hit("user-a")


async def test_window_rotates_into_a_new_bucket(monkeypatch):
    rl = rate_limit.RateLimit(name="test", capacity=1, window_seconds=60)
    await rl.hit("user-a")
    # Move time forward into the next 60s window.
    monkeypatch.setattr(rate_limit.time, "time", lambda: 1_000_060.0)
    await rl.hit("user-a")  # fresh bucket → no 429


def test_client_ip_prefers_forwarded_header():
    class _Req:
        headers = {"x-forwarded-for": "203.0.113.7, 10.0.0.1"}

        class client:
            host = "10.0.0.1"

    assert rate_limit.client_ip(_Req()) == "203.0.113.7"


def test_client_ip_falls_back_to_socket_peer():
    class _Req:
        headers: dict[str, str] = {}

        class client:
            host = "198.51.100.4"

    assert rate_limit.client_ip(_Req()) == "198.51.100.4"


def test_client_ip_handles_missing_client():
    class _Req:
        headers: dict[str, str] = {}
        client = None

    assert rate_limit.client_ip(_Req()) == "unknown"
