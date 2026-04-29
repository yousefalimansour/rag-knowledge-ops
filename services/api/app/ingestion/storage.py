"""Raw upload persistence.

Files land under `<UPLOAD_ROOT>/<workspace_id>/<doc_id>.<ext>` so traversal-safe
filenames are guaranteed and per-workspace isolation is preserved on disk.
The upload root is a docker-compose-managed shared volume so the api writes
and the worker reads from the same place.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.core.config import get_settings


def upload_root() -> Path:
    return Path(get_settings().UPLOAD_ROOT)


def storage_path_for(workspace_id: UUID, doc_id: UUID, extension: str) -> Path:
    ws_dir = upload_root() / str(workspace_id)
    ws_dir.mkdir(parents=True, exist_ok=True)
    ext = extension.lower().lstrip(".")
    return ws_dir / f"{doc_id}.{ext}"


def write_bytes(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def read_bytes(target: str | Path) -> bytes:
    return Path(target).read_bytes()
