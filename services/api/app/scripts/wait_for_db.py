"""Block until Postgres accepts a connection — used by the api entrypoint."""

from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

log = logging.getLogger("api.wait_for_db")


async def main(retries: int = 60, delay_s: float = 1.0) -> int:
    url = get_settings().DATABASE_URL
    engine = create_async_engine(url, pool_pre_ping=True)
    for attempt in range(1, retries + 1):
        try:
            async with engine.connect() as conn:
                await conn.exec_driver_sql("SELECT 1")
            print(f"db ready after {attempt} attempt(s)")
            await engine.dispose()
            return 0
        except Exception as e:  # noqa: BLE001
            print(f"db not ready (attempt {attempt}/{retries}): {e}")
            await asyncio.sleep(delay_s)
    await engine.dispose()
    print("db never became ready", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
