"""UC Volume raw-file upload/download/dedup — dossier storage triad (D2, ADR-0013)."""

from __future__ import annotations

import hashlib
import io
from typing import BinaryIO

from agent_memory.config import Settings, get_workspace_client


def content_hash(raw_bytes: bytes) -> str:
    """SHA-256 hex digest — the dedup key (ADR-0013)."""
    return hashlib.sha256(raw_bytes).hexdigest()


def build_volume_path(
    *, client_id: str, artifact_id: int, ext: str, settings: Settings | None = None
) -> str:
    """/Volumes/{catalog}/{schema}/{volume_name}/{client_id}/{artifact_id}.{ext}"""
    cfg = settings or Settings.from_env()
    volume_name = getattr(cfg, "volume_name", "dossier_raw")
    return f"/Volumes/{cfg.uc_catalog}/{cfg.uc_schema}/{volume_name}/{client_id}/{artifact_id}.{ext}"


def upload_raw(
    *, volume_path: str, raw_bytes: bytes, settings: Settings | None = None
) -> None:
    """Upload raw bytes to UC Volume as an immutable artifact.

    Uses wc.files.upload with overwrite=False — the Volume is immutable;
    a path collision indicates a bug, not a silent overwrite (ADR-0013).
    """
    cfg = settings or Settings.from_env()
    wc = get_workspace_client(cfg)
    wc.files.upload(volume_path, io.BytesIO(raw_bytes), overwrite=False)


def download_raw(*, volume_path: str, settings: Settings | None = None) -> BinaryIO:
    """Download raw bytes from UC Volume for provenance/raw route (ADR-0013).

    Returns the BinaryIO contents from wc.files.download.
    """
    cfg = settings or Settings.from_env()
    wc = get_workspace_client(cfg)
    response = wc.files.download(volume_path)
    if response.contents is None:
        raise RuntimeError(f"Volume download returned no contents for path: {volume_path!r}")
    return response.contents


def ext_for(*, kind: str, original_filename: str) -> str:
    """Map kind/filename -> canonical file extension.

    Derivation order:
    1. If ``original_filename`` has an extension, return it (lowercased).
       For well-known kinds this disambiguates e.g. .jpeg vs .jpg vs .png.
    2. Fall back to the kind-default only when there is no usable extension in
       the filename (no dot, or trailing dot).

    This means ``kind='other'`` with ``original_filename='file.xyz'`` returns
    ``'xyz'`` rather than ``'bin'``.
    """
    _KIND_DEFAULT = {
        "pdf": "pdf",
        "image": "png",
        "docx": "docx",
        "text": "txt",
        "other": "bin",
    }
    parts = original_filename.rsplit(".", 1)
    if len(parts) == 2 and parts[1]:
        return parts[1].lower()
    return _KIND_DEFAULT.get(kind, "bin")
