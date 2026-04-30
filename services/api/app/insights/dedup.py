"""Dedup hash for insights.

Hash inputs are intentionally order-stable so the same logical insight
produced from different runs collapses on the unique constraint.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from uuid import UUID


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def dedup_hash(*, type_: str, source_chunk_ids: Iterable[UUID | str], title: str) -> str:
    sorted_ids = sorted(str(c) for c in source_chunk_ids)
    payload = f"{type_}|{','.join(sorted_ids)}|{_normalize_title(title)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
