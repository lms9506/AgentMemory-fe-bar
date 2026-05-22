"""Deterministic synthetic clients, portfolios, and conversation seeds."""

from __future__ import annotations

import random
from datetime import UTC, datetime

from agent_memory.synthetic.models import (
    ClientProfile,
    ConversationSeed,
    ConversationTurn,
    Holding,
    Portfolio,
    RiskTolerance,
    SyntheticDataset,
)

_FIRST = ("Alex", "Jordan", "Morgan", "Riley", "Casey", "Taylor", "Quinn", "Avery")
_LAST = ("Chen", "Patel", "Nguyen", "Brooks", "Santos", "Kim", "Okafor", "Walsh")
_GOALS = (
    ("retirement", "tax-efficient growth"),
    ("college funding", "capital preservation"),
    ("estate planning", "income in retirement"),
    ("business exit", "philanthropy"),
)
_FAMILY = (
    "Married, two children in high school; aging parent nearby.",
    "Single professional; supports sibling's education.",
    "Recently widowed; adult children live out of state.",
    "Domestic partner; planning first home purchase in 3 years.",
)
_INCOME = ("100k-250k", "250k-500k", "500k-1M", "1M+")
_NET_WORTH = ("250k-1M", "1M-5M", "5M-25M", "25M+")
_SYMBOLS: list[tuple[str, Holding]] = [
    ("VTI", Holding(symbol="VTI", asset_class="equity", weight_pct=45.0)),
    ("BND", Holding(symbol="BND", asset_class="bond", weight_pct=25.0)),
    ("VMFXX", Holding(symbol="VMFXX", asset_class="cash", weight_pct=10.0)),
    ("VNQ", Holding(symbol="VNQ", asset_class="alternative", weight_pct=8.0)),
    ("VXUS", Holding(symbol="VXUS", asset_class="equity", weight_pct=12.0)),
]
_RISK: list[RiskTolerance] = ["conservative", "moderate", "aggressive"]


def _client_id(index: int) -> str:
    return f"client_{index:04d}"


def generate_clients(*, count: int, rng: random.Random) -> list[ClientProfile]:
    """Build `count` synthetic client profiles."""
    clients: list[ClientProfile] = []
    for i in range(count):
        goals = list(rng.choice(_GOALS))
        clients.append(
            ClientProfile(
                client_id=_client_id(i),
                display_name=f"{rng.choice(_FIRST)} {rng.choice(_LAST)}",
                risk_tolerance=rng.choice(_RISK),
                investment_goals=goals,
                family_context=rng.choice(_FAMILY),
                annual_income_band=rng.choice(_INCOME),
                liquid_net_worth_band=rng.choice(_NET_WORTH),
            )
        )
    return clients


def generate_portfolios(
    clients: list[ClientProfile],
    rng: random.Random,
    *,
    as_of: datetime | None = None,
) -> list[Portfolio]:
    """One portfolio per client with randomized total value."""
    as_of = as_of or datetime(2026, 1, 1, tzinfo=UTC)
    portfolios: list[Portfolio] = []
    for client in clients:
        holdings = [h.model_copy() for _, h in _SYMBOLS]
        portfolios.append(
            Portfolio(
                client_id=client.client_id,
                as_of=as_of,
                holdings=holdings,
                total_value_usd=round(rng.uniform(250_000, 8_000_000), 2),
            )
        )
    return portfolios


def generate_conversations(
    clients: list[ClientProfile],
    *,
    sessions_per_client: int,
    rng: random.Random,
) -> list[ConversationSeed]:
    """Seed advisor-client transcripts referencing goals and risk profile."""
    conversations: list[ConversationSeed] = []
    for client in clients:
        for s in range(sessions_per_client):
            session_id = f"{client.client_id}_session_{s:02d}"
            goals = ", ".join(client.investment_goals)
            conversations.append(
                ConversationSeed(
                    client_id=client.client_id,
                    advisor_id="advisor_demo_01",
                    session_id=session_id,
                    turns=[
                        ConversationTurn(
                            role="user",
                            content=(
                                f"I'm reviewing {client.display_name}'s plan. "
                                f"They want {goals} with a {client.risk_tolerance} profile."
                            ),
                        ),
                        ConversationTurn(
                            role="assistant",
                            content=(
                                f"Noted. Last time we discussed {client.family_context} "
                                "and suitability constraints. I'll factor that into recommendations."
                            ),
                        ),
                    ],
                )
            )
    return conversations


def generate_dataset(
    *,
    client_count: int = 5,
    sessions_per_client: int = 2,
    seed: int = 42,
) -> SyntheticDataset:
    """Produce a full synthetic dataset for demos and tests."""
    rng = random.Random(seed)
    clients = generate_clients(count=client_count, rng=rng)
    return SyntheticDataset(
        clients=clients,
        portfolios=generate_portfolios(clients, rng),
        conversations=generate_conversations(
            clients,
            sessions_per_client=sessions_per_client,
            rng=rng,
        ),
    )
