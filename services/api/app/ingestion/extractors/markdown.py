"""Markdown extractor that preserves heading structure as section metadata.

Each heading line opens a new section; the content under it (until the next
heading) is the section text. If the doc has no headings, paragraphs become
sections with no heading.
"""

from __future__ import annotations

import re

from app.ingestion.normalize import normalize_text
from app.ingestion.types import ExtractedDocument, Section

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def extract_markdown(*, raw: bytes, title: str) -> ExtractedDocument:
    text = normalize_text(raw.decode("utf-8", errors="replace"))
    sections = _split_by_headings(text) or [
        Section(text=p) for p in (q.strip() for q in text.split("\n\n")) if p
    ]
    if not sections:
        sections = [Section(text=text)]
    return ExtractedDocument(title=title, source_type="md", sections=sections)


def _split_by_headings(text: str) -> list[Section]:
    sections: list[Section] = []
    current_heading: str | None = None
    buf: list[str] = []

    def flush() -> None:
        body = "\n".join(buf).strip()
        if body or current_heading:
            sections.append(Section(text=body, heading=current_heading))
        buf.clear()

    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            flush()
            current_heading = m.group(2).strip()
        else:
            buf.append(line)
    flush()
    # If we collected nothing but headings, return empty so caller falls back.
    return [s for s in sections if s.text or s.heading]
