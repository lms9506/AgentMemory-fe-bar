"""Tests for HITL proposal store and API endpoints — dossier model.

Contract source: interfaces.md § ProposalCreator, § ProposalOut, § route list.
Dead symbols removed: source_turn_ids, latest_source_turn_id.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_memory.memory.distillation import (
    ArtifactSummary,
    InMemoryArtifactSource,
    run_distillation,
)
from agent_memory.memory.profile_models import DistilledClientProfile
from agent_memory.memory.profile_store import InMemoryProfileStore
from agent_memory.memory.proposal_models import ProfileProposal
from agent_memory.memory.proposal_store import InMemoryProposalStore
from agent_memory.ui.server import create_app

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _sample_profile(client_id: str = "client_0000") -> DistilledClientProfile:
    return DistilledClientProfile(
        client_id=client_id,
        risk_tolerance="moderate",
        investment_goals=["retirement income"],
        family_context="Married, two children",
        stated_preferences="Tax-efficient bonds",
        summary="Client seeks steady retirement income.",
        source_artifact_ids=[1, 2, 3],
    )


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


def _fake_distill_model():
    import json

    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    payload = {
        "client_id": "client_0000",
        "risk_tolerance": "moderate",
        "investment_goals": ["retirement income"],
        "family_context": "Married",
        "stated_preferences": "Municipal bonds",
        "summary": "Steady retirement income focus.",
    }
    return FakeListChatModel(responses=[json.dumps(payload)])


def _artifact(artifact_id: int, client_id: str = "client_0000") -> ArtifactSummary:
    return ArtifactSummary(
        artifact_id=artifact_id,
        client_id=client_id,
        kind="text",
        summary="retirement planning discussion",
        ingested_at=datetime.now(tz=timezone.utc) - timedelta(days=1),
    )


# ---------------------------------------------------------------------------
# InMemoryProposalStore — unit tests
# ---------------------------------------------------------------------------

def test_create_proposal_returns_uuid():
    store = InMemoryProposalStore()
    pid = store.create_proposal(_sample_profile())
    assert isinstance(pid, str) and len(pid) == 36


def test_list_proposals_pending():
    store = InMemoryProposalStore()
    pid = store.create_proposal(_sample_profile())
    proposals = store.list_proposals(status="pending")
    assert len(proposals) == 1
    assert proposals[0].proposal_id == pid
    assert proposals[0].status == "pending"


def test_create_proposal_supersedes_prior_pending():
    store = InMemoryProposalStore()
    first = store.create_proposal(_sample_profile("client_0000"))
    second = store.create_proposal(_sample_profile("client_0000"))

    assert store.get_proposal(first).status == "superseded"
    assert store.get_proposal(second).status == "pending"
    pending = store.list_proposals(status="pending", client_id="client_0000")
    assert [p.proposal_id for p in pending] == [second]


def test_create_proposal_does_not_supersede_other_clients():
    store = InMemoryProposalStore()
    a = store.create_proposal(_sample_profile("client_0000"))
    b = store.create_proposal(_sample_profile("client_0001"))

    assert store.get_proposal(a).status == "pending"
    assert store.get_proposal(b).status == "pending"


def test_list_proposals_filtered_by_client():
    store = InMemoryProposalStore()
    store.create_proposal(_sample_profile("client_0000"))
    store.create_proposal(_sample_profile("client_0001"))
    results = store.list_proposals(status="pending", client_id="client_0000")
    assert len(results) == 1
    assert results[0].client_id == "client_0000"


def test_accept_proposal_commits_to_profile_store():
    profile_store = InMemoryProfileStore()
    store = InMemoryProposalStore(profile_store=profile_store)
    pid = store.create_proposal(_sample_profile())

    store.accept_proposal(pid, reviewed_by="advisor_01")

    assert store.get_proposal(pid).status == "accepted"
    assert store.get_proposal(pid).reviewed_by == "advisor_01"
    assert "client_0000" in profile_store.profiles
    assert profile_store.profiles["client_0000"].risk_tolerance == "moderate"


def test_accept_proposal_with_overrides():
    profile_store = InMemoryProfileStore()
    store = InMemoryProposalStore(profile_store=profile_store)
    pid = store.create_proposal(_sample_profile())

    store.accept_proposal(
        pid,
        reviewed_by="advisor_01",
        overrides={"risk_tolerance": "conservative", "summary": "Edited by advisor"},
    )

    committed = profile_store.profiles["client_0000"]
    assert committed.risk_tolerance == "conservative"
    assert committed.summary == "Edited by advisor"
    assert committed.investment_goals == ["retirement income"]


def test_reject_proposal_does_not_write_profile():
    profile_store = InMemoryProfileStore()
    store = InMemoryProposalStore(profile_store=profile_store)
    pid = store.create_proposal(_sample_profile())

    store.reject_proposal(pid, reviewed_by="advisor_01")

    assert store.get_proposal(pid).status == "rejected"
    assert "client_0000" not in profile_store.profiles


def test_double_accept_raises():
    store = InMemoryProposalStore()
    pid = store.create_proposal(_sample_profile())
    store.accept_proposal(pid, reviewed_by="advisor_01")
    with pytest.raises(ValueError, match="already has status"):
        store.accept_proposal(pid, reviewed_by="advisor_01")


def test_accept_unknown_proposal_raises():
    store = InMemoryProposalStore()
    with pytest.raises(ValueError, match="not found"):
        store.accept_proposal("no-such-id", reviewed_by="advisor_01")


# ---------------------------------------------------------------------------
# source_artifact_ids (renamed from source_turn_ids)
# ---------------------------------------------------------------------------

def test_proposal_profile_has_source_artifact_ids():
    store = InMemoryProposalStore()
    pid = store.create_proposal(_sample_profile())
    proposal = store.get_proposal(pid)
    assert hasattr(proposal.proposed_profile, "source_artifact_ids")
    assert not hasattr(proposal.proposed_profile, "source_turn_ids")
    assert proposal.proposed_profile.source_artifact_ids == [1, 2, 3]


def test_latest_source_artifact_id_is_none_when_no_proposals():
    store = InMemoryProposalStore()
    assert store.latest_source_artifact_id("client_0000") is None


def test_latest_source_artifact_id_returns_max():
    store = InMemoryProposalStore()
    store.create_proposal(_sample_profile("client_0000"))  # source_artifact_ids=[1,2,3]
    result = store.latest_source_artifact_id("client_0000")
    assert result == 3


def test_latest_source_artifact_id_scoped_to_client():
    store = InMemoryProposalStore()
    store.create_proposal(_sample_profile("client_0000"))
    assert store.latest_source_artifact_id("client_0001") is None


def test_latest_source_artifact_id_method_name_not_turn():
    """ProposalCreator must expose latest_source_artifact_id, not latest_source_turn_id."""
    store = InMemoryProposalStore()
    assert hasattr(store, "latest_source_artifact_id")
    assert not hasattr(store, "latest_source_turn_id")


# ---------------------------------------------------------------------------
# Audit row on every LTM write
# ---------------------------------------------------------------------------

def test_accept_proposal_writes_audit_row():
    """Accepting a proposal is a LTM write — an audit row must be emitted (§7 invariant)."""
    profile_store = InMemoryProfileStore()
    store = InMemoryProposalStore(profile_store=profile_store)
    pid = store.create_proposal(_sample_profile())

    # The InMemoryProfileStore's upsert_profile must be called with audit kwargs
    original_upsert = profile_store.upsert_profile
    audit_calls = []

    def _spy_upsert(profile, **kwargs):
        audit_calls.append(kwargs)
        return original_upsert(profile, **kwargs)

    profile_store.upsert_profile = _spy_upsert
    store.accept_proposal(pid, reviewed_by="advisor_01")

    assert len(audit_calls) == 1
    kwargs = audit_calls[0]
    assert kwargs.get("audit_actor") == "advisor_01"
    assert kwargs.get("audit_actor_kind") in ("advisor", "agent")


# ---------------------------------------------------------------------------
# run_distillation HITL — artifact source, audit row
# ---------------------------------------------------------------------------

def test_run_distillation_hitl_writes_proposals(monkeypatch):
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
        model=_fake_distill_model(),
        use_delta=False,
        hitl=True,
        proposal_store=proposal_store,
    )

    assert len(results) == 1
    assert results[0].status == "proposed"
    assert results[0].proposal_id is not None

    pending = proposal_store.list_proposals(status="pending")
    assert len(pending) == 1
    assert pending[0].proposed_profile.risk_tolerance == "moderate"


def test_run_distillation_skips_when_no_new_artifacts(monkeypatch):
    monkeypatch.setenv("DATABRICKS_HOST", "https://e2-demo-field-eng.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "dapi_test_token")
    monkeypatch.setattr(
        "agent_memory.memory.distillation.ensure_databricks_auth", lambda _: True
    )
    proposal_store = InMemoryProposalStore()

    def _run(artifacts):
        return run_distillation(
            lookback_days=7,
            client_id="client_0000",
            settings=_settings(),
            artifact_source=InMemoryArtifactSource(artifacts),
            model=_fake_distill_model(),
            use_delta=False,
            hitl=True,
            proposal_store=proposal_store,
        )

    a1 = _artifact(1, "client_0000")
    assert _run([a1])[0].status == "proposed"
    # Same artifact again: high-water mark covers it, skip
    assert _run([a1])[0].status == "skipped_no_new_artifacts"
    assert len(proposal_store.list_proposals(status="pending")) == 1

    # New artifact id=2 triggers again
    a2 = _artifact(2, "client_0000")
    assert _run([a1, a2])[0].status == "proposed"


def test_run_distillation_hitl_requires_proposal_store(monkeypatch):
    monkeypatch.setenv("DATABRICKS_HOST", "https://e2-demo-field-eng.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "dapi_test_token")
    monkeypatch.setattr(
        "agent_memory.memory.distillation.ensure_databricks_auth", lambda _: True
    )
    with pytest.raises(ValueError, match="proposal_store must be provided"):
        run_distillation(settings=_settings(), use_delta=False, hitl=True)


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with (
        patch("agent_memory.ui.server.ensure_databricks_auth", return_value=True),
        TestClient(create_app()) as test_client,
    ):
        yield test_client


def _mock_proposal(proposal_id: str = "pid-1", status: str = "pending") -> ProfileProposal:
    return ProfileProposal(
        proposal_id=proposal_id,
        client_id="client_0000",
        proposed_profile=DistilledClientProfile(
            client_id="client_0000",
            risk_tolerance="moderate",
            investment_goals=["retirement"],
            summary="Steady income",
            source_artifact_ids=[5, 6],
        ),
        status=status,  # type: ignore[arg-type]
        proposed_at=datetime.now(tz=timezone.utc),
    )


def test_list_proposals_api(client: TestClient) -> None:
    mock_store = MagicMock()
    mock_store.list_proposals.return_value = [_mock_proposal()]
    with patch("agent_memory.ui.server.LakebaseProposalStore", return_value=mock_store):
        res = client.get("/api/proposals")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["proposal_id"] == "pid-1"
    assert data[0]["risk_tolerance"] == "moderate"
    # source_artifact_ids must be in the response, not source_turn_ids
    assert "source_artifact_ids" in data[0]
    assert "source_turn_ids" not in data[0]


def test_accept_proposal_api(client: TestClient) -> None:
    mock_store = MagicMock()
    mock_store.accept_proposal.return_value = 42
    with patch("agent_memory.ui.server.LakebaseProposalStore", return_value=mock_store):
        res = client.post(
            "/api/proposals/pid-1/accept",
            json={"reviewed_by": "advisor_01"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "accepted"
    assert body["delta_version"] == 42
    mock_store.accept_proposal.assert_called_once_with(
        "pid-1", reviewed_by="advisor_01", overrides=None
    )


def test_accept_proposal_api_with_overrides(client: TestClient) -> None:
    mock_store = MagicMock()
    mock_store.accept_proposal.return_value = 43
    with patch("agent_memory.ui.server.LakebaseProposalStore", return_value=mock_store):
        res = client.post(
            "/api/proposals/pid-1/accept",
            json={"reviewed_by": "advisor_01", "risk_tolerance": "conservative"},
        )
    assert res.status_code == 200
    _, kwargs = mock_store.accept_proposal.call_args
    assert kwargs["overrides"] == {"risk_tolerance": "conservative"}


def test_accept_proposal_api_not_found(client: TestClient) -> None:
    mock_store = MagicMock()
    mock_store.accept_proposal.side_effect = ValueError("Proposal 'x' not found")
    with patch("agent_memory.ui.server.LakebaseProposalStore", return_value=mock_store):
        res = client.post("/api/proposals/x/accept", json={"reviewed_by": "a"})
    assert res.status_code == 404


def test_reject_proposal_api(client: TestClient) -> None:
    mock_store = MagicMock()
    with patch("agent_memory.ui.server.LakebaseProposalStore", return_value=mock_store):
        res = client.post(
            "/api/proposals/pid-1/reject",
            json={"reviewed_by": "advisor_01"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "rejected"
    assert body["proposal_id"] == "pid-1"


# ---------------------------------------------------------------------------
# Manual profile edit — source_artifact_ids preserved
# ---------------------------------------------------------------------------

def test_edit_profile_api_commits_with_advisor_audit(client: TestClient) -> None:
    mock_store = MagicMock()
    mock_store.get_profile.return_value = None
    mock_store.upsert_profile.return_value = 7
    with patch("agent_memory.ui.server.DeltaProfileStore", return_value=mock_store):
        res = client.put(
            "/api/clients/client_0000/profile",
            json={
                "edited_by": "advisor_01",
                "risk_tolerance": "conservative",
                "investment_goals": ["capital preservation"],
                "family_context": "Widowed",
                "stated_preferences": "No equities",
                "summary": "Manually corrected by advisor.",
            },
        )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "committed"
    assert body["delta_version"] == 7
    _, kwargs = mock_store.upsert_profile.call_args
    assert kwargs["audit_actor"] == "advisor_01"
    assert kwargs["audit_actor_kind"] == "advisor"
    assert kwargs["audit_action"] == "manual_profile_edit"
    committed = mock_store.upsert_profile.call_args.args[0]
    assert committed.risk_tolerance == "conservative"
    assert committed.investment_goals == ["capital preservation"]


def test_edit_profile_api_preserves_source_artifact_ids(client: TestClient) -> None:
    """Manual edit must carry over existing source_artifact_ids (provenance chain)."""
    existing = _sample_profile("client_0000").model_copy(update={"source_artifact_ids": [11, 22]})
    mock_store = MagicMock()
    mock_store.get_profile.return_value = existing
    mock_store.upsert_profile.return_value = 8
    with patch("agent_memory.ui.server.DeltaProfileStore", return_value=mock_store):
        res = client.put(
            "/api/clients/client_0000/profile",
            json={"edited_by": "advisor_01", "risk_tolerance": "aggressive"},
        )
    assert res.status_code == 200
    committed = mock_store.upsert_profile.call_args.args[0]
    # Provenance must be preserved; must use source_artifact_ids, not source_turn_ids
    assert committed.source_artifact_ids == [11, 22]
    assert not hasattr(committed, "source_turn_ids")


# ---------------------------------------------------------------------------
# ProposalOut schema: source_artifact_ids (contract test)
# ---------------------------------------------------------------------------

def test_proposal_out_schema_has_source_artifact_ids():
    from agent_memory.ui.schemas import ProposalOut

    p = ProposalOut(
        proposal_id="p1",
        client_id="c0",
        status="pending",
        proposed_at=datetime.now(tz=timezone.utc),
        risk_tolerance="moderate",
        source_artifact_ids=[1, 2],
    )
    assert p.source_artifact_ids == [1, 2]
    assert not hasattr(p, "source_turn_ids")


def test_proposal_out_schema_default_source_artifact_ids():
    from agent_memory.ui.schemas import ProposalOut

    p = ProposalOut(
        proposal_id="p1",
        client_id="c0",
        status="pending",
        proposed_at=datetime.now(tz=timezone.utc),
        risk_tolerance="moderate",
    )
    assert isinstance(p.source_artifact_ids, list)
    assert p.source_artifact_ids == []
