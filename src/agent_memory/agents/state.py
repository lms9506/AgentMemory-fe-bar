"""LangGraph state for the wealth advisor agent."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AdvisorAgentState(TypedDict):
    """Advisor agent state including retrieved artifact chunks (dossier model)."""

    client_id: str
    advisor_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    response: str | None
    retrieved_chunks: list[dict[str, Any]]
    agent_run_id: str | None


class IngestGraphState(TypedDict):
    """State for the artifact ingest pipeline (ADR-0010)."""

    client_id: str
    advisor_id: str
    original_filename: str
    kind: str                     # ArtifactKind
    raw_bytes: bytes
    content_hash: str | None
    volume_path: str | None
    artifact_id: int | None
    extracted_text: str | None
    summary: str | None
    chunk_count: int | None
    proposal_id: str | None
    deduped: bool
    agent_run_id: str | None
    error: str | None
