"""Format-specific extractors. Each returns an ExtractedDocument; the dispatch
helper picks the right one by source_type."""

from app.ingestion.extractors.dispatch import (
    extract_file,
    extract_source,
    sniff_source_type,
)

__all__ = ["extract_file", "extract_source", "sniff_source_type"]
