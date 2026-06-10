"""Tests for synthetic/personas.py and store.backdate_artifact (ADR-0015)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from agent_memory.memory.store import InMemoryArtifactStore
from agent_memory.synthetic.personas import PERSONAS

_EXT = {"text": ".txt", "handwritten": ".png", "pdf": ".pdf", "scan": ".jpg"}


def test_three_personas_with_unique_ids():
    assert len(PERSONAS) == 3
    ids = [p.client_id for p in PERSONAS]
    assert len(set(ids)) == 3
    assert all(p.display_name for p in PERSONAS)


def test_personas_have_rich_history():
    # The whole point of the refinement: more than the old 3 artifacts each.
    for p in PERSONAS:
        assert len(p.artifacts) >= 5


def test_personas_cover_all_input_formats():
    fmts = {a.fmt for p in PERSONAS for a in p.artifacts}
    assert {"text", "handwritten", "pdf", "scan"} <= fmts
    kinds = {a.kind for p in PERSONAS for a in p.artifacts}
    assert {"text", "image", "pdf"} <= kinds


def test_format_to_kind_mapping():
    by_fmt = {a.fmt: a.kind for p in PERSONAS for a in p.artifacts}
    assert by_fmt["handwritten"] == "image"
    assert by_fmt["scan"] == "image"
    assert by_fmt["pdf"] == "pdf"
    assert by_fmt["text"] == "text"


def test_filenames_match_client_and_format():
    for p in PERSONAS:
        for a in p.artifacts:
            fn = a.filename(p.client_id)
            assert fn.startswith(p.client_id)
            assert fn.endswith(_EXT[a.fmt])


def test_history_spans_months_and_is_in_the_past():
    for p in PERSONAS:
        days = [a.days_ago for a in p.artifacts]
        assert all(d > 0 for d in days)
        assert max(days) - min(days) >= 90  # spans at least ~3 months


def test_slugs_unique_within_each_client():
    for p in PERSONAS:
        slugs = [a.slug for a in p.artifacts]
        assert len(set(slugs)) == len(slugs)


def test_backdate_artifact_overrides_ingested_at():
    store = InMemoryArtifactStore()
    rec = store.ingest_artifact(
        client_id="client_0000",
        advisor_id="advisor_demo_01",
        kind="pdf",
        original_filename="x.pdf",
        volume_path="/Volumes/c/s/v/x.pdf",
        content_hash="hash",
    )
    past = datetime.now(tz=timezone.utc) - timedelta(days=120)
    store.backdate_artifact(artifact_id=rec.artifact_id, ingested_at=past)
    got = store.list_artifacts(client_id="client_0000")[0]
    assert got.ingested_at == past
