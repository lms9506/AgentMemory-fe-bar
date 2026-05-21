"""Memory layer data types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ConversationTurnRecord:
    turn_id: int
    client_id: str
    advisor_id: str
    session_id: str
    turn_index: int
    role: str
    content: str
    ts: datetime


@dataclass(frozen=True)
class RetrievedTurn:
    """A past turn surfaced by semantic search."""

    turn_id: int
    content: str
    role: str
    score: float
    ts: datetime
