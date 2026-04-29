"""Sniff a file's MIME type via `filetype` (pure-Python, no libmagic), then
delegate to the matching extractor. For source-payload ingestion (Slack,
Notion), the source kind is explicit so dispatch is straightforward.
"""

from __future__ import annotations

from typing import Any

import filetype

from app.core.errors import IngestionError
from app.ingestion.extractors.markdown import extract_markdown
from app.ingestion.extractors.notion import extract_notion
from app.ingestion.extractors.pdf import extract_pdf
from app.ingestion.extractors.slack import extract_slack
from app.ingestion.extractors.text import extract_txt
from app.ingestion.types import ExtractedDocument

ALLOWED_FILE_TYPES = {"pdf", "txt", "md"}


def sniff_source_type(*, raw: bytes, filename: str | None) -> str:
    """Returns one of {'pdf','txt','md'} or raises IngestionError.

    Trusts content sniffing over the client-supplied extension. Markdown is
    distinguished from txt only by extension, since both are plain UTF-8.
    """
    if not raw:
        raise IngestionError("Empty file.")

    kind = filetype.guess(raw)
    if kind and kind.extension == "pdf":
        return "pdf"
    if kind and kind.extension in {"txt"}:
        return _ext_or("txt", filename)

    # filetype only knows a handful of plaintext kinds. Fall back to a UTF-8
    # decode probe — if it decodes cleanly, treat as text/markdown by extension.
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise IngestionError("Unsupported binary file (only PDF, TXT, MD).") from e
    return _ext_or("txt", filename)


def _ext_or(default: str, filename: str | None) -> str:
    if filename and filename.lower().endswith((".md", ".markdown")):
        return "md"
    if filename and filename.lower().endswith(".txt"):
        return "txt"
    return default


def extract_file(*, raw: bytes, source_type: str, title: str) -> ExtractedDocument:
    if source_type == "pdf":
        return extract_pdf(raw=raw, title=title)
    if source_type == "txt":
        return extract_txt(raw=raw, title=title)
    if source_type == "md":
        return extract_markdown(raw=raw, title=title)
    raise IngestionError(f"Unsupported file source_type: {source_type}")


def extract_source(*, source: str, payload: dict[str, Any], title: str) -> ExtractedDocument:
    if source == "slack":
        return extract_slack(payload=payload, title=title)
    if source == "notion":
        return extract_notion(payload=payload, title=title)
    raise IngestionError(f"Unsupported source: {source}")
