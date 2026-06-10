"""Pydantic models for HITL profile proposals (FR-6, M9)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from agent_memory.memory.profile_models import DistilledClientProfile

ProposalStatus = Literal["pending", "accepted", "rejected", "superseded"]


class ProfileProposal(BaseModel):
    """A machine-distilled profile pending advisor review.

    source_artifact_ids is carried on the embedded DistilledClientProfile
    (formerly source_turn_ids — renamed in profile_models.py).
    """

    proposal_id: str
    client_id: str
    proposed_profile: DistilledClientProfile
    status: ProposalStatus = "pending"
    proposed_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    run_id: str | None = None
