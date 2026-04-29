from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class Section:
    """One semantic block within a document — paragraph(s) under a heading, a single Slack thread, etc."""

    text: str
    heading: str | None = None
    page_number: int | None = None
    source_timestamp: datetime | None = None


@dataclass(slots=True)
class ExtractedDocument:
    """Output of every extractor. The chunker consumes this."""

    title: str
    source_type: str
    sections: list[Section] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n\n".join(s.text for s in self.sections if s.text.strip())
