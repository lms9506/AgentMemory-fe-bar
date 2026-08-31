"""Deterministic synthetic clients, portfolios, and dossier artifacts (D7)."""

from __future__ import annotations

import random
from datetime import datetime, timezone

from agent_memory.synthetic.models import (
    ClientProfile,
    DossierArtifact,
    DossierSeed,
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

_ADVISOR_ID = "advisor_demo_01"


def _client_id(index: int) -> str:
    return f"client_{index:04d}"


def generate_clients(*, count: int, rng: random.Random, start_index: int = 0) -> list[ClientProfile]:
    """Build `count` synthetic client profiles.

    `start_index` offsets the client-id numbering so a generated batch can avoid
    colliding with other id ranges (e.g. the hand-authored personas at 0000-0002).
    """
    clients: list[ClientProfile] = []
    for i in range(count):
        goals = list(rng.choice(_GOALS))
        clients.append(
            ClientProfile(
                client_id=_client_id(start_index + i),
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
    as_of = as_of or datetime(2026, 1, 1, tzinfo=timezone.utc)
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


# ---------------------------------------------------------------------------
# Public plain-text generators (D7).
#
# These functions return str (the plain-text content of the artifact) so
# callers that only need the text don't have to construct DossierArtifact.
#
# Pass ``seed`` for a standalone deterministic call; pass ``rng`` to share an
# existing RNG state (e.g. inside generate_artifacts).  If both are omitted a
# fresh non-seeded RNG is used.
# ---------------------------------------------------------------------------

def generate_artifact_note(
    client: ClientProfile,
    *,
    rng: random.Random | None = None,
    seed: int | None = None,
) -> str:
    """Synthetic meeting note (~300 words) for a client — returns plain text."""
    if rng is None:
        rng = random.Random(seed)
    goals = ", ".join(client.investment_goals)
    note_idx = rng.randint(1, 999)
    return (
        f"Meeting Note — {client.display_name}\n"
        f"Date: 2026-0{rng.randint(1, 6)}-{rng.randint(10, 28)}\n\n"
        f"Advisor reviewed the client's current objectives: {goals}. "
        f"Risk profile confirmed as {client.risk_tolerance}. "
        f"Family context: {client.family_context}\n\n"
        f"Key discussion points:\n"
        f"- Client expressed interest in reviewing current allocation against stated goals.\n"
        f"- Income band {client.annual_income_band}; liquid net worth band "
        f"{client.liquid_net_worth_band}.\n"
        f"- No material life changes reported since last review.\n"
        f"- Client would like a follow-up on suitability assessment before next quarter.\n\n"
        f"Action items:\n"
        f"1. Prepare a suitability summary referencing current holdings.\n"
        f"2. Review any concentration risk above 30% in a single asset class.\n"
        f"3. Flag any tax-loss harvesting opportunities before year-end.\n\n"
        f"Notes: Advisor reminded client that all recommendations are considerations only "
        f"and subject to compliance review. Client acknowledged. [ref:{note_idx}]"
    )


def generate_artifact_statement(
    client: ClientProfile,
    *,
    rng: random.Random | None = None,
    seed: int | None = None,
) -> str:
    """Synthetic brokerage statement (plain text) for a client — returns plain text."""
    if rng is None:
        rng = random.Random(seed)
    total_value = round(rng.uniform(250_000, 8_000_000), 2)
    stmt_idx = rng.randint(1, 999)
    lines = [
        f"Brokerage Statement — {client.display_name}",
        f"Account: {client.client_id.upper()}-BROK",
        f"Period ending: 2026-0{rng.randint(1, 6)}-30",
        "",
        f"Total portfolio value: ${total_value:,.2f}",
        "",
        "Holdings summary:",
    ]
    symbols = [s for s, _ in _SYMBOLS]
    rng.shuffle(symbols)
    for sym in symbols[:4]:
        value = round(total_value * rng.uniform(0.05, 0.40), 2)
        lines.append(f"  {sym:10s}  ${value:>15,.2f}")
    lines += [
        "",
        f"Risk profile on file: {client.risk_tolerance}",
        f"Investment objectives: {', '.join(client.investment_goals)}",
        "",
        "This statement is provided for informational purposes only. "
        "Past performance is not indicative of future results. "
        f"[ref:{stmt_idx}]",
    ]
    return "\n".join(lines)


def generate_artifact_doc(
    client: ClientProfile,
    *,
    rng: random.Random | None = None,
    seed: int | None = None,
) -> str:
    """Synthetic advisory questionnaire (plain text) for a client — returns plain text."""
    if rng is None:
        rng = random.Random(seed)
    doc_idx = rng.randint(1, 999)
    goals = ", ".join(client.investment_goals)
    return (
        f"Advisory Questionnaire — {client.display_name}\n"
        f"Completed: 2026-0{rng.randint(1, 6)}-{rng.randint(1, 28)}\n\n"
        f"1. Investment objectives: {goals}\n"
        f"2. Risk tolerance: {client.risk_tolerance}\n"
        f"3. Time horizon: {rng.choice(['3-5 years', '5-10 years', '10+ years'])}\n"
        f"4. Liquidity needs: "
        f"{rng.choice(['Low', 'Moderate', 'High'])} — "
        f"liquid assets in band {client.liquid_net_worth_band}\n"
        f"5. Annual income band: {client.annual_income_band}\n"
        f"6. Family situation: {client.family_context}\n"
        f"7. Prior investment experience: "
        f"{rng.choice(['Beginner', 'Intermediate', 'Experienced'])}\n"
        f"8. Ethical / ESG preferences: "
        f"{rng.choice(['None specified', 'Exclude tobacco', 'ESG preferred', 'Impact focus'])}\n\n"
        f"Client signature on file. Advisor review complete. [ref:{doc_idx}]"
    )


# ---------------------------------------------------------------------------
# Internal artifact builders — each wraps a content generator and sets the
# artifact kind / filename.  Used by generate_artifacts (round-robin).
#
# ALL synthetic artifacts hold plain-text content → kind='text' for every
# generated artifact so extract_text routes them through the plain-text path
# (not ai_parse_document, which would misroute plain text through PDF/OCR).
#
# The ``category`` field (note/statement/doc) captures what type of document
# this is — that is the dimension that legitimately varies across artifacts.
# ---------------------------------------------------------------------------

def _build_artifact_note(client: ClientProfile, rng: random.Random) -> DossierArtifact:
    content = generate_artifact_note(client, rng=rng)
    # derive a stable index from the last word of the content line for filename
    ref_idx = int(content.split("[ref:")[-1].rstrip("]")) if "[ref:" in content else 0
    return DossierArtifact(
        client_id=client.client_id,
        advisor_id=_ADVISOR_ID,
        kind="text",
        category="note",
        original_filename=f"meeting_note_{client.client_id}_{ref_idx}.txt",
        content=content,
    )


def _build_artifact_statement(client: ClientProfile, rng: random.Random) -> DossierArtifact:
    content = generate_artifact_statement(client, rng=rng)
    ref_idx = int(content.split("[ref:")[-1].rstrip("]")) if "[ref:" in content else 0
    return DossierArtifact(
        client_id=client.client_id,
        advisor_id=_ADVISOR_ID,
        kind="text",
        category="statement",
        original_filename=f"statement_{client.client_id}_{ref_idx}.txt",
        content=content,
    )


def _build_artifact_doc(client: ClientProfile, rng: random.Random) -> DossierArtifact:
    content = generate_artifact_doc(client, rng=rng)
    ref_idx = int(content.split("[ref:")[-1].rstrip("]")) if "[ref:" in content else 0
    return DossierArtifact(
        client_id=client.client_id,
        advisor_id=_ADVISOR_ID,
        kind="text",
        category="doc",
        original_filename=f"questionnaire_{client.client_id}_{ref_idx}.txt",
        content=content,
    )


def generate_artifacts(
    clients: list[ClientProfile],
    *,
    artifacts_per_client: int,
    rng: random.Random,
) -> list[DossierArtifact]:
    """Generate artifacts_per_client artifacts for each client (round-robin note/statement/doc).

    All artifacts have kind='text' (plain text, not binary) so the ingest pipeline
    routes them through the plain-text decode path rather than ai_parse_document.
    The category field (note/statement/doc) varies so any dataset with ≥2 artifacts
    per client contains ≥2 distinct categories.
    """
    _builders = [_build_artifact_note, _build_artifact_statement, _build_artifact_doc]
    artifacts: list[DossierArtifact] = []
    for client in clients:
        for i in range(artifacts_per_client):
            builder = _builders[i % len(_builders)]
            artifacts.append(builder(client, rng))
    return artifacts


def generate_dossier_seeds(
    clients: list[ClientProfile],
    *,
    artifacts_per_client: int,
    rng: random.Random,
) -> list[DossierSeed]:
    """One DossierSeed per client, each containing its generated artifacts."""
    all_artifacts = generate_artifacts(
        clients, artifacts_per_client=artifacts_per_client, rng=rng
    )
    seeds: list[DossierSeed] = []
    for client in clients:
        client_artifacts = [a for a in all_artifacts if a.client_id == client.client_id]
        seeds.append(
            DossierSeed(
                client_id=client.client_id,
                advisor_id=_ADVISOR_ID,
                artifacts=client_artifacts,
            )
        )
    return seeds


def generate_dataset(
    *,
    client_count: int = 5,
    artifacts_per_client: int = 3,
    seed: int = 42,
    start_index: int = 0,
) -> SyntheticDataset:
    """Produce a full synthetic dataset for demos and tests.

    `start_index` offsets the generated client-id range (see `generate_clients`).
    """
    rng = random.Random(seed)
    clients = generate_clients(count=client_count, rng=rng, start_index=start_index)
    artifacts = generate_artifacts(
        clients, artifacts_per_client=artifacts_per_client, rng=rng
    )
    return SyntheticDataset(
        clients=clients,
        portfolios=generate_portfolios(clients, rng),
        artifacts=artifacts,
    )
