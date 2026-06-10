"""Memory layer data types — dossier model (D1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ArtifactKind = Literal["pdf", "image", "docx", "text", "other"]


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: int
    client_id: str
    advisor_id: str
    kind: ArtifactKind
    original_filename: str
    volume_path: str
    content_hash: str
    extracted_text: str | None
    summary: str | None
    sensitivity_tags: list[str]
    ingested_at: datetime


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk surfaced by semantic search over artifact_chunks."""

    chunk_id: int
    artifact_id: int
    chunk_index: int
    content: str
    score: float
    created_at: datetime
