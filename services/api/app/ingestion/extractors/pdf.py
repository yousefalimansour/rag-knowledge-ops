"""PDF extractor.

Uses pypdf as the fast pure-Python path; falls back to pdfminer.six if pypdf
returns empty text (scanned PDFs without OCR will still produce nothing —
that's surfaced as IngestionError upstream).
"""

from __future__ import annotations

import io

from app.core.errors import IngestionError
from app.ingestion.normalize import normalize_text
from app.ingestion.types import ExtractedDocument, Section


def extract_pdf(*, raw: bytes, title: str) -> ExtractedDocument:
    sections = _try_pypdf(raw) or _try_pdfminer(raw)
    if not sections or not any(s.text.strip() for s in sections):
        raise IngestionError(
            "No extractable text found in PDF. Scanned/image PDFs require OCR (out of scope)."
        )
    return ExtractedDocument(title=title, source_type="pdf", sections=sections)


def _try_pypdf(raw: bytes) -> list[Section]:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as e:  # pragma: no cover
        raise IngestionError(f"pypdf not installed: {e}") from e

    try:
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            raise IngestionError("Encrypted PDFs are not supported.")
        out: list[Section] = []
        for i, page in enumerate(reader.pages, start=1):
            text = normalize_text(page.extract_text() or "")
            if text:
                out.append(Section(text=text, page_number=i))
        return out
    except PdfReadError as e:
        raise IngestionError(f"Malformed PDF: {e}") from e


def _try_pdfminer(raw: bytes) -> list[Section]:
    try:
        from pdfminer.high_level import extract_text  # type: ignore
    except ImportError:
        return []
    try:
        text = normalize_text(extract_text(io.BytesIO(raw)) or "")
    except Exception:  # noqa: BLE001
        return []
    return [Section(text=text)] if text else []
