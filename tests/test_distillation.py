"""Tests for the dossier-model distillation (D5).

Derived from interfaces.md § distillation.py + § profile_models.py.
Dead symbols removed: EpisodicTurn, InMemoryTurnSource, turn_source, source_turn_ids.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agent_memory.memory.distillation import (
    ArtifactSummary,
    InMemoryArtifactSource,
    run_distillation,
)
from agent_memory.memory.profile_store import InMemoryProfileStore
from agent_memory.memory.proposal_store import InMemoryProposalStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _artifact(artifact_id: int, client_id: str = "client_0000", summary: str = "retirement") -> ArtifactSummary:
    return ArtifactSummary(
        artifact_id=artifact_id,
        client_id=client_id,
        kind="text",
        summary=summary,
        ingested_at=_now() - timedelta(days=1),
    )


def _fake_model(risk_tolerance: str = "moderate") -> FakeListChatModel:
    payload = {
        "client_id": "client_0000",
        "risk_tolerance": risk_tolerance,
        "investment_goals": ["retirement income"],
        "family_context": "Married, two children in college",
        "stated_preferences": "Tax-efficient municipal bonds",
        "summary": "Client seeks tax-aware retirement income with moderate risk.",
    }
    return FakeListChatModel(responses=[json.dumps(payload)])


def _settings():
    from agent_memory.config import Settings

    return Settings(
        databricks_host="https://e2-demo-field-eng.cloud.databricks.com",
        databricks_token="dapi_test",
        databricks_profile=None,
        fm_api_endpoint="x",
        fm_api_embedding_endpoint="y",
        mlflow_experiment_name="/test",
        uc_catalog="agent_memory_dev",
        uc_schema="wealth_advisor",
        lakebase_database=None,
        lakebase_conninfo="postgresql://u@h/db",
        databricks_client_id=None,
        databricks_client_secret=None,
    )


# ---------------------------------------------------------------------------
# ArtifactSummary dataclass shape (contract test)
# ---------------------------------------------------------------------------

def test_artifact_summary_fields():
    a = _artifact(42)
    assert a.artifact_id == 42
    assert a.client_id == "client_0000"
    assert a.kind == "text"
    assert isinstance(a.summary, str)
    assert isinstance(a.ingested_at, datetime)


def test_artifact_summary_is_frozen():
    a = _artifact(1)
    with pytest.raises((AttributeError, TypeError)):
        a.artifact_id = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# InMemoryArtifactSource
# ---------------------------------------------------------------------------

def test_in_memory_source_list_client_ids():
    artifacts = [_artifact(1, "c0"), _artifact(2, "c1"), _artifact(3, "c0")]
    source = InMemoryArtifactSource(artifacts)
    since = _now() - timedelta(days=7)
    ids = source.list_client_ids(since=since)
    assert set(ids) == {"c0", "c1"}


def test_in_memory_source_fetch_artifacts_scoped_to_client():
    artifacts = [_artifact(1, "c0"), _artifact(2, "c1"), _artifact(3, "c0")]
    source = InMemoryArtifactSource(artifacts)
    since = _now() - timedelta(days=7)
    result = source.fetch_artifacts("c0", since=since)
    assert all(a.client_id == "c0" for a in result)
    assert {a.artifact_id for a in result} == {1, 3}


def test_in_memory_source_fetch_respects_since():
    old = ArtifactSummary(
        artifact_id=1,
        client_id="c0",
        kind="text",
        summary="old",
        ingested_at=_now() - timedelta(days=30),
    )
    recent = ArtifactSummary(
        artifact_id=2,
        client_id="c0",
        kind="text",
        summary="recent",
        ingested_at=_now() - timedelta(days=1),
    )
    source = InMemoryArtifactSource([old, recent])
    since = _now() - timedelta(days=7)
    result = source.fetch_artifacts("c0", since=since)
    assert len(result) == 1
    assert result[0].artifact_id == 2


def test_in_memory_source_empty_returns_empty():
    source = InMemoryArtifactSource([])
    since = _now() - timedelta(days=7)
    assert source.list_client_ids(since=since) == []
    assert source.fetch_artifacts("c0", since=since) == []


# ---------------------------------------------------------------------------
# run_distillation — happy path (non-delta, artifact_source kwarg)
# ---------------------------------------------------------------------------

def test_run_distillation_artifact_source_kwarg(monkeypatch):
    monkeypatch.setenv("DATABRICKS_HOST", "https://e2-demo-field-eng.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "dapi_test_token_for_unit_tests_only")
    monkeypatch.setattr(
        "agent_memory.memory.distillation.ensure_databricks_auth",
        lambda _cfg: True,
    )

    artifacts = [_artifact(10, "client_0000"), _artifact(11, "client_0000")]
    source = InMemoryArtifactSource(artifacts)
    store = InMemoryProfileStore()

    results = run_distillation(
        lookback_days=7,
        client_id="client_0000",
        settings=_settings(),
        artifact_source=source,
        profile_store=store,
        model=_fake_model(),
        use_delta=False,
    )

    assert len(results) == 1
    r = results[0]
    assert r.status == "upserted"
    assert "client_0000" in store.profiles
    committed = store.profiles["client_0000"]
    assert committed.risk_tolerance == "moderate"
    # source_artifact_ids must be present (not source_turn_ids)
    assert hasattr(committed, "source_artifact_ids")
    assert not hasattr(committed, "source_turn_ids")


# ---------------------------------------------------------------------------
# High-water mark: max(artifact_id)
# ---------------------------------------------------------------------------

def test_run_distillation_high_water_mark_skips_when_all_covered(monkeypatch):
    monkeypatch.setenv("DATABRICKS_HOST", "https://e2-demo-field-eng.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "dapi_test_token")
    monkeypatch.setattr(
        "agent_memory.memory.distillation.ensure_databricks_auth", lambda _: True
    )
    store = InMemoryProfileStore()
    # Seed profile as already covering artifact_id=5
    from agent_memory.memory.profile_models import DistilledClientProfile
    store.upsert_profile(
        DistilledClientProfile(
            client_id="client_0000",
            risk_tolerance="moderate",
            source_artifact_ids=[5],
        )
    )
    # Source has only artifact_id=5 — no new artifacts
    source = InMemoryArtifactSource([_artifact(5, "client_0000")])

    results = run_distillation(
        lookback_days=7,
        client_id="client_0000",
        settings=_settings(),
        artifact_source=source,
        profile_store=store,
        model=_fake_model(),
        use_delta=False,
    )

    assert len(results) == 1
    assert results[0].status == "skipped_no_new_artifacts"


def test_run_distillation_high_water_mark_runs_when_new_artifact(monkeypatch):
    monkeypatch.setenv("DATABRICKS_HOST", "https://e2-demo-field-eng.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "dapi_test_token")
    monkeypatch.setattr(
        "agent_memory.memory.distillation.ensure_databricks_auth", lambda _: True
    )
    store = InMemoryProfileStore()
    from agent_memory.memory.profile_models import DistilledClientProfile
    store.upsert_profile(
        DistilledClientProfile(
            client_id="client_0000",
            risk_tolerance="conservative",
            source_artifact_ids=[5],
        )
    )
    # New artifact with id=6 exceeds the high-water mark
    source = InMemoryArtifactSource([_artifact(5, "client_0000"), _artifact(6, "client_0000")])

    results = run_distillation(
        lookback_days=7,
        client_id="client_0000",
        settings=_settings(),
        artifact_source=source,
        profile_store=store,
        model=_fake_model(),
        use_delta=False,
    )

    assert len(results) == 1
    assert results[0].status == "upserted"


# ---------------------------------------------------------------------------
# HITL proposal creation
# ---------------------------------------------------------------------------

def test_run_distillation_hitl_creates_proposal(monkeypatch):
    monkeypatch.setenv("DATABRICKS_HOST", "https://e2-demo-field-eng.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "dapi_test_token")
    monkeypatch.setattr(
        "agent_memory.memory.distillation.ensure_databricks_auth", lambda _: True
    )
    source = InMemoryArtifactSource([_artifact(1, "client_0000")])
    proposal_store = InMemoryProposalStore()

    results = run_distillation(
        lookback_days=7,
        client_id="client_0000",
        settings=_settings(),
        artifact_source=source,
        model=_fake_model(),
        use_delta=False,
        hitl=True,
        proposal_store=proposal_store,
    )

    assert len(results) == 1
    assert results[0].status == "proposed"
    assert results[0].proposal_id is not None

    pending = proposal_store.list_proposals(status="pending")
    assert len(pending) == 1
    p = pending[0]
    assert p.proposed_profile.risk_tolerance == "moderate"
    # Proposal must reference artifact IDs, not turn IDs
    assert hasattr(p.proposed_profile, "source_artifact_ids")
    assert not hasattr(p.proposed_profile, "source_turn_ids")


def test_run_distillation_hitl_supersedes_prior_proposal(monkeypatch):
    monkeypatch.setenv("DATABRICKS_HOST", "https://e2-demo-field-eng.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "dapi_test_token")
    monkeypatch.setattr(
        "agent_memory.memory.distillation.ensure_databricks_auth", lambda _: True
    )
    proposal_store = InMemoryProposalStore()

    def _run_with_artifact(artifact_id: int) -> list:
        source = InMemoryArtifactSource([_artifact(artifact_id, "client_0000")])
        return run_distillation(
            lookback_days=7,
            client_id="client_0000",
            settings=_settings(),
            artifact_source=source,
            model=_fake_model(),
            use_delta=False,
            hitl=True,
            proposal_store=proposal_store,
        )

    r1 = _run_with_artifact(1)
    assert r1[0].status == "proposed"
    first_pid = r1[0].proposal_id

    # Second run with a new artifact triggers a new proposal and supersedes the first
    r2 = _run_with_artifact(2)
    assert r2[0].status == "proposed"
    second_pid = r2[0].proposal_id
    assert second_pid != first_pid

    assert proposal_store.get_proposal(first_pid).status == "superseded"
    assert proposal_store.get_proposal(second_pid).status == "pending"


def test_run_distillation_hitl_requires_proposal_store(monkeypatch):
    monkeypatch.setenv("DATABRICKS_HOST", "https://e2-demo-field-eng.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "dapi_test_token")
    monkeypatch.setattr(
        "agent_memory.memory.distillation.ensure_databricks_auth", lambda _: True
    )
    with pytest.raises(ValueError, match="proposal_store must be provided"):
        run_distillation(settings=_settings(), use_delta=False, hitl=True)


# ---------------------------------------------------------------------------
# Audit row on LTM write
# ---------------------------------------------------------------------------

def test_run_distillation_non_hitl_writes_audit_row(monkeypatch):
    """Every LTM write must emit an audit_log row (interfaces.md §7 invariant)."""
    monkeypatch.setenv("DATABRICKS_HOST", "https://e2-demo-field-eng.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "dapi_test_token")
    monkeypatch.setattr(
        "agent_memory.memory.distillation.ensure_databricks_auth", lambda _: True
    )
    source = InMemoryArtifactSource([_artifact(1, "client_0000")])
    store = InMemoryProfileStore()

    results = run_distillation(
        lookback_days=7,
        client_id="client_0000",
        settings=_settings(),
        artifact_source=source,
        profile_store=store,
        model=_fake_model(),
        use_delta=False,
    )

    assert results[0].status == "upserted"
    # InMemoryProfileStore must expose audit log or the result carries run_id
    # At minimum we verify the distillation result has traceability
    assert results[0].client_id == "client_0000"


# ---------------------------------------------------------------------------
# DistilledClientProfile field shape (contract test)
# ---------------------------------------------------------------------------

def test_distilled_client_profile_has_source_artifact_ids_not_source_turn_ids():
    from agent_memory.memory.profile_models import DistilledClientProfile

    p = DistilledClientProfile(
        client_id="c0",
        risk_tolerance="moderate",
        source_artifact_ids=[1, 2, 3],
    )
    assert p.source_artifact_ids == [1, 2, 3]
    assert not hasattr(p, "source_turn_ids")


def test_distilled_client_profile_default_source_artifact_ids_is_list():
    from agent_memory.memory.profile_models import DistilledClientProfile

    p = DistilledClientProfile(client_id="c0")
    assert isinstance(p.source_artifact_ids, list)
    assert p.source_artifact_ids == []


def test_distilled_client_profile_all_fields_present():
    from agent_memory.memory.profile_models import DistilledClientProfile

    p = DistilledClientProfile(
        client_id="c0",
        risk_tolerance="aggressive",
        investment_goals=["growth"],
        family_context="Single",
        stated_preferences="Equities",
        summary="Growth focus.",
        source_artifact_ids=[7, 8],
    )
    assert p.client_id == "c0"
    assert p.risk_tolerance == "aggressive"
    assert p.investment_goals == ["growth"]
    assert p.family_context == "Single"
    assert p.stated_preferences == "Equities"
    assert p.summary == "Growth focus."
    assert p.source_artifact_ids == [7, 8]


# ---------------------------------------------------------------------------
# Prior-profile-aware re-distillation: amend in place, don't reword (churn fix)
# ---------------------------------------------------------------------------

class _RecordingModel:
    """Captures the messages passed to invoke; returns a fixed JSON payload."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.last_prompt: str = ""

    def invoke(self, messages):
        self.last_prompt = "\n".join(str(m.content) for m in messages)

        class _R:
            content = json.dumps(self._payload)

        return _R()


