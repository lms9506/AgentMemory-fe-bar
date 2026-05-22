"""Pydantic models for synthetic wealth-advisor demo data."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RiskTolerance = Literal["conservative", "moderate", "aggressive"]


class ClientProfile(BaseModel):
    """Synthetic client suitable for distillation demos and eval fixtures."""

    client_id: str
    display_name: str
    risk_tolerance: RiskTolerance
    investment_goals: list[str]
    family_context: str
    annual_income_band: str
    liquid_net_worth_band: str


class Holding(BaseModel):
    symbol: str
    asset_class: Literal["equity", "bond", "cash", "alternative"]
    weight_pct: float = Field(ge=0, le=100)


class Portfolio(BaseModel):
    client_id: str
    as_of: datetime
    holdings: list[Holding]
    total_value_usd: float


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ConversationSeed(BaseModel):
    """Seed transcript for episodic-memory demos and retrieval eval."""

    client_id: str
    advisor_id: str
    session_id: str
    turns: list[ConversationTurn]


class SyntheticDataset(BaseModel):
    """Bundle written by the generator CLI."""

    clients: list[ClientProfile]
    portfolios: list[Portfolio]
    conversations: list[ConversationSeed]
