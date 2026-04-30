"""Generic Redis cache helpers.

`get_or_set` is the cache-aside primitive used everywhere. The query-cache,
retrieval-cache, and (eventually) any other workspace-scoped cache should
build their key with `make_workspace_key()` so cross-tenant collisions are
impossible by construction.

All helpers are best-effort: a Redis outage degrades to a cache miss rather
than an HTTP 500.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar
from uuid import UUID

from app.core.rate_limit import get_redis

log = logging.getLogger("api.cache")

T = TypeVar("T")


def make_workspace_key(prefix: str, workspace_id: UUID, *parts: str) -> str:
    """`{prefix}:{workspace_id}:{sha256(parts)}` — small + collision-resistant."""
    raw = "|".join(parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{prefix}:{workspace_id}:{digest}"


async def get_json(key: str) -> Any | None:
    try:
        raw = await get_redis().get(key)
    except Exception as e:  # noqa: BLE001
        log.warning("cache.get_failed", extra={"key": key, "error": str(e)[:120]})
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def set_json(key: str, value: Any, *, ttl: int) -> None:
    try:
        await get_redis().set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as e:  # noqa: BLE001
        log.warning("cache.set_failed", extra={"key": key, "error": str(e)[:120]})


async def delete(*keys: str) -> None:
    if not keys:
        return
    try:
        await get_redis().delete(*keys)
    except Exception as e:  # noqa: BLE001
        log.warning("cache.delete_failed", extra={"error": str(e)[:120]})


async def get_or_set(
    key: str,
    *,
    ttl: int,
    loader: Callable[[], Awaitable[T]],
) -> tuple[T, bool]:
    """Returns `(value, cached)`. Loader runs only on a miss."""
    cached = await get_json(key)
    if cached is not None:
        return cached, True
    fresh = await loader()
    await set_json(key, fresh, ttl=ttl)
    return fresh, False
