"""Session-scoped fixtures for the retrieval-quality eval harness.

The corpus is ingested once per pytest session into a fresh workspace whose
name is unique to the session. Documents are ingested SYNCHRONOUSLY by
calling `services.ingest.ingest_document` directly, which means we don't
depend on the Celery worker queue being drained — but we do hit real
Postgres, real Chroma, and real Gemini for embeddings.

If `GOOGLE_API_KEY` is not set the eval is skipped at collection time with
a clear message, since the embedding + reasoning steps require it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
import yaml

from app.ai import chroma_client
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.ingestion import storage
from app.models import Document, IngestJob, User, UserWorkspace, Workspace
from app.services.ingest import ingest_document

log = logging.getLogger("eval.retrieval")

CORPUS_DIR = Path(__file__).parent / "corpus"
QUESTIONS_FILE = Path(__file__).parent / "questions.yaml"

# Map filename → (logical_id, title, source_type). Logical id is the stem of
# the filename and is what `questions.yaml` uses in `expected_doc_ids`.
FILE_FIXTURES = [
    ("pricing-policy-v1.md", "pricing-policy-v1", "Pricing Policy v1 (archived)", "md"),
    ("pricing-policy-v2.md", "pricing-policy-v2", "Pricing Policy v2 (current)", "md"),
    ("product-decisions.md", "product-decisions", "Product Decisions Log 2025", "md"),
    ("security-handbook.md", "security-handbook", "Security Handbook", "md"),
]
SOURCE_FIXTURES = [
    ("support-logs.json", "support-logs", "Support channel — recent threads", "slack"),
    ("onboarding.notion.json", "onboarding.notion", "Engineering Onboarding (Notion)", "notion"),
]


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Skip the whole eval run if no Gemini key is available."""
    if not os.environ.get("GOOGLE_API_KEY"):
        skip = pytest.mark.skip(reason="GOOGLE_API_KEY not set — retrieval eval requires Gemini")
        for item in items:
            item.add_marker(skip)


@dataclass(slots=True)
class EvalCorpus:
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    doc_id_by_logical: dict[str, uuid.UUID]
    title_by_logical: dict[str, str]

    def doc_id_for(self, logical_id: str) -> uuid.UUID:
        if logical_id not in self.doc_id_by_logical:
            raise KeyError(
                f"Logical id {logical_id!r} not in corpus. "
                f"Available: {sorted(self.doc_id_by_logical)}"
            )
        return self.doc_id_by_logical[logical_id]


