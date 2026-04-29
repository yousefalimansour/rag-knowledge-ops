from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.rate_limit import get_redis
from app.db.session import engine

router = APIRouter(tags=["health"])
log = logging.getLogger("api.health")


async def _check_db() -> str:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as e:
        log.warning("health.db_failed", extra={"error": str(e)})
        return "down"


async def _check_redis() -> str:
    try:
        await get_redis().ping()
        return "ok"
    except Exception as e:
        log.warning("health.redis_failed", extra={"error": str(e)})
        return "down"


async def _check_chroma() -> str:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{get_settings().CHROMA_URL}/api/v1/heartbeat")
            return "ok" if r.status_code == 200 else "down"
    except Exception as e:
        log.warning("health.chroma_failed", extra={"error": str(e)})
        return "down"


def _check_gemini() -> str:
    return "ok" if get_settings().GOOGLE_API_KEY else "unknown"


@router.get("/api/health")
async def health() -> dict[str, str]:
    db, redis_, chroma = await asyncio.gather(_check_db(), _check_redis(), _check_chroma())
    overall = "ok" if all(s == "ok" for s in (db, redis_, chroma)) else "degraded"
    return {
        "status": overall,
        "db": db,
        "redis": redis_,
        "chroma": chroma,
        "gemini": _check_gemini(),
    }
