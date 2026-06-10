"""Read episodic artifacts from Lakebase, distill profiles, write to Delta (FR-3, FR-6)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from agent_memory.memory.proposal_store import ProposalCreator

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from agent_memory.agents.llm import build_chat_model
from agent_memory.config import Settings, ensure_databricks_auth
from agent_memory.memory.connection import lakebase_connection
from agent_memory.memory.profile_models import DistilledClientProfile
from agent_memory.memory.profile_store import (
    DeltaProfileStore,
    InMemoryProfileStore,
    ProfileStore,
)

_DISTILL_SYSTEM = """You are a compliance-oriented wealth-management analyst.
Given recent advisor-client artifact summaries, produce a structured client profile JSON.

Respond with ONLY valid JSON matching this schema (no markdown):
{
  "client_id": "<same as input>",
  "risk_tolerance": "conservative" | "moderate" | "aggressive" | "unknown",
  "investment_goals": ["..."],
  "family_context": "...",
  "stated_preferences": "...",
  "summary": "2-4 sentences for the advisor"
}
"""


@dataclass(frozen=True)
class ArtifactSummary:
    """Distillation input — summary, not full extracted text (cheaper)."""

    artifact_id: int
    client_id: str
    kind: str
    summary: str          # falls back to extracted_text[:N] if summary is None
    ingested_at: datetime


class ArtifactSource(Protocol):
    def list_client_ids(self, *, since: datetime) -> list[str]: ...
    def fetch_artifacts(self, client_id: str, *, since: datetime) -> list[ArtifactSummary]: ...


class LakebaseArtifactSource:
    """Queries the `artifacts` table in Lakebase."""

    _SUMMARY_FALLBACK_CHARS = 2000

    def __init__(self, settings: Settings | None = None) -> None:
        # settings accepted for forward-compatibility with callers that pass it;
        # lakebase_connection() resolves its own settings internally.
        del settings  # not stored — connection uses its own env resolution

    def list_client_ids(self, *, since: datetime) -> list[str]:
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT client_id
                FROM artifacts
                WHERE ingested_at >= %s
                ORDER BY client_id
                """,
                (since,),
            )
            return [str(row[0]) for row in cur.fetchall()]

    def fetch_artifacts(self, client_id: str, *, since: datetime) -> list[ArtifactSummary]:
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT artifact_id, client_id, kind, summary, extracted_text, ingested_at
                FROM artifacts
                WHERE client_id = %s AND ingested_at >= %s
                ORDER BY ingested_at ASC
                """,
                (client_id, since),
            )
            rows = cur.fetchall()
        results = []
        for row in rows:
            artifact_id, cid, kind, summary, extracted_text, ingested_at = row
            # Fall back to first N chars of extracted_text if summary is absent.
            effective_summary = summary or ""
            if not effective_summary and extracted_text:
                effective_summary = str(extracted_text)[: self._SUMMARY_FALLBACK_CHARS]
            results.append(
                ArtifactSummary(
                    artifact_id=int(artifact_id),
                    client_id=str(cid),
                    kind=str(kind),
                    summary=effective_summary,
                    ingested_at=ingested_at if isinstance(ingested_at, datetime)
                    else datetime.now(tz=timezone.utc),
                )
            )
        return results


class InMemoryArtifactSource:
    """Test double — wraps a list of ArtifactSummary objects."""

    def __init__(self, artifacts: list[ArtifactSummary]) -> None:
        self._artifacts = artifacts

    def list_client_ids(self, *, since: datetime) -> list[str]:
        ids = {a.client_id for a in self._artifacts if a.ingested_at >= since}
        return sorted(ids)

    def fetch_artifacts(self, client_id: str, *, since: datetime) -> list[ArtifactSummary]:
        return [
            a for a in self._artifacts
            if a.client_id == client_id and a.ingested_at >= since
        ]


def _format_artifacts_for_prompt(artifacts: list[ArtifactSummary]) -> str:
    lines = []
    for a in artifacts:
        lines.append(
            f"[artifact_id={a.artifact_id} kind={a.kind} ingested_at={a.ingested_at.date()}] "
            f"{a.summary}"
        )
    return "\n".join(lines)


# Appended to the prompt on a re-distill so the model amends the existing profile
# rather than rewriting it from scratch — keeps unchanged facts phrased identically
# so the advisor's proposal diff shows only what genuinely changed.
_REDISTILL_INSTRUCTION = """\
A profile for this client already exists (shown below). This is an UPDATE, not a \
fresh distillation. Carry the existing profile forward VERBATIM and change only what \
the new artifacts actually justify — add new goals/preferences, revise a field when an \
artifact contradicts or refines it. Do NOT reword, reorder, or rephrase content that \
has not changed. If the new artifacts add nothing material to a field, return that \
field exactly as it appears below.

