"""Pydantic models for synthetic wealth-advisor demo data — dossier model (D7)."""

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


class DossierArtifact(BaseModel):
    """A single synthetic dossier artifact (plain text content) for a client.

    The ``kind`` field uses the ArtifactKind vocabulary (pdf/image/docx/text/other).
    D7 generates plain-text content only — all synthetic artifacts have kind='text'
    so extract_text routes them through the plain-text path (not ai_parse_document).

    The ``category`` field captures what TYPE of document this is: 'note' (meeting
    note), 'statement' (brokerage statement), or 'doc' (advisory questionnaire).
    This is the dimension that legitimately varies across generated artifacts.
    """

    client_id: str
    advisor_id: str
    kind: Literal["pdf", "image", "docx", "text", "other"]
    category: Literal["note", "statement", "doc"]
    original_filename: str
    content: str                   # UTF-8 plain text (the bytes that will be ingested)


class DossierSeed(BaseModel):
    """All artifacts generated for one client."""

    client_id: str
    advisor_id: str
    artifacts: list[DossierArtifact]


class SyntheticDataset(BaseModel):
    """Bundle written by the generator CLI."""

    clients: list[ClientProfile]
    portfolios: list[Portfolio]
    artifacts: list[DossierArtifact]   # was conversations
