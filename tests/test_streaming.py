"""Tests for dossier-model streaming (D4, ADR-0010).

Covers:
- Chat stream: retrieved_chunks (not retrieved_turns), no session_id
- Ingest SSE: saved → extracted → embedded → summarized → (proposed?) → done event sequence
- Dedup hit: done with deduped=True, no intermediate steps
- Error event shape
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessageChunk

from agent_memory.agents.streaming import stream_advisor_events

# ---------------------------------------------------------------------------
# Chat stream: retrieved_chunks, no session_id, no write_memory
# ---------------------------------------------------------------------------

def test_chat_stream_emits_retrieved_chunks_not_turns():
    mock_store = MagicMock()
    mock_store.retrieve_chunks.return_value = []

    mock_model = MagicMock()
    mock_model.stream.return_value = [
        AIMessageChunk(content="Hello "),
        AIMessageChunk(content="there."),
    ]

    with (
        patch("agent_memory.agents.streaming.ensure_databricks_auth", return_value=True),
        patch("agent_memory.agents.streaming.LakebaseArtifactStore", return_value=mock_store),
        patch("agent_memory.agents.streaming.build_chat_model", return_value=mock_model),
        patch("agent_memory.agents.streaming.mlflow") as mock_mlflow,
    ):
        mock_run = MagicMock()
        mock_run.info.run_id = "run-id"
        mock_mlflow.start_run.return_value.__enter__.return_value = mock_run
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)
        mock_mlflow.active_run.return_value = None
        events = list(
            stream_advisor_events(
                client_id="c1",
                advisor_id="a1",
                user_message="Hi",
            )
        )

    types = [e["type"] for e in events]
    assert "retrieved" in types

    # The retrieved event must have 'chunks', not 'turns'
    retrieved_events = [e for e in events if e["type"] == "retrieved"]
    assert len(retrieved_events) >= 1
    for ev in retrieved_events:
        assert "chunks" in ev or "retrieved_chunks" in ev
        assert "turns" not in ev

    assert types.count("token") == 2
    assert events[-1]["type"] == "done"


def test_chat_stream_done_event_has_retrieved_chunks():
    mock_store = MagicMock()
    mock_store.retrieve_chunks.return_value = []

    mock_model = MagicMock()
    mock_model.stream.return_value = [AIMessageChunk(content="Done.")]

    with (
        patch("agent_memory.agents.streaming.ensure_databricks_auth", return_value=True),
        patch("agent_memory.agents.streaming.LakebaseArtifactStore", return_value=mock_store),
        patch("agent_memory.agents.streaming.build_chat_model", return_value=mock_model),
        patch("agent_memory.agents.streaming.mlflow") as mock_mlflow,
    ):
        mock_run = MagicMock()
        mock_run.info.run_id = "run-id"
        mock_mlflow.start_run.return_value.__enter__.return_value = mock_run
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)
        mock_mlflow.active_run.return_value = None
        events = list(
            stream_advisor_events(
                client_id="c1",
                advisor_id="a1",
                user_message="Hi",
            )
        )

    done = events[-1]
    assert done["type"] == "done"
    # done event must carry retrieved_chunks, not retrieved_turns
    assert "retrieved_chunks" in done
    assert "retrieved_turns" not in done


def test_chat_stream_no_session_id_in_call():
    """stream_advisor_events must not accept or require session_id."""
    import inspect
    sig = inspect.signature(stream_advisor_events)
    assert "session_id" not in sig.parameters


def test_chat_stream_no_write_memory_called():
    """Query path must never call ingest_artifact or write_chunks."""
    mock_store = MagicMock()
    mock_store.retrieve_chunks.return_value = []

    mock_model = MagicMock()
    mock_model.stream.return_value = [AIMessageChunk(content="Hi")]

    with (
        patch("agent_memory.agents.streaming.ensure_databricks_auth", return_value=True),
        patch("agent_memory.agents.streaming.LakebaseArtifactStore", return_value=mock_store),
        patch("agent_memory.agents.streaming.build_chat_model", return_value=mock_model),
        patch("agent_memory.agents.streaming.mlflow") as mock_mlflow,
    ):
        mock_run = MagicMock()
        mock_run.info.run_id = "run-id"
        mock_mlflow.start_run.return_value.__enter__.return_value = mock_run
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)
        mock_mlflow.active_run.return_value = None
        list(stream_advisor_events(client_id="c1", advisor_id="a1", user_message="Hi"))

    mock_store.ingest_artifact.assert_not_called()
    mock_store.write_chunks.assert_not_called()


# ---------------------------------------------------------------------------
# Ingest SSE event sequence (interfaces.md §6)
# ---------------------------------------------------------------------------

def _parse_sse_events(raw_text: str) -> list[dict]:
    """Parse 'data: <json>\\n\\n' SSE frames into dicts."""
    events = []
    for line in raw_text.split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            if payload:
                events.append(json.loads(payload))
    return events


def test_ingest_sse_happy_path_event_sequence():
    """Full happy path: saved → extracted → embedded → summarized → done."""
    from agent_memory.agents.streaming import stream_ingest_events
    from agent_memory.memory.store import InMemoryArtifactStore

    mock_store = InMemoryArtifactStore()
    raw_bytes = b"Hello, world. This is a plain text note."

    with (
        patch("agent_memory.agents.ingest_graph.ensure_databricks_auth", return_value=True),
        patch("agent_memory.agents.ingest_graph.mlflow") as mock_mlflow,
        patch("agent_memory.agents.ingest_graph.LakebaseArtifactStore", return_value=mock_store),
        patch("agent_memory.memory.volume_store.get_workspace_client") as mock_wc_factory,
        patch("agent_memory.memory.embeddings.embed_texts", return_value=[[0.1] * 1024]),
        patch("agent_memory.agents.llm.build_chat_model") as mock_model_factory,
    ):
        mock_wc = MagicMock()
        mock_wc.files.upload.return_value = None
        mock_wc_factory.return_value = mock_wc
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Summary of the note.")
        mock_model_factory.return_value = mock_llm
        mock_run = MagicMock()
        mock_run.info.run_id = "test-run-id"
        mock_mlflow.start_run.return_value.__enter__.return_value = mock_run
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

        raw_dicts = list(
            stream_ingest_events(
                client_id="c1",
                advisor_id="a1",
                original_filename="note.txt",
                kind="text",
                raw_bytes=raw_bytes,
            )
        )

    # stream_ingest_events delegates to run_ingest_graph which yields dicts
    events = raw_dicts
    types = [e["type"] for e in events]

    # Must have at least: step(saved), step(extracted), step(embedded), step(summarized), done
    assert "step" in types
    assert "done" in types

    step_events = [e for e in events if e["type"] == "step"]
    step_names = [e["step"] for e in step_events]

    assert "saved" in step_names
    assert "extracted" in step_names
    assert "embedded" in step_names
    assert "summarized" in step_names

    # done must come last
    assert events[-1]["type"] == "done"

    # done event must have artifact_id and deduped=False
    done = events[-1]
    assert "artifact_id" in done
    assert done["deduped"] is False


def test_ingest_sse_saved_event_has_artifact_id():
    from agent_memory.agents.streaming import stream_ingest_events
    from agent_memory.memory.store import InMemoryArtifactStore

    mock_store = InMemoryArtifactStore()

    with (
        patch("agent_memory.agents.ingest_graph.ensure_databricks_auth", return_value=True),
        patch("agent_memory.agents.ingest_graph.mlflow") as mock_mlflow,
        patch("agent_memory.agents.ingest_graph.LakebaseArtifactStore", return_value=mock_store),
        patch("agent_memory.memory.volume_store.get_workspace_client") as mock_wc_factory,
        patch("agent_memory.memory.embeddings.embed_texts", return_value=[[0.1] * 1024]),
        patch("agent_memory.agents.llm.build_chat_model") as mock_model_factory,
    ):
        mock_wc = MagicMock()
        mock_wc.files.upload.return_value = None
        mock_wc_factory.return_value = mock_wc
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Summary.")
        mock_model_factory.return_value = mock_llm
        mock_run = MagicMock()
        mock_run.info.run_id = "run-id"
        mock_mlflow.start_run.return_value.__enter__.return_value = mock_run
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

        events = list(
            stream_ingest_events(
                client_id="c1",
                advisor_id="a1",
                original_filename="note.txt",
                kind="text",
                raw_bytes=b"some text",
            )
        )

    saved_events = [e for e in events if e.get("type") == "step" and e.get("step") == "saved"]
    assert len(saved_events) >= 1
    assert saved_events[0]["artifact_id"] is not None


def test_ingest_sse_extracted_event_has_chars():
    from agent_memory.agents.streaming import stream_ingest_events
    from agent_memory.memory.store import InMemoryArtifactStore

    raw_bytes = b"This is a twenty-char note."
    mock_store = InMemoryArtifactStore()

    with (
        patch("agent_memory.agents.ingest_graph.ensure_databricks_auth", return_value=True),
        patch("agent_memory.agents.ingest_graph.mlflow") as mock_mlflow,
        patch("agent_memory.agents.ingest_graph.LakebaseArtifactStore", return_value=mock_store),
        patch("agent_memory.memory.volume_store.get_workspace_client") as mock_wc_factory,
        patch("agent_memory.memory.embeddings.embed_texts", return_value=[[0.1] * 1024]),
        patch("agent_memory.agents.llm.build_chat_model") as mock_model_factory,
    ):
        mock_wc = MagicMock()
        mock_wc.files.upload.return_value = None
        mock_wc_factory.return_value = mock_wc
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Summary.")
        mock_model_factory.return_value = mock_llm
        mock_run = MagicMock()
        mock_run.info.run_id = "run-id"
        mock_mlflow.start_run.return_value.__enter__.return_value = mock_run
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

        events = list(
            stream_ingest_events(
                client_id="c1",
                advisor_id="a1",
                original_filename="note.txt",
                kind="text",
                raw_bytes=raw_bytes,
            )
        )

    extracted_events = [e for e in events if e.get("type") == "step" and e.get("step") == "extracted"]
    assert len(extracted_events) >= 1
    assert "chars" in extracted_events[0]
    assert isinstance(extracted_events[0]["chars"], int)
    assert extracted_events[0]["chars"] > 0


def test_ingest_sse_embedded_event_has_chunks():
    from agent_memory.agents.streaming import stream_ingest_events
    from agent_memory.memory.store import InMemoryArtifactStore

    mock_store = InMemoryArtifactStore()

    with (
        patch("agent_memory.agents.ingest_graph.ensure_databricks_auth", return_value=True),
        patch("agent_memory.agents.ingest_graph.mlflow") as mock_mlflow,
        patch("agent_memory.agents.ingest_graph.LakebaseArtifactStore", return_value=mock_store),
        patch("agent_memory.memory.volume_store.get_workspace_client") as mock_wc_factory,
        patch("agent_memory.memory.embeddings.embed_texts", return_value=[[0.1] * 1024]),
        patch("agent_memory.agents.llm.build_chat_model") as mock_model_factory,
    ):
        mock_wc = MagicMock()
        mock_wc.files.upload.return_value = None
        mock_wc_factory.return_value = mock_wc
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Summary.")
        mock_model_factory.return_value = mock_llm
        mock_run = MagicMock()
        mock_run.info.run_id = "run-id"
        mock_mlflow.start_run.return_value.__enter__.return_value = mock_run
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

        events = list(
            stream_ingest_events(
                client_id="c1",
                advisor_id="a1",
                original_filename="note.txt",
                kind="text",
                raw_bytes=b"some text content for chunking",
            )
        )

    embedded_events = [e for e in events if e.get("type") == "step" and e.get("step") == "embedded"]
    assert len(embedded_events) >= 1
    assert "chunks" in embedded_events[0]
    assert isinstance(embedded_events[0]["chunks"], int)
    assert embedded_events[0]["chunks"] >= 0


def test_ingest_sse_dedup_hit_emits_done_deduped_true():
    """When content_hash matches an existing artifact, done must have deduped=True."""
    import hashlib

    from agent_memory.agents.streaming import stream_ingest_events
    from agent_memory.memory.store import InMemoryArtifactStore

    mock_store = InMemoryArtifactStore()
    raw_bytes = b"This is a duplicate document."

    # Pre-ingest the artifact so the hash already exists
    sha = hashlib.sha256(raw_bytes).hexdigest()
    mock_store.ingest_artifact(
        client_id="c1",
        advisor_id="a1",
        kind="text",
        original_filename="dup.txt",
        volume_path="/vol/c1/1.txt",
        content_hash=sha,
    )

    with (
        patch("agent_memory.agents.ingest_graph.ensure_databricks_auth", return_value=True),
        patch("agent_memory.agents.ingest_graph.mlflow") as mock_mlflow,
        patch("agent_memory.agents.ingest_graph.LakebaseArtifactStore", return_value=mock_store),
        patch("agent_memory.memory.volume_store.get_workspace_client") as mock_wc_factory,
    ):
        mock_wc = MagicMock()
        mock_wc_factory.return_value = mock_wc
        mock_run = MagicMock()
        mock_run.info.run_id = "run-id"
        mock_mlflow.start_run.return_value.__enter__.return_value = mock_run
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

        events = list(
            stream_ingest_events(
                client_id="c1",
                advisor_id="a1",
                original_filename="dup.txt",
                kind="text",
                raw_bytes=raw_bytes,
            )
        )

    # On dedup hit: done event must be present with deduped=True
    done_events = [e for e in events if e.get("type") == "done"]
    assert len(done_events) >= 1
    assert done_events[-1]["deduped"] is True


def test_ingest_sse_error_event_has_message():
    """If a node raises, the SSE stream must emit a single error event."""
    from agent_memory.agents.streaming import stream_ingest_events

    with (
        patch("agent_memory.agents.ingest_graph.ensure_databricks_auth", return_value=True),
        patch("agent_memory.agents.ingest_graph.mlflow") as mock_mlflow,
        patch("agent_memory.agents.ingest_graph.LakebaseArtifactStore") as mock_store_cls,
    ):
        mock_store = MagicMock()
        mock_store.find_by_hash.side_effect = RuntimeError("DB unreachable")
        mock_store_cls.return_value = mock_store
        mock_run = MagicMock()
        mock_run.info.run_id = "run-id"
        mock_mlflow.start_run.return_value.__enter__.return_value = mock_run
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

        events = list(
            stream_ingest_events(
                client_id="c1",
                advisor_id="a1",
                original_filename="note.txt",
                kind="text",
                raw_bytes=b"data",
            )
        )

    error_events = [e for e in events if e.get("type") == "error"]
    assert len(error_events) >= 1
    assert "message" in error_events[0]
    assert len(error_events[0]["message"]) > 0


# ---------------------------------------------------------------------------
# SSE Pydantic model shapes (contract tests — interfaces.md §4)
# ---------------------------------------------------------------------------

def test_ingest_step_event_model_fields():
    from agent_memory.ui.schemas import IngestStepEvent

    e = IngestStepEvent(step="saved", artifact_id=42)
    assert e.type == "step"
    assert e.step == "saved"
    assert e.artifact_id == 42
    assert e.chars is None
    assert e.chunks is None
    assert e.summary is None
    assert e.proposal_id is None


def test_ingest_done_event_model_fields():
    from agent_memory.ui.schemas import IngestDoneEvent

    e = IngestDoneEvent(artifact_id=1)
    assert e.type == "done"
    assert e.artifact_id == 1
    assert e.deduped is False


def test_ingest_done_event_deduped_true():
    from agent_memory.ui.schemas import IngestDoneEvent

    e = IngestDoneEvent(artifact_id=1, deduped=True)
    assert e.deduped is True


def test_ingest_error_event_model_fields():
    from agent_memory.ui.schemas import IngestErrorEvent

    e = IngestErrorEvent(message="something went wrong")
    assert e.type == "error"
    assert e.message == "something went wrong"


def test_ingest_step_event_valid_steps():
    import pytest

    from agent_memory.ui.schemas import IngestStepEvent

    valid_steps = ["saved", "extracted", "embedded", "summarized", "proposed"]
    for step in valid_steps:
        ev = IngestStepEvent(step=step)  # type: ignore[arg-type]
        assert ev.step == step

    # pydantic v2 ValidationError subclasses ValueError
    with pytest.raises(ValueError):
        IngestStepEvent(step="invalid_step")  # type: ignore[arg-type]