Existing profile:
{prior}"""


def _format_prior_profile(profile: DistilledClientProfile) -> str:
    return json.dumps(
        {
            "risk_tolerance": profile.risk_tolerance,
            "investment_goals": profile.investment_goals,
            "family_context": profile.family_context,
            "stated_preferences": profile.stated_preferences,
            "summary": profile.summary,
        },
        indent=2,
    )


def _parse_profile_json(
    text: str, client_id: str, artifact_ids: list[int]
) -> DistilledClientProfile:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    data["client_id"] = client_id
    data["source_artifact_ids"] = artifact_ids
    return DistilledClientProfile.model_validate(data)


def distill_client_profile(
    *,
    client_id: str,
    artifacts: list[ArtifactSummary],
    model: BaseChatModel,
    prior_profile: DistilledClientProfile | None = None,
) -> DistilledClientProfile | None:
    """Return None when there is nothing to distill.

    When ``prior_profile`` is supplied (a re-distill), the model is instructed to amend
    the existing profile in place rather than rewrite it — so re-runs produce additive
    diffs instead of reworded restatements of unchanged facts.
    """
    if not artifacts:
        return None
    artifact_ids = [a.artifact_id for a in artifacts]
    prompt = (
        f"client_id: {client_id}\n\n"
        f"Artifact summaries:\n{_format_artifacts_for_prompt(artifacts)}"
    )
    if prior_profile is not None:
        prompt += "\n\n" + _REDISTILL_INSTRUCTION.format(
            prior=_format_prior_profile(prior_profile)
        )
    result = model.invoke(
        [SystemMessage(content=_DISTILL_SYSTEM), HumanMessage(content=prompt)]
    )
    text = result.content if isinstance(result.content, str) else str(result.content)
    profile = _parse_profile_json(text, client_id, artifact_ids)
    return profile.model_copy(update={"distilled_at": datetime.now(tz=timezone.utc)})


@dataclass
class DistillationResult:
    client_id: str
    status: str
    delta_version: int | None = None
    proposal_id: str | None = None
    error: str | None = None


def _last_distilled_artifact_id(
    client_id: str,
    *,
    hitl: bool,
    proposal_store: ProposalCreator | None,
    store: ProfileStore,
) -> int | None:
    """High-water mark of artifact_ids already distilled for a client.

    In HITL mode the answer lives in prior proposals — the nightly job never commits
    to Delta, so the committed profile would be a stale signal until an advisor accepts.
    In direct-Delta mode the committed profile carries the artifact_ids it was built from.
    """
    if hitl and proposal_store is not None:
        return proposal_store.latest_source_artifact_id(client_id)
    profile = store.get_profile(client_id)
    if profile and profile.source_artifact_ids:
        return max(profile.source_artifact_ids)
    return None


def run_distillation(
    *,
    lookback_days: int = 7,
    client_id: str | None = None,
    settings: Settings | None = None,
    artifact_source: ArtifactSource | None = None,   # was: turn_source
    profile_store: ProfileStore | None = None,
    model: BaseChatModel | None = None,
    use_delta: bool = True,
    hitl: bool = False,
    proposal_store: ProposalCreator | None = None,
    mlflow_run_id: str | None = None,
) -> list[DistillationResult]:
    """Distill recent episodic memory into UC Delta profiles for all active clients.

    When hitl=True, writes pending proposals to Lakebase instead of committing to Delta.
    The proposal_store arg must be supplied when hitl=True.
    """
    cfg = settings or Settings.from_env()
    if not ensure_databricks_auth(cfg):
        raise RuntimeError(f"Databricks auth failed. {cfg.auth_diagnostics()}")
    if use_delta and not cfg.lakebase_configured:
        raise RuntimeError("Lakebase required for distillation audit log and artifact reads.")
    if hitl and proposal_store is None:
        raise ValueError("proposal_store must be provided when hitl=True")

    since = datetime.now(tz=timezone.utc) - timedelta(days=lookback_days)
    source = artifact_source or LakebaseArtifactSource()
    store = profile_store or (DeltaProfileStore(cfg) if use_delta else InMemoryProfileStore())
    llm = model or build_chat_model(cfg)

    client_ids = [client_id] if client_id else source.list_client_ids(since=since)
    results: list[DistillationResult] = []

    for cid in client_ids:
        try:
            artifacts = source.fetch_artifacts(cid, since=since)
            if not artifacts:
                results.append(
                    DistillationResult(client_id=cid, status="skipped_no_artifacts")
                )
                continue
            # Only distill when new artifacts have landed since the last run. artifact_id
            # is a monotonic BIGSERIAL — its max is a clean high-water mark of "what we've
            # already seen".
            latest_artifact_id = max(a.artifact_id for a in artifacts)
            already = _last_distilled_artifact_id(
                cid, hitl=hitl, proposal_store=proposal_store, store=store
            )
            if already is not None and latest_artifact_id <= already:
                results.append(
                    DistillationResult(client_id=cid, status="skipped_no_new_artifacts")
                )
                continue
            # On a re-distill, feed the committed profile back in so the model amends it
            # rather than rephrasing unchanged facts (only relevant when one already exists).
            prior_profile = store.get_profile(cid) if already is not None else None
            profile = distill_client_profile(
                client_id=cid, artifacts=artifacts, model=llm, prior_profile=prior_profile
            )
            if profile is None:
                results.append(DistillationResult(client_id=cid, status="skipped_empty"))
                continue
            if hitl and proposal_store is not None:
                pid = proposal_store.create_proposal(profile, run_id=mlflow_run_id)
                results.append(
                    DistillationResult(client_id=cid, status="proposed", proposal_id=pid)
                )
            else:
                version = store.upsert_profile(profile)
                results.append(
                    DistillationResult(client_id=cid, status="upserted", delta_version=version)
                )
        except Exception as exc:
            results.append(
                DistillationResult(client_id=cid, status="error", error=str(exc))
            )
    return results
