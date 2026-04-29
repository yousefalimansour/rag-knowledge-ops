"""Seed demo data — placeholder until step 02 lands real ingestion fixtures."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User, UserWorkspace, Workspace

log = logging.getLogger("api.seed")

DEMO_EMAIL = "demo@kops.local"
DEMO_PASSWORD = "demo-pass-1234"  # noqa: S105 — local-only seed


async def main() -> None:
    async with SessionLocal() as session:
        existing = (
            await session.execute(select(User).where(User.email == DEMO_EMAIL))
        ).scalar_one_or_none()
        if existing is not None:
            print(f"demo user already present: {DEMO_EMAIL}")
            return

        user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
        session.add(user)
        await session.flush()

        ws = Workspace(name="Demo workspace", owner_user_id=user.id)
        session.add(ws)
        await session.flush()

        session.add(UserWorkspace(user_id=user.id, workspace_id=ws.id, role="owner"))
        await session.commit()
        print(f"seeded demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
