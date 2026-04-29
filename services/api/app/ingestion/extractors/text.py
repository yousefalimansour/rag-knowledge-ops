from __future__ import annotations

from app.ingestion.normalize import normalize_text
from app.ingestion.types import ExtractedDocument, Section


def extract_txt(*, raw: bytes, title: str) -> ExtractedDocument:
    text = normalize_text(raw.decode("utf-8", errors="replace"))
    return ExtractedDocument(
        title=title,
        source_type="txt",
        sections=[Section(text=p) for p in _paragraphs(text)] or [Section(text=text)],
    )


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]
