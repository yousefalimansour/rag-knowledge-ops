"""Ingestion entry points — files (multipart) and external sources (JSON)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import current_workspace, db_session
from app.core.errors import IngestionError
from app.core.rate_limit import RateLimit, client_ip
from app.ingestion import storage
from app.ingestion.extractors import sniff_source_type
from app.models import Document, IngestJob, Workspace
from app.schemas.ingest import SourceIngestIn
from app.schemas.jobs import FilesIngestResult, JobEnqueueResult, SourceIngestResult
from app.services import dedup

log = logging.getLogger("api.ingest")
router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def _ingest_limiter() -> RateLimit:
    return RateLimit(
        name="ingest", capacity=get_settings().RATE_LIMIT_PER_MIN, window_seconds=60
    )


def _enqueue(job_id: UUID) -> None:
    """Publish the ingest task to Redis. The api container does not import
    the worker package — `app.core.publisher.publish` attaches the current
    request_id to the message headers so worker logs can be correlated.
    """
    from app.core.publisher import publish

    publish("worker.tasks.ingest.run", str(job_id))


def _ingest_dispatcher() -> object:
    """Override hook for tests. Returns a callable taking job_id (UUID) → None."""
    return _enqueue


@router.post(
    "/files",
    response_model=FilesIngestResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_files(
    request: Request,
    files: list[UploadFile] = File(...),
    workspace: Workspace = Depends(current_workspace),
    session: AsyncSession = Depends(db_session),
) -> FilesIngestResult:
    await _ingest_limiter().hit(client_ip(request))
    settings = get_settings()
    cap_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    out_jobs: list[JobEnqueueResult] = []
    enqueue = _ingest_dispatcher()

    for upload in files:
        raw = await upload.read()
        if not raw:
            raise HTTPException(status_code=400, detail=f"{upload.filename}: empty file")
        if len(raw) > cap_bytes:
            raise HTTPException(
                status_code=413, detail=f"{upload.filename}: exceeds {settings.MAX_UPLOAD_MB} MB"
            )

        original = (upload.filename or "untitled").strip() or "untitled"
        try:
            source_type = sniff_source_type(raw=raw, filename=original)
        except IngestionError as e:
            raise HTTPException(status_code=415, detail=str(e)) from e

        content_hash = dedup.hash_bytes(raw)

        existing = await dedup.find_duplicate(
            session=session, workspace_id=workspace.id, content_hash=content_hash
        )
        if existing is not None:
            out_jobs.append(
                JobEnqueueResult(
                    id=uuid4(),  # synthetic — no new job created
                    document_id=existing.id,
                    status=existing.status,
                    deduplicated=True,
                )
            )
            continue

        title = _title_from_filename(original)
        version = await dedup.next_version_for_title(
            session=session, workspace_id=workspace.id, title=title
        )

        doc_id = uuid4()
        ext = source_type
        target = storage.storage_path_for(workspace.id, doc_id, ext)
        storage.write_bytes(target, raw)

        doc = Document(
            id=doc_id,
            workspace_id=workspace.id,
            title=title,
            source_type=source_type,
            original_filename=original,
            content_hash=content_hash,
            version=version,
            status="pending",
            chunk_count=0,
            storage_path=str(target),
            source_metadata={"size_bytes": len(raw)},
        )
        session.add(doc)
        await session.flush()

        job = IngestJob(
            id=uuid4(),
            document_id=doc.id,
            workspace_id=workspace.id,
            status="queued",
            attempts=0,
            created_at=datetime.now(UTC),
        )
        session.add(job)
        await session.flush()
        try:
            await session.commit()
        except IntegrityError as e:
            await session.rollback()
            raise HTTPException(status_code=409, detail=f"Race on dedup: {e}") from e

        try:
            enqueue(job.id)  # type: ignore[misc]
        except Exception as e:  # noqa: BLE001
            log.warning("ingest.enqueue_failed", extra={"job_id": str(job.id), "error": str(e)})

        out_jobs.append(
            JobEnqueueResult(id=job.id, document_id=doc.id, status="queued", deduplicated=False)
        )

    return FilesIngestResult(jobs=out_jobs)


@router.post(
    "/source",
    response_model=SourceIngestResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_source(
    request: Request,
    payload: SourceIngestIn,
    workspace: Workspace = Depends(current_workspace),
    session: AsyncSession = Depends(db_session),
) -> SourceIngestResult:
    await _ingest_limiter().hit(client_ip(request))
    enqueue = _ingest_dispatcher()

    content_hash = dedup.hash_payload(payload.payload)

    existing = await dedup.find_duplicate(
        session=session, workspace_id=workspace.id, content_hash=content_hash
    )
    if existing is not None:
        return SourceIngestResult(
            job=JobEnqueueResult(
                id=uuid4(),
                document_id=existing.id,
                status=existing.status,
                deduplicated=True,
            )
        )

    title = payload.title.strip() or f"{payload.source} import"
    version = await dedup.next_version_for_title(
        session=session, workspace_id=workspace.id, title=title
    )

    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        workspace_id=workspace.id,
        title=title,
        source_type=payload.source,
        original_filename=None,
        content_hash=content_hash,
        version=version,
        status="pending",
        chunk_count=0,
        storage_path=None,
        source_metadata={"payload": payload.payload},
    )
    session.add(doc)
    await session.flush()

    job = IngestJob(
        id=uuid4(),
        document_id=doc.id,
        workspace_id=workspace.id,
        status="queued",
        attempts=0,
        created_at=datetime.now(UTC),
    )
    session.add(job)
    await session.commit()

    try:
        enqueue(job.id)  # type: ignore[misc]
    except Exception as e:  # noqa: BLE001
        log.warning("ingest.enqueue_failed", extra={"job_id": str(job.id), "error": str(e)})

    return SourceIngestResult(
        job=JobEnqueueResult(id=job.id, document_id=doc.id, status="queued", deduplicated=False)
    )


def _title_from_filename(name: str) -> str:
    stem = Path(name).stem
    return stem.replace("_", " ").replace("-", " ").strip() or "Untitled"