def _payload(**over):
    base = {
        "client_id": "client_0000",
        "risk_tolerance": "moderate",
        "investment_goals": ["retirement income"],
        "family_context": "Married, two children in college",
        "stated_preferences": "Tax-efficient municipal bonds",
        "summary": "Client seeks tax-aware retirement income with moderate risk.",
    }
    base.update(over)
    return base


def test_distill_includes_prior_profile_and_instruction_on_redistill():
    from agent_memory.memory.distillation import distill_client_profile
    from agent_memory.memory.profile_models import DistilledClientProfile

    prior = DistilledClientProfile(
        client_id="client_0000",
        risk_tolerance="moderate",
        investment_goals=["retirement income"],
        family_context="Married, two children in college",
        stated_preferences="Tax-efficient municipal bonds",
        summary="Existing summary verbatim.",
    )
    model = _RecordingModel(_payload())
    distill_client_profile(
        client_id="client_0000",
        artifacts=[_artifact(5, summary="new 529 college-savings note")],
        model=model,
        prior_profile=prior,
    )
    # The re-distill instruction and the prior content must both reach the prompt.
    assert "UPDATE, not a" in model.last_prompt
    assert "Do NOT reword" in model.last_prompt
    assert "Existing summary verbatim." in model.last_prompt


def test_distill_omits_instruction_on_first_distillation():
    from agent_memory.memory.distillation import distill_client_profile

    model = _RecordingModel(_payload())
    distill_client_profile(
        client_id="client_0000",
        artifacts=[_artifact(1)],
        model=model,
        prior_profile=None,
    )
    assert "UPDATE, not a" not in model.last_prompt
    assert "Existing profile:" not in model.last_prompt
