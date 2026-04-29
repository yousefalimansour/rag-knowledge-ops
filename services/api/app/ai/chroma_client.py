"""Chroma collection bootstrap + chunk upsert/delete helpers.

The collection is created on first API start (with retry/backoff because
the vector container can be slow to come up). Embeddings are provided by
the api/worker; Chroma only stores raw vectors + metadata.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings

log = logging.getLogger("api.chroma")

_client: ClientAPI | None = None


def get_chroma_client() -> ClientAPI:
    global _client
    if _client is None:
        settings = get_settings()
        url = settings.CHROMA_URL.rstrip("/")
        scheme, host_part = url.split("://", 1)
        host, _, port = host_part.partition(":")
        _client = chromadb.HttpClient(
            host=host,
            port=int(port) if port else (443 if scheme == "https" else 8000),
            ssl=(scheme == "https"),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_collection():
    """Return the workspace-shared collection. We filter by workspace_id metadata at query time."""
    settings = get_settings()
    return get_chroma_client().get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine", "embedding_dim": settings.EMBEDDING_DIM},
    )


async def ensure_collection(retries: int = 10, backoff_seconds: float = 1.5) -> None:
    settings = get_settings()
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            client = get_chroma_client()
            client.heartbeat()
            client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION,
                metadata={"hnsw:space": "cosine", "embedding_dim": settings.EMBEDDING_DIM},
            )
            log.info(
                "chroma.collection_ready",
                extra={"collection": settings.CHROMA_COLLECTION, "attempt": attempt},
            )
            return
        except Exception as e:
            last_err = e
            log.warning(
                "chroma.bootstrap_retry",
                extra={"attempt": attempt, "error": str(e)},
            )
            await asyncio.sleep(backoff_seconds * attempt)
    log.error("chroma.bootstrap_failed", extra={"error": str(last_err)})


def upsert_chunks(
    *,
    ids: Sequence[str],
    embeddings: Sequence[Sequence[float]],
    documents_text: Sequence[str],
    metadatas: Sequence[dict[str, Any]],
) -> None:
    """Idempotent — Chroma upsert replaces by id if present."""
    if not ids:
        return
    coll = get_collection()
    coll.upsert(
        ids=list(ids),
        embeddings=[list(e) for e in embeddings],
        documents=list(documents_text),
        metadatas=[_clean_metadata(m) for m in metadatas],
    )


def delete_for_document(document_id: UUID) -> None:
    coll = get_collection()
    coll.delete(where={"document_id": str(document_id)})


def _clean_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Chroma rejects None-valued metadata; drop those keys."""
    return {k: v for k, v in meta.items() if v is not None}
