"""Redis answer cache.

Key: `q:<workspace_id>:<sha256(question + filters_json)>`.
Value: full QueryOut JSON, TTL = 600s.

Bypassed when we cannot reach Redis (cache becomes a no-op rather than failing
the request). On cache hit we tag the response with `cached: true` so the UI
and logs can tell.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from app.core.rate_limit import get_redis

log = logging.getLogger("api.query_cache")

DEFAULT_TTL = 600  # 10 minutes


def _normalize_filters(filters: dict[str, Any] | None) -> str:
    return json.dumps(filters or {}, sort_keys=True, separators=(",", ":"), default=str)


def make_key(*, workspace_id: UUID, question: str, filters: dict[str, Any] | None) -> str:
    raw = f"{question.strip()}|{_normalize_filters(filters)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"q:{workspace_id}:{digest}"


async def get(key: str) -> dict | None:
    try:
        raw = await get_redis().get(key)
    except Exception as e:  # noqa: BLE001
        log.warning("cache.get_failed", extra={"error": str(e)[:120]})
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def put(key: str, value: dict, *, ttl: int = DEFAULT_TTL) -> None:
    try:
        await get_redis().set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as e:  # noqa: BLE001
        log.warning("cache.put_failed", extra={"error": str(e)[:120]})
