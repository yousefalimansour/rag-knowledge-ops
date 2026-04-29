from __future__ import annotations

import time
from dataclasses import dataclass

import redis.asyncio as redis
from fastapi import HTTPException, Request, status

from app.core.config import get_settings

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    return _redis


@dataclass(slots=True)
class RateLimit:
    """Sliding-window counter per (key, window). Approximates a token bucket."""

    name: str
    capacity: int
    window_seconds: int

    async def hit(self, key: str) -> None:
        r = get_redis()
        bucket = f"rl:{self.name}:{key}:{int(time.time() // self.window_seconds)}"
        # INCR + EXPIRE in a tiny pipeline so the TTL is set on first hit only.
        async with r.pipeline(transaction=False) as pipe:
            pipe.incr(bucket, 1)
            pipe.expire(bucket, self.window_seconds, nx=True)
            count, _ = await pipe.execute()
        if int(count) > self.capacity:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"rate limit exceeded for {self.name}",
                headers={"Retry-After": str(self.window_seconds)},
            )


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
