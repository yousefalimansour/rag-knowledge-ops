"""Heading-aware, paragraph-respecting text chunker.

Token counts are approximated as `len(text) / 4` — adequate for batching and
size guards. Exact token accounting would need the Gemini tokenizer, which
isn't published; the embedding model accepts up to ~2048 tokens per input,
so 512-token chunks (≈2048 chars) leave plenty of headroom.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from app.ingestion.types import ExtractedDocument, Section

# Defaults — translate to ≈2048 chars / chunk and ≈256 chars overlap.
DEFAULT_CHUNK_TOKENS = 512
DEFAULT_OVERLAP_TOKENS = 64
CHARS_PER_TOKEN = 4

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'])")
_WS_RE = re.compile(r"\s+")


def approx_token_count(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


@dataclass(slots=True)
class ChunkOut:
    text: str
    chunk_index: int
    heading: str | None
    page_number: int | None
    source_timestamp: datetime | None
    token_count: int


def chunk_document(
    doc: ExtractedDocument,
    *,
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[ChunkOut]:
    """Walk sections in order. Within each section, accumulate sentences into
    chunks of ≤ `chunk_tokens`. Chunks always carry their section's heading and
    page metadata. Sentences longer than the budget are split mid-sentence.
    """
    max_chars = chunk_tokens * CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN

    out: list[ChunkOut] = []
    chunk_index = 0

    for section in doc.sections:
        text = section.text.strip()
        if not text:
            continue
        sentences = _split_sentences(text)
        buf = ""
        last_tail = ""

        for sent in sentences:
            sent = _WS_RE.sub(" ", sent).strip()
            if not sent:
                continue

            # If a single sentence is too big, hard-split it.
            if len(sent) > max_chars:
                pieces = [sent[i : i + max_chars] for i in range(0, len(sent), max_chars)]
                for piece in pieces:
                    if buf:
                        out.append(_emit(chunk_index, buf, section))
                        chunk_index += 1
                        last_tail = buf[-overlap_chars:] if overlap_chars else ""
                        buf = (last_tail + " " + piece).strip() if last_tail else piece
                    else:
                        buf = piece
                continue

            candidate = (buf + " " + sent).strip() if buf else sent
            if len(candidate) <= max_chars:
                buf = candidate
            else:
                out.append(_emit(chunk_index, buf, section))
                chunk_index += 1
                last_tail = buf[-overlap_chars:] if overlap_chars else ""
                buf = (last_tail + " " + sent).strip() if last_tail else sent

        if buf.strip():
            out.append(_emit(chunk_index, buf, section))
            chunk_index += 1

    return out


def _emit(idx: int, text: str, section: Section) -> ChunkOut:
    return ChunkOut(
        text=text.strip(),
        chunk_index=idx,
        heading=section.heading,
        page_number=section.page_number,
        source_timestamp=section.source_timestamp,
        token_count=approx_token_count(text),
    )


def _split_sentences(text: str) -> list[str]:
    """Cheap sentence splitter. Falls back to paragraph splits if the text has no terminators."""
    if "." not in text and "?" not in text and "!" not in text:
        return [p for p in text.split("\n\n") if p.strip()]
    parts = _SENTENCE_SPLIT_RE.split(text)
    return [p for p in parts if p.strip()]
