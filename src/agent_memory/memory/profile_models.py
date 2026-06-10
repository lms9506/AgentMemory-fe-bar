"""Structured long-term client profile produced by distillation (FR-3)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RiskTolerance = Literal["conservative", "moderate", "aggressive", "unknown"]


class DistilledClientProfile(BaseModel):
    """LLM output + metadata written to UC Delta `client_profile`."""

    client_id: str
    risk_tolerance: RiskTolerance = "unknown"
    investment_goals: list[str] = Field(default_factory=list)
    family_context: str = ""
    stated_preferences: str = ""
    summary: str = ""
    source_artifact_ids: list[int] = Field(default_factory=list)   # was source_turn_ids
    distilled_at: datetime | None = None
