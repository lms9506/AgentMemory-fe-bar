"""API request/response models for the wealth advisor app (FR-7)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ArtifactKind = Literal["pdf", "image", "docx", "text", "other"]


class ArtifactOut(BaseModel):
    artifact_id: int
    client_id: str
    advisor_id: str
    kind: ArtifactKind
    original_filename: str
    volume_path: str
    content_hash: str
    summary: str | None = None
    extracted_text: str | None = None        # included on detail route; omitted/null on list
    sensitivity_tags: list[str] = Field(default_factory=list)
    contributed_to_profile: bool = False      # artifact_id ∈ profile.source_artifact_ids
    ingested_at: datetime | None = None


class RetrievedChunkOut(BaseModel):
    chunk_id: int
    artifact_id: int
    chunk_index: int
    content: str
    score: float
    created_at: str | None = None             # ISO string


class ClientProfileOut(BaseModel):
    client_id: str
    risk_tolerance: str
    investment_goals: list[str] = Field(default_factory=list)
    family_context: str = ""
    stated_preferences: str = ""
    summary: str = ""
    source_artifact_ids: list[int] = Field(default_factory=list)
    distilled_at: datetime | None = None


class ChatRequest(BaseModel):
    client_id: str = "client_0000"
    advisor_id: str = "advisor_demo_01"
    message: str
    # NO session_id


class ChatResponse(BaseModel):
    response: str
    retrieved_chunks: list[RetrievedChunkOut] = Field(default_factory=list)
    agent_run_id: str | None = None


# --- Ingest SSE event union (ADR-0010). One model per event type; serialized as JSON. ---
class IngestStepEvent(BaseModel):
    type: Literal["step"] = "step"
    step: Literal["saved", "extracted", "embedded", "summarized", "proposed"]
    artifact_id: int | None = None
    chars: int | None = None          # step='extracted'
    chunks: int | None = None         # step='embedded'
    summary: str | None = None        # step='summarized'
    proposal_id: str | None = None    # step='proposed'


class IngestDoneEvent(BaseModel):
    type: Literal["done"] = "done"
    artifact_id: int
    deduped: bool = False             # True when the upload matched an existing content_hash


class IngestErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


class HealthResponse(BaseModel):
    status: str
    lakebase_configured: bool
    databricks_app: bool
    # Storage locations, surfaced so the UI can link to where data lives.
    uc_catalog: str | None = None
    uc_schema: str | None = None
    volume_name: str | None = None
    workspace_url: str | None = None


class ClientInfo(BaseModel):
    id: str
    display_name: str


class DistillResponse(BaseModel):
    status: str
    run_id: int | None = None
    message: str = ""


class DistillRunStatus(BaseModel):
    run_id: int
    life_cycle_state: str = ""
    result_state: str | None = None
    finished: bool = False


class ProposalOut(BaseModel):
    proposal_id: str
    client_id: str
    status: str
    proposed_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    risk_tolerance: str
    investment_goals: list[str] = Field(default_factory=list)
    family_context: str = ""
    stated_preferences: str = ""
    summary: str = ""
    source_artifact_ids: list[int] = Field(default_factory=list)


class ProposalAcceptRequest(BaseModel):
    reviewed_by: str
    # Optional field-level edits applied before the Delta write (Edit-then-Accept flow).
    risk_tolerance: str | None = None
    investment_goals: list[str] | None = None
    family_context: str | None = None
    stated_preferences: str | None = None
    summary: str | None = None


class ProposalRejectRequest(BaseModel):
    reviewed_by: str


class ProposalActionResponse(BaseModel):
    status: str
    proposal_id: str
    delta_version: int | None = None


class ProfileEditRequest(BaseModel):
    """Manual (no-LLM) advisor edit committed straight to the Delta profile."""

    edited_by: str
    risk_tolerance: str
    investment_goals: list[str] = Field(default_factory=list)
    family_context: str = ""
    stated_preferences: str = ""
    summary: str = ""


class ProfileEditResponse(BaseModel):
    status: str
    client_id: str
    delta_version: int | None = None


def retrieved_chunks_from_state(chunks: list[dict[str, Any]]) -> list[RetrievedChunkOut]:
    return [
        RetrievedChunkOut(
            chunk_id=int(c["chunk_id"]),
            artifact_id=int(c["artifact_id"]),
            chunk_index=int(c["chunk_index"]),
            content=str(c["content"]),
            score=float(c.get("score", 0)),
            created_at=c.get("created_at"),
        )
        for c in chunks
    ]
