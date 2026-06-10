"""Tests for synthetic data generation — dossier model.

Contract source: interfaces.md §3 (synthetic/models.py), research/brief.md §D7.
Dead symbols removed: generate_dataset (session-based), ConversationTurn, ConversationSeed,
SyntheticDataset.conversations, sessions_per_client.
"""

from __future__ import annotations

import json
from pathlib import Path

from agent_memory.synthetic import generate_dataset
from agent_memory.synthetic.models import DossierArtifact, DossierSeed

# ---------------------------------------------------------------------------
# DossierArtifact / DossierSeed / SyntheticDataset shape (contract tests)
# ---------------------------------------------------------------------------

def test_dossier_artifact_fields():
    """DossierArtifact must match the dossier model, not the session model."""
    # DossierArtifact must NOT have turn/session fields
    assert not hasattr(DossierArtifact, "turn_id")
    assert not hasattr(DossierArtifact, "session_id")


def test_dossier_seed_has_artifacts_not_conversations():
    """DossierSeed must expose artifacts, not conversations."""
    assert hasattr(DossierSeed, "__dataclass_fields__") or hasattr(DossierSeed, "model_fields")
    # Check the field name is 'artifacts' not 'conversations'
    try:
        fields = DossierSeed.model_fields  # pydantic
    except AttributeError:
        import dataclasses
        fields = {f.name for f in dataclasses.fields(DossierSeed)}

    if isinstance(fields, dict):
        assert "artifacts" in fields
        assert "conversations" not in fields
    else:
        assert "artifacts" in fields
        assert "conversations" not in fields


def test_synthetic_dataset_has_artifacts_not_conversations():
    """SyntheticDataset.artifacts must exist; SyntheticDataset.conversations must not."""
    ds = generate_dataset(client_count=1, artifacts_per_client=1, seed=42)
    assert hasattr(ds, "artifacts")
    assert not hasattr(ds, "conversations")


# ---------------------------------------------------------------------------
# generate_dataset — shape and content
# ---------------------------------------------------------------------------

def test_generate_dataset_shape():
    ds = generate_dataset(client_count=2, artifacts_per_client=3, seed=1)
    assert len(ds.clients) == 2
    assert len(ds.portfolios) == 2
    # artifacts: 2 clients x 3 artifacts = 6
    assert len(ds.artifacts) == 6
    assert ds.clients[0].client_id == "client_0000"
    assert all(c.client_id == p.client_id for c, p in zip(ds.clients, ds.portfolios, strict=True))


def test_generate_dataset_reproducible():
    a = generate_dataset(client_count=3, artifacts_per_client=2, seed=99)
    b = generate_dataset(client_count=3, artifacts_per_client=2, seed=99)
    assert a.model_dump(mode="json") == b.model_dump(mode="json")


def test_generate_dataset_different_seeds_differ():
    a = generate_dataset(client_count=2, artifacts_per_client=2, seed=1)
    b = generate_dataset(client_count=2, artifacts_per_client=2, seed=2)
    # At minimum the artifact content should differ
    assert a.model_dump(mode="json") != b.model_dump(mode="json")


def test_generate_dataset_artifact_clients_match():
    ds = generate_dataset(client_count=3, artifacts_per_client=2, seed=5)
    valid_client_ids = {c.client_id for c in ds.clients}
    for artifact in ds.artifacts:
        assert artifact.client_id in valid_client_ids


# ---------------------------------------------------------------------------
# Artifact kinds: note, statement, doc (D7)
# ---------------------------------------------------------------------------

def test_generate_artifact_note_is_plain_text():
    from agent_memory.synthetic.generator import generate_artifact_note

    client = generate_dataset(client_count=1, artifacts_per_client=1, seed=10).clients[0]
    note = generate_artifact_note(client, seed=10)
    assert isinstance(note, str)
    assert len(note) >= 50


def test_generate_artifact_statement_is_plain_text():
    from agent_memory.synthetic.generator import generate_artifact_statement

    client = generate_dataset(client_count=1, artifacts_per_client=1, seed=10).clients[0]
    stmt = generate_artifact_statement(client, seed=10)
    assert isinstance(stmt, str)
    assert len(stmt) >= 50


def test_generate_artifact_doc_is_plain_text():
    from agent_memory.synthetic.generator import generate_artifact_doc

    client = generate_dataset(client_count=1, artifacts_per_client=1, seed=10).clients[0]
    doc = generate_artifact_doc(client, seed=10)
    assert isinstance(doc, str)
    assert len(doc) >= 50


def test_generated_artifacts_are_plain_text():
    """All generated artifacts in a dataset must be plain text (no PDF/binary for D7)."""
    ds = generate_dataset(client_count=2, artifacts_per_client=3, seed=7)
    for artifact in ds.artifacts:
        assert isinstance(artifact.content, str)
        assert len(artifact.content) > 0


def test_generated_artifacts_cover_multiple_categories():
    """Generator must produce multiple artifact categories (note/statement/doc).

    All synthetic artifacts are plain text (kind='text') so they route through the
    text-decode path, not ai_parse_document; the type that varies is `category`.
    """
    ds = generate_dataset(client_count=2, artifacts_per_client=6, seed=42)
    assert {a.kind for a in ds.artifacts} == {"text"}
    categories = {a.category for a in ds.artifacts}
    assert len(categories) >= 2


# ---------------------------------------------------------------------------
# CLI writes artifacts.json (not conversations.json)
# ---------------------------------------------------------------------------

def test_cli_writes_artifacts_json(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    from agent_memory.synthetic.cli import main as cli_main

    cli_main(["--client-count", "2", "--artifacts-per-client", "2", "--seed", "1", "--output", str(tmp_path / "out")])

    output_file = tmp_path / "out" / "artifacts.json"
    assert output_file.exists(), f"Expected artifacts.json at {output_file}"

    data = json.loads(output_file.read_text())
    assert "artifacts" in data
    assert "conversations" not in data
    assert len(data["artifacts"]) == 4  # 2 clients x 2 artifacts


def test_cli_does_not_write_conversations_json(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    from agent_memory.synthetic.cli import main as cli_main

    cli_main(["--client-count", "1", "--artifacts-per-client", "1", "--seed", "1", "--output", str(tmp_path / "out")])

    conversations_file = tmp_path / "out" / "conversations.json"
    assert not conversations_file.exists()
