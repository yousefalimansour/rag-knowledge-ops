"""End-to-end ingest service test with stubbed embeddings + Chroma.

Walks: upload TXT → run orchestrator → assert chunks persisted, status ready,
job succeeded, embedding cache populated, no real network calls.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import session as db_session_module
from app.models import Chunk, Document, EmbeddingCache, IngestJob

pytestmark = pytest.mark.asyncio


async def test_ingest_orchestrator_processes_txt_to_ready(
    signed_in, engine, monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)

    # Stub embeddings so no Gemini call happens.
    from app.ai import embeddings as emb

    def fake_embed_one(text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        # Deterministic 768-d vector keyed by text hash.
        h = sum(text.encode("utf-8")) % 100
        return [float(h) / 100.0] * 768

    monkeypatch.setattr(emb, "embed_one", fake_embed_one)

    # Stub Chroma so no HTTP call happens.
    from app.ai import chroma_client as cc

    upserts: list[dict] = []
    monkeypatch.setattr(cc, "delete_for_document", lambda _doc_id: None)
    monkeypatch.setattr(
        cc,
        "upsert_chunks",
        lambda **kw: upserts.append(kw),
    )

    # Stub the celery enqueue path on the api side; we'll run the orchestrator
    # directly so the test does not need a worker.
    from app.api import ingest as ingest_router
    monkeypatch.setattr(ingest_router, "_ingest_dispatcher", lambda: lambda _job_id: None)

    files = [("files", ("kb.txt", b"alpha beta gamma.\n\ndelta epsilon zeta.", "text/plain"))]
    r = await signed_in.post("/api/ingest/files", files=files)
    assert r.status_code == 202, r.text
    job_id_str = r.json()["jobs"][0]["id"]

    # Run the orchestrator directly.
    from uuid import UUID

    from app.services.ingest import ingest_document

    async with db_session_module.SessionLocal() as session:
        result = await ingest_document(session=session, job_id=UUID(job_id_str))

    assert result["status"] == "ready"
    assert result["chunks_indexed"] >= 1

    # Verify persisted state.
    async with db_session_module.SessionLocal() as session:
        job = (
            await session.execute(select(IngestJob).where(IngestJob.id == UUID(job_id_str)))
        ).scalar_one()
        assert job.status == "succeeded"
        assert job.stage == "indexed"

        doc = (
            await session.execute(select(Document).where(Document.id == job.document_id))
        ).scalar_one()
        assert doc.status == "ready"
        assert doc.chunk_count >= 1

        chunks = (
            (await session.execute(select(Chunk).where(Chunk.document_id == doc.id)))
            .scalars()
            .all()
        )
        assert len(chunks) == doc.chunk_count
        assert all(c.embedding_id == str(c.id) for c in chunks)

        cache = (
            (await session.execute(select(EmbeddingCache))).scalars().all()
        )
        assert len(cache) >= 1

    assert upserts, "Chroma upsert was never called"
    payload = upserts[0]
    assert len(payload["ids"]) == doc.chunk_count
    assert all(len(v) == 768 for v in payload["embeddings"])


async def test_ingest_orchestrator_idempotent_on_ready_doc(signed_in, engine, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    from app.ai import chroma_client as cc
    from app.ai import embeddings as emb
    from app.api import ingest as ingest_router

    monkeypatch.setattr(emb, "embed_one", lambda t, **_: [0.1] * 768)
    monkeypatch.setattr(cc, "delete_for_document", lambda _doc_id: None)
    monkeypatch.setattr(cc, "upsert_chunks", lambda **_kw: None)
    monkeypatch.setattr(ingest_router, "_ingest_dispatcher", lambda: lambda _job_id: None)

    files = [("files", ("idem.txt", b"once and only once", "text/plain"))]
    r = await signed_in.post("/api/ingest/files", files=files)
    assert r.status_code == 202, r.text
    job_id_str = r.json()["jobs"][0]["id"]

    from uuid import UUID

    from app.services.ingest import ingest_document

    async with db_session_module.SessionLocal() as session:
        first = await ingest_document(session=session, job_id=UUID(job_id_str))
    async with db_session_module.SessionLocal() as session:
        second = await ingest_document(session=session, job_id=UUID(job_id_str))

    assert first["status"] == "ready"
    assert second["status"] == "ready"
    # Second call is a no-op — same chunk count, no duplicate work.
    assert second["chunks_indexed"] == first["chunks_indexed"]