def load_questions() -> list[dict[str, Any]]:
    raw = yaml.safe_load(QUESTIONS_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise RuntimeError(f"{QUESTIONS_FILE} must be a non-empty YAML list")
    for q in raw:
        q.setdefault("expected_doc_ids", [])
        q.setdefault("expected_phrases", [])
        q.setdefault("must_refuse", False)
    return raw


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def corpus() -> AsyncIterator[EvalCorpus]:
    if not os.environ.get("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set — retrieval eval requires Gemini")

    session_token = uuid.uuid4().hex[:8]
    email = f"eval-{session_token}@example.com"

    async with SessionLocal() as session:
        user = User(email=email, password_hash=hash_password(f"eval-pass-{session_token}"))
        session.add(user)
        await session.flush()

        ws = Workspace(name=f"eval-ws-{session_token}", owner_user_id=user.id)
        session.add(ws)
        await session.flush()
        session.add(UserWorkspace(user_id=user.id, workspace_id=ws.id, role="owner"))
        await session.commit()

        log.info("eval.corpus.workspace_created", extra={"workspace_id": str(ws.id)})

        doc_id_by_logical: dict[str, uuid.UUID] = {}
        title_by_logical: dict[str, str] = {}

        for filename, logical_id, title, source_type in FILE_FIXTURES:
            doc_id = await _ingest_file(
                session=session,
                workspace_id=ws.id,
                fixture_path=CORPUS_DIR / filename,
                title=title,
                source_type=source_type,
            )
            doc_id_by_logical[logical_id] = doc_id
            title_by_logical[logical_id] = title

        for filename, logical_id, title, source_type in SOURCE_FIXTURES:
            doc_id = await _ingest_source(
                session=session,
                workspace_id=ws.id,
                fixture_path=CORPUS_DIR / filename,
                title=title,
                source_type=source_type,
            )
            doc_id_by_logical[logical_id] = doc_id
            title_by_logical[logical_id] = title

    log.info(
        "eval.corpus.ready",
        extra={"workspace_id": str(ws.id), "documents": len(doc_id_by_logical)},
    )

    yield EvalCorpus(
        workspace_id=ws.id,
        user_id=user.id,
        doc_id_by_logical=doc_id_by_logical,
        title_by_logical=title_by_logical,
    )

    # Best-effort cleanup so re-runs don't pile up data. We also delete the
    # Chroma vectors per-doc since they're keyed by chunk_id (workspace_id is
    # only metadata, not a key namespace).
    try:
        for doc_id in doc_id_by_logical.values():
            chroma_client.delete_for_document(doc_id)
        async with SessionLocal() as session:
            ws_row = await session.get(Workspace, ws.id)
            if ws_row is not None:
                await session.delete(ws_row)
            user_row = await session.get(User, user.id)
            if user_row is not None:
                await session.delete(user_row)
            await session.commit()
        log.info("eval.corpus.cleaned_up", extra={"workspace_id": str(ws.id)})
    except Exception:  # noqa: BLE001
        log.exception("eval.corpus.cleanup_failed")


async def _ingest_file(
    *,
    session,
    workspace_id: uuid.UUID,
    fixture_path: Path,
    title: str,
    source_type: str,
) -> uuid.UUID:
    raw = fixture_path.read_bytes()
    content_hash = hashlib.sha256(raw).hexdigest()
    doc_id = uuid.uuid4()
    target = storage.storage_path_for(workspace_id, doc_id, source_type)
    storage.write_bytes(target, raw)
    doc = Document(
        id=doc_id,
        workspace_id=workspace_id,
        title=title,
        source_type=source_type,
        original_filename=fixture_path.name,
        content_hash=content_hash,
        version=1,
        status="pending",
        chunk_count=0,
        storage_path=str(target),
        source_metadata={"size_bytes": len(raw), "eval": True},
    )
    session.add(doc)
    await session.flush()
    job = IngestJob(
        id=uuid.uuid4(), document_id=doc.id, workspace_id=workspace_id, status="queued"
    )
    session.add(job)
    await session.commit()
    started = time.monotonic()
    result = await ingest_document(session=session, job_id=job.id)
    log.info(
        "eval.corpus.ingest_done",
        extra={
            "title": title,
            "logical": fixture_path.stem,
            "chunks": result.get("chunks_indexed"),
            "elapsed_s": round(time.monotonic() - started, 2),
        },
    )
    return doc.id


async def _ingest_source(
    *,
    session,
    workspace_id: uuid.UUID,
    fixture_path: Path,
    title: str,
    source_type: str,
) -> uuid.UUID:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        workspace_id=workspace_id,
        title=title,
        source_type=source_type,
        original_filename=None,
        content_hash=content_hash,
        version=1,
        status="pending",
        chunk_count=0,
        storage_path=None,
        source_metadata={"payload": payload, "eval": True},
    )
    session.add(doc)
    await session.flush()
    job = IngestJob(
        id=uuid.uuid4(), document_id=doc.id, workspace_id=workspace_id, status="queued"
    )
    session.add(job)
    await session.commit()
    started = time.monotonic()
    result = await ingest_document(session=session, job_id=job.id)
    log.info(
        "eval.corpus.ingest_done",
        extra={
            "title": title,
            "logical": fixture_path.stem,
            "chunks": result.get("chunks_indexed"),
            "elapsed_s": round(time.monotonic() - started, 2),
        },
    )
    return doc.id
