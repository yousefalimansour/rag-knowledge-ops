"""Embedding service for ingestion + retrieval.

Wraps `google.generativeai.embed_content` with:
- batched calls (retrieve N at a time)
- per-text caching keyed by SHA-256 + model name (in `embedding_cache` table)
- exponential backoff on transient failures (3 attempts)

The actual Gemini call is wrapped in a thin function so tests can monkeypatch
`embed_one` without touching network code.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import LLMError
from app.models import EmbeddingCache

log = logging.getLogger("api.embeddings")


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embed_one(text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """Single-text embedding via Gemini. Retried on transient failure."""
    settings = get_settings()
    if not settings.GOOGLE_API_KEY:
        raise LLMError("GOOGLE_API_KEY is not set; cannot generate embeddings.")

    import google.generativeai as genai  # local import keeps the cold-start lighter

    genai.configure(api_key=settings.GOOGLE_API_KEY)
    last_err: Exception | None = None
    # gemini-embedding-001 is 3072d native; pass output_dimensionality so we
    # always get a 768-dim vector compatible with our Chroma collection.
    kwargs: dict = {
        "model": f"models/{settings.EMBEDDING_MODEL}",
        "content": text,
        "task_type": task_type,
    }
    if settings.EMBEDDING_DIM and settings.EMBEDDING_DIM != 0:
        kwargs["output_dimensionality"] = settings.EMBEDDING_DIM
    for attempt in range(1, 4):
        try:
            res = genai.embed_content(**kwargs)
            embedding = res["embedding"] if isinstance(res, dict) else res.embedding
            if not isinstance(embedding, list) or len(embedding) != settings.EMBEDDING_DIM:
                raise LLMError(
                    f"Embedding size mismatch: expected {settings.EMBEDDING_DIM}, got "
                    f"{len(embedding) if isinstance(embedding, list) else 'unknown'}"
                )
            return [float(x) for x in embedding]
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("embed.retry", extra={"attempt": attempt, "error": str(e)})
            time.sleep(min(2 ** attempt, 8))
    raise LLMError(f"Embedding failed after retries: {last_err}")


async def embed_texts(
    texts: Sequence[str],
    *,
    session: AsyncSession,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    """Returns one embedding per input. Hits cache first; only calls Gemini for misses."""
    settings = get_settings()
    model = settings.EMBEDDING_MODEL
    hashes = [text_hash(t) for t in texts]

    # Pull cached vectors in one query.
    rows = (
        await session.execute(
            select(EmbeddingCache.text_hash, EmbeddingCache.embedding).where(
                EmbeddingCache.model == model,
                EmbeddingCache.text_hash.in_(set(hashes)),
            )
        )
    ).all()
    cached: dict[str, list[float]] = {h: list(emb) for h, emb in rows}

    out: list[list[float]] = []
    for text, h in zip(texts, hashes, strict=True):
        if h in cached:
            out.append(cached[h])
            continue
        vec = embed_one(text, task_type=task_type)
        cached[h] = vec
        session.add(EmbeddingCache(text_hash=h, model=model, embedding=vec))
        out.append(vec)

    return out
