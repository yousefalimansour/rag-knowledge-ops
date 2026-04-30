"""End-to-end ingest orchestrator: extract → normalize → chunk → embed → index.

Called from the Celery task per document. Idempotent: if the document is
already `ready`, returns a no-op result; otherwise it runs each stage,
updating the IngestJob's `stage` field and the Document's status as it goes.

Failure handling: any exception bubbles up after the job/document are marked
`failed` with an error message persisted. The Celery task chooses retry vs.
final fail.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import chroma_client
from app.ai.embeddings import embed_texts, text_hash
from app.core.errors import IngestionError
from app.ingestion import storage
from app.ingestion.chunker import chunk_document
from app.ingestion.extractors import extract_file, extract_source
from app.ingestion.types import ExtractedDocument
from app.models import Chunk, Document, IngestJob

log = logging.getLogger("api.ingest")


async def ingest_document(*, session: AsyncSession, job_id: UUID) -> dict:
    job = await session.get(IngestJob, job_id)
    if job is None:
        raise IngestionError(f"IngestJob {job_id} not found")

    doc = await session.get(Document, job.document_id)
    if doc is None:
        raise IngestionError(f"Document {job.document_id} not found")

    if doc.status == "ready":
        log.info("ingest.idempotent_skip", extra={"document_id": str(doc.id)})
        return {"status": "ready", "deduplicated": False, "chunks_indexed": doc.chunk_count}

    job.status = "running"
    job.attempts += 1
    job.started_at = job.started_at or datetime.now(UTC)
    job.error = None
    doc.status = "processing"
    doc.error = None
    await session.commit()

    try:
        extracted = await _extract_for(doc=doc, session=session, job=job)
        chunks_payload = await _chunk_and_persist(doc=doc, extracted=extracted, session=session, job=job)
        await _embed_and_index(doc=doc, chunks=chunks_payload, session=session, job=job)

        doc.status = "ready"
        doc.processed_at = datetime.now(UTC)
        doc.chunk_count = len(chunks_payload)
        job.status = "succeeded"
        job.stage = "indexed"
        job.finished_at = datetime.now(UTC)
        await session.commit()

        log.info(
            "ingest.complete",
            extra={"document_id": str(doc.id), "chunks": len(chunks_payload)},
        )

        # Post-ingest hook: notify users + enqueue scoped insight generation.
        from app.notifications.dispatcher import notify_ingest_completed

        await notify_ingest_completed(
            session=session,
            workspace_id=doc.workspace_id,
            document_id=doc.id,
            document_title=doc.title,
            chunk_count=doc.chunk_count,
        )
        await session.commit()
        _enqueue_scoped_insights(workspace_id=doc.workspace_id, doc_id=doc.id)

        return {"status": "ready", "chunks_indexed": len(chunks_payload), "deduplicated": False}

    except Exception as e:  # noqa: BLE001
        log.exception("ingest.failed", extra={"document_id": str(doc.id)})
        job.status = "failed"
        job.error = str(e)[:2000]
        job.finished_at = datetime.now(UTC)
        doc.status = "failed"
        doc.error = str(e)[:2000]
        await session.commit()

        # Best-effort failure notification.
        try:
            from app.notifications.dispatcher import notify_ingest_completed

            await notify_ingest_completed(
                session=session,
                workspace_id=doc.workspace_id,
                document_id=doc.id,
                document_title=doc.title,
                chunk_count=0,
                failed=True,
                error=str(e)[:200],
            )
            await session.commit()
        except Exception:  # noqa: BLE001
            log.warning("notify.ingest_failed_dispatch_failed")
        raise


def _enqueue_scoped_insights(*, workspace_id, doc_id) -> None:
    """Publish the scoped-insight task. Goes through `core.publisher.publish`
    so the api request_id is propagated to the worker."""
    from app.core.publisher import publish

    publish(
        "worker.tasks.insights.scoped",
        str(workspace_id),
        [str(doc_id)],
    )


async def _extract_for(
    *, doc: Document, session: AsyncSession, job: IngestJob
) -> ExtractedDocument:
    job.stage = "extract"
    await session.commit()

    if doc.source_type in {"pdf", "txt", "md"}:
        if not doc.storage_path:
            raise IngestionError(f"Document {doc.id} has no storage_path")
        raw = storage.read_bytes(doc.storage_path)
        return extract_file(raw=raw, source_type=doc.source_type, title=doc.title)

    if doc.source_type in {"slack", "notion"}:
        payload = (doc.source_metadata or {}).get("payload")
        if not isinstance(payload, dict):
            raise IngestionError(f"Document {doc.id} has no source payload")
        return extract_source(source=doc.source_type, payload=payload, title=doc.title)

    raise IngestionError(f"Unknown source_type: {doc.source_type}")


async def _chunk_and_persist(
    *,
    doc: Document,
    extracted: ExtractedDocument,
    session: AsyncSession,
    job: IngestJob,
) -> list[Chunk]:
    job.stage = "chunk"
    await session.commit()

    chunks_out = chunk_document(extracted)
    if not chunks_out:
        raise IngestionError("No chunks produced from document text.")

    # Replace any existing chunks for this doc (re-ingest case).
    existing = (
        await session.execute(select(Chunk).where(Chunk.document_id == doc.id))
    ).scalars().all()
    for c in existing:
        await session.delete(c)
    await session.flush()

    persisted: list[Chunk] = []
    for c in chunks_out:
        row = Chunk(
            id=uuid4(),
            document_id=doc.id,
            chunk_index=c.chunk_index,
            text=c.text,
            text_hash=text_hash(c.text),
            token_count=c.token_count,
            heading=c.heading,
            page_number=c.page_number,
            source_timestamp=c.source_timestamp,
        )
        session.add(row)
        persisted.append(row)
    await session.flush()
    return persisted


async def _embed_and_index(
    *,
    doc: Document,
    chunks: list[Chunk],
    session: AsyncSession,
    job: IngestJob,
) -> None:
    job.stage = "embed"
    await session.commit()

    texts = [c.text for c in chunks]
    embeddings = await embed_texts(texts, session=session)

    job.stage = "index"
    await session.flush()

    # Wipe any prior vectors for this doc, then upsert fresh.
    chroma_client.delete_for_document(doc.id)
    chroma_client.upsert_chunks(
        ids=[str(c.id) for c in chunks],
        embeddings=embeddings,
        documents_text=texts,
        metadatas=[
            {
                "document_id": str(doc.id),
                "workspace_id": str(doc.workspace_id),
                "source_type": doc.source_type,
                "chunk_index": c.chunk_index,
                "heading": c.heading,
                "page_number": c.page_number,
                "source_timestamp": c.source_timestamp.isoformat() if c.source_timestamp else None,
            }
            for c in chunks
        ],
    )
    for c in chunks:
        c.embedding_id = str(c.id)
    await session.flush()
