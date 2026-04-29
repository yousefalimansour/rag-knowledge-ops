"""Notion page ingestion.

Canonical input shape (simulated):
{
  "title": "Page title",                 // optional, falls back to caller-supplied title
  "blocks": [
    {"type": "heading_1" | "heading_2" | "heading_3", "text": "..."},
    {"type": "paragraph",                "text": "..."},
    {"type": "bulleted_list_item",       "text": "..."},
    {"type": "numbered_list_item",       "text": "..."},
    {"type": "code", "text": "...", "language": "py"},
    {"type": "child_page", "title": "...", "blocks": [...]}   // recursive
  ]
}
"""

from __future__ import annotations

from typing import Any

from app.core.errors import IngestionError
from app.ingestion.normalize import normalize_text
from app.ingestion.types import ExtractedDocument, Section

HEADING_TYPES = {"heading_1", "heading_2", "heading_3"}
TEXT_TYPES = {
    "paragraph",
    "bulleted_list_item",
    "numbered_list_item",
    "to_do",
    "quote",
    "callout",
    "code",
}


def extract_notion(*, payload: dict[str, Any], title: str) -> ExtractedDocument:
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        raise IngestionError("Notion payload missing 'blocks' list.")

    title = (payload.get("title") or title or "").strip() or title
    sections = _walk(blocks, current_heading=None, depth=0)
    if not sections:
        raise IngestionError("Notion payload has no extractable blocks.")
    return ExtractedDocument(title=title, source_type="notion", sections=sections)


def _walk(blocks: list[Any], *, current_heading: str | None, depth: int) -> list[Section]:
    sections: list[Section] = []
    buf: list[str] = []

    def flush() -> None:
        body = normalize_text("\n".join(buf))
        if body:
            sections.append(Section(text=body, heading=current_heading))
        buf.clear()

    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = str(block.get("type", "")).lower()
        text = str(block.get("text", "")).strip()

        if btype in HEADING_TYPES:
            flush()
            current_heading = text or current_heading
        elif btype in TEXT_TYPES and text:
            prefix = ""
            if btype == "bulleted_list_item":
                prefix = "• "
            elif btype == "numbered_list_item":
                prefix = "- "
            elif btype == "code":
                prefix = "    "
            buf.append(prefix + text)
        elif btype == "child_page":
            flush()
            child_title = str(block.get("title", "")).strip()
            child_heading = (
                f"{current_heading} / {child_title}" if current_heading else child_title or None
            )
            child_blocks = block.get("blocks", []) or []
            sections.extend(_walk(child_blocks, current_heading=child_heading, depth=depth + 1))
        # silently skip unknown block types; preserves forward compat
    flush()
    return sections
