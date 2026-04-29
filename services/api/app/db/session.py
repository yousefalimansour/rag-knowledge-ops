from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()

# SQLite (used by the unit-test fixture) uses StaticPool and rejects
# pool_size / max_overflow. Only pass those for real Postgres URLs.
_engine_kwargs: dict[str, object] = {"pool_pre_ping": True, "echo": False}
if not _settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update(pool_size=10, max_overflow=10)

engine = create_async_engine(_settings.DATABASE_URL, **_engine_kwargs)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
