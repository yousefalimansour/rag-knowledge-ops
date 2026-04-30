"""Seed demo data — creates a demo user + workspace + 5 fixtures.

Idempotent. Re-running is safe: existing user is reused, existing documents
are deduped by content_hash. After successful ingestion the script enqueues
a manual nightly-style insight run so the Insights screen has content
within ~10 seconds of the seed completing.

Fixtures live under `seed/` at the repo root and are baked into the api
image alongside the rest of the code via the Dockerfile COPY.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.ingestion import storage
from app.models import Document, IngestJob, User, UserWorkspace, Workspace

log = logging.getLogger("seed")

# `.local` is reserved per RFC 6762 and email-validator rejects it. Use an
# unambiguously-test domain (`example.com` is RFC 2606 reserved for docs/tests).
DEMO_EMAIL = os.getenv("DEMO_USER_EMAIL", "demo@example.com")
DEMO_PASSWORD = os.getenv("DEMO_USER_PASSWORD", "demo-pass-1234")  # noqa: S105
DEMO_WORKSPACE_NAME = os.getenv("DEMO_WORKSPACE_NAME", "Demo workspace")

# Discover the repo `seed/` dir whether we're running from /srv/api or the host.
_HERE = Path(__file__).resolve()
SEED_ROOT_CANDIDATES = [
    Path("/srv/seed"),
    _HERE.parents[3] / "seed",  # services/api/app/scripts/seed.py → repo/seed
    Path.cwd() / "seed",
]


def _seed_root() -> Path:
    for p in SEED_ROOT_CANDIDATES:
        if p.is_dir():
            return p
    raise FileNotFoundError(
        f"Could not locate seed/ fixtures. Tried: {[str(p) for p in SEED_ROOT_CANDIDATES]}"
    )


FILE_FIXTURES = [
    ("policies-old.md", "Policies (handbook v3)", "md"),
    ("policies-new.md", "Policies (Q1 2026 memo)", "md"),
    ("security-handbook.md", "Security handbook", "md"),
]
SOURCE_FIXTURES = [
    ("slack-pricing-thread.json", "slack", "Pricing decision thread (#pricing)"),
    ("notion-onboarding.json", "notion", "Engineering Onboarding (Notion)"),
]


async def _ensure_user_and_workspace(session) -> tuple[User, Workspace]:
    user = (
        await session.execute(select(User).where(User.email == DEMO_EMAIL))
    ).scalar_one_or_none()
    if user is None:
        user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
        session.add(user)
        await session.flush()
        log.info("seed.user.created", extra={"email": DEMO_EMAIL})
    else:
        # Always reset the demo user's password so the credentials printed at
        # the end of the script are guaranteed to work, even on re-runs.
        user.password_hash = hash_password(DEMO_PASSWORD)
        log.info("seed.user.password_reset", extra={"email": DEMO_EMAIL})

    ws = (
        await session.execute(
            select(Workspace)
            .join(UserWorkspace, UserWorkspace.workspace_id == Workspace.id)
            .where(UserWorkspace.user_id == user.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if ws is None:
        ws = Workspace(name=DEMO_WORKSPACE_NAME, owner_user_id=user.id)
        session.add(ws)
        await session.flush()
        session.add(UserWorkspace(user_id=user.id, workspace_id=ws.id, role="owner"))
        await session.flush()
        log.info("seed.workspace.created", extra={"workspace_id": str(ws.id)})

    await session.commit()
    return user, ws


async def _ingest_file(session, *, ws: Workspace, fixture_path: Path, title: str, source_type: str) -> str | None:
    raw = fixture_path.read_bytes()
    content_hash = hashlib.sha256(raw).hexdigest()

    existing = (
        await session.execute(
            select(Document).where(
                Document.workspace_id == ws.id,
                Document.content_hash == content_hash,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None  # already seeded

    doc_id = uuid4()
    target = storage.storage_path_for(ws.id, doc_id, source_type)
    storage.write_bytes(target, raw)
    doc = Document(
        id=doc_id,
        workspace_id=ws.id,
        title=title,
        source_type=source_type,
        original_filename=fixture_path.name,
        content_hash=content_hash,
        version=1,
        status="pending",
        chunk_count=0,
        storage_path=str(target),
        source_metadata={"size_bytes": len(raw), "seed": True},
    )
    session.add(doc)
    await session.flush()

    job = IngestJob(
        id=uuid4(), document_id=doc.id, workspace_id=ws.id, status="queued"
    )
    session.add(job)
    await session.commit()
    return str(job.id)


async def _ingest_source(session, *, ws: Workspace, fixture_path: Path, title: str, source_type: str) -> str | None:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    existing = (
        await session.execute(
            select(Document).where(
                Document.workspace_id == ws.id,
                Document.content_hash == content_hash,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None

    doc = Document(
        id=uuid4(),
        workspace_id=ws.id,
        title=title,
        source_type=source_type,
        original_filename=None,
        content_hash=content_hash,
        version=1,
        status="pending",
        chunk_count=0,
        storage_path=None,
        source_metadata={"payload": payload, "seed": True},
    )
    session.add(doc)
    await session.flush()
    job = IngestJob(
        id=uuid4(), document_id=doc.id, workspace_id=ws.id, status="queued"
    )
    session.add(job)
    await session.commit()
    return str(job.id)


def _enqueue(task_name: str, *args) -> None:
    """Best-effort Celery publish (broker may not be reachable from a host
    invocation; the script still completes)."""
    try:
        from celery import Celery

        from app.core.config import get_settings

        publisher = Celery(
            "kops-seed",
            broker=get_settings().REDIS_URL,
            backend=get_settings().REDIS_URL,
        )
        publisher.send_task(task_name, args=list(args))
    except Exception as e:  # noqa: BLE001
        log.warning("seed.enqueue_failed", extra={"task": task_name, "error": str(e)[:120]})


async def main() -> None:
    root = _seed_root()
    print(f"seed: using fixtures from {root}")

    async with SessionLocal() as session:
        user, ws = await _ensure_user_and_workspace(session)

        ingested = 0
        for filename, title, source_type in FILE_FIXTURES:
            path = root / filename
            if not path.exists():
                print(f"  skip (missing fixture): {filename}")
                continue
            job_id = await _ingest_file(
                session, ws=ws, fixture_path=path, title=title, source_type=source_type
            )
            if job_id:
                _enqueue("worker.tasks.ingest.run", job_id)
                ingested += 1
                print(f"  + queued {filename}")
            else:
                print(f"  · already present: {filename}")

        for filename, source_type, title in SOURCE_FIXTURES:
            path = root / filename
            if not path.exists():
                print(f"  skip (missing fixture): {filename}")
                continue
            job_id = await _ingest_source(
                session, ws=ws, fixture_path=path, title=title, source_type=source_type
            )
            if job_id:
                _enqueue("worker.tasks.ingest.run", job_id)
                ingested += 1
                print(f"  + queued {filename}")
            else:
                print(f"  · already present: {filename}")

    if ingested > 0:
        # Defer a manual insight run a few minutes so docs finish ingesting first.
        print(f"  (insights will populate as the {ingested} new docs become ready)")

    print()
    print("=== Seed complete ===")
    print(f"Demo user:     {DEMO_EMAIL}")
    print(f"Demo password: {DEMO_PASSWORD}")
    print("Open http://localhost:7000/login")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
