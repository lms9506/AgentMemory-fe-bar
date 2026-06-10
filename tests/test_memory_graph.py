"""Tests for the dossier-model query graph (D1 / ADR-0003).

Contract source: interfaces.md § ArtifactStore protocol, § AdvisorAgentState.
Dead symbols removed: InMemoryMemoryStore, session_id, retrieved_turns, build_graph (graph.py).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage

from agent_memory.agents.state import AdvisorAgentState
from agent_memory.memory.models import RetrievedChunk
from agent_memory.memory.store import InMemoryArtifactStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk(chunk_id: int = 1, content: str = "retirement income") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        artifact_id=100,
        chunk_index=0,
        content=content,
        score=0.9,
        created_at=datetime.now(tz=timezone.utc),
    )


def _initial_state(client_id: str = "client_0000") -> AdvisorAgentState:
    return {
        "client_id": client_id,
        "advisor_id": "advisor_demo_01",
        "messages": [HumanMessage(content="What should we review for this client?")],
        "response": None,
        "retrieved_chunks": [],
        "agent_run_id": None,
    }


# ---------------------------------------------------------------------------
# AdvisorAgentState shape (contract tests)
# ---------------------------------------------------------------------------

def test_advisor_agent_state_has_retrieved_chunks_not_turns():
    state = _initial_state()
    assert "retrieved_chunks" in state
    assert "retrieved_turns" not in state


def test_advisor_agent_state_has_no_session_id():
    state = _initial_state()
    assert "session_id" not in state


# ---------------------------------------------------------------------------
# InMemoryArtifactStore — retrieve_chunks
# ---------------------------------------------------------------------------

def test_in_memory_store_retrieve_chunks_returns_list():
    store = InMemoryArtifactStore()
    chunks = store.retrieve_chunks(client_id="c0", query="retirement", top_k=5)
    assert isinstance(chunks, list)


def test_in_memory_store_retrieve_chunks_type():
    store = InMemoryArtifactStore()
    store.ingest_artifact(
        client_id="c0",
        advisor_id="a0",
        kind="text",
        original_filename="note.txt",
        volume_path="/vol/c0/1.txt",
        content_hash="abc123",
        extracted_text="retirement income planning",
    )
    store.write_chunks(
        artifact_id=1,
        client_id="c0",
        chunks=["retirement income planning"],
        embeddings=[[0.1] * 1024],
    )
    results = store.retrieve_chunks(client_id="c0", query="retirement", top_k=5)
    assert isinstance(results, list)
    for r in results:
        assert isinstance(r, RetrievedChunk)
        assert hasattr(r, "chunk_id")
        assert hasattr(r, "artifact_id")
        assert hasattr(r, "chunk_index")
        assert hasattr(r, "content")
        assert hasattr(r, "score")
        assert hasattr(r, "created_at")


# ---------------------------------------------------------------------------
# Query graph: retrieve → generate → END (no write-memory side effect)
# ---------------------------------------------------------------------------

def test_query_graph_returns_response():
    from agent_memory.agents.llm import build_chat_model_for_tests
    from agent_memory.agents.query_graph import build_query_graph

    store = InMemoryArtifactStore()
    graph = build_query_graph(build_chat_model_for_tests(), artifact_store=store)

    state = _initial_state()
    final = graph.invoke(state)
    assert final["response"]


def test_query_graph_populates_retrieved_chunks():
    from agent_memory.agents.llm import build_chat_model_for_tests
    from agent_memory.agents.query_graph import build_query_graph

    store = InMemoryArtifactStore()
    # Pre-seed a chunk so retrieval returns something
    store.ingest_artifact(
        client_id="client_0000",
        advisor_id="advisor_demo_01",
        kind="text",
        original_filename="note.txt",
        volume_path="/vol/client_0000/1.txt",
        content_hash="abc123",
        extracted_text="Client wants tax-efficient retirement income.",
    )
    store.write_chunks(
        artifact_id=1,
        client_id="client_0000",
        chunks=["Client wants tax-efficient retirement income."],
        embeddings=[[0.1] * 1024],
    )

    graph = build_query_graph(build_chat_model_for_tests(), artifact_store=store)
    state = _initial_state()
    final = graph.invoke(state)

    # The result state must use retrieved_chunks, not retrieved_turns
    assert "retrieved_chunks" in final
    assert "retrieved_turns" not in final


def test_query_graph_no_session_id_in_output():
    from agent_memory.agents.llm import build_chat_model_for_tests
    from agent_memory.agents.query_graph import build_query_graph

    store = InMemoryArtifactStore()
    graph = build_query_graph(build_chat_model_for_tests(), artifact_store=store)
    final = graph.invoke(_initial_state())
    assert "session_id" not in final


def test_query_graph_no_write_memory_side_effect():
    """Query graph must NOT call ingest_artifact or write_chunks (FR-10)."""
    from agent_memory.agents.llm import build_chat_model_for_tests
    from agent_memory.agents.query_graph import build_query_graph

    store = InMemoryArtifactStore()
    store.ingest_artifact = MagicMock(side_effect=AssertionError("query graph must not ingest"))
    store.write_chunks = MagicMock(side_effect=AssertionError("query graph must not write chunks"))

    graph = build_query_graph(build_chat_model_for_tests(), artifact_store=store)
    # This must complete without triggering the side-effect mocks
    final = graph.invoke(_initial_state())
    assert final["response"]


# ---------------------------------------------------------------------------
# RetrievedChunk dataclass shape (contract test)
# ---------------------------------------------------------------------------

def test_retrieved_chunk_fields():
    c = _chunk()
    assert c.chunk_id == 1
    assert c.artifact_id == 100
    assert c.chunk_index == 0
    assert isinstance(c.content, str)
    assert isinstance(c.score, float)
    assert isinstance(c.created_at, datetime)


def test_retrieved_chunk_is_frozen():
    import pytest
    c = _chunk()
    with pytest.raises((AttributeError, TypeError)):
        c.score = 0.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ArtifactRecord dataclass shape (contract test)
# ---------------------------------------------------------------------------

def test_artifact_record_fields():
    from agent_memory.memory.models import ArtifactRecord

    r = ArtifactRecord(
        artifact_id=1,
        client_id="c0",
        advisor_id="a0",
        kind="pdf",
        original_filename="doc.pdf",
        volume_path="/vol/c0/1.pdf",
        content_hash="deadbeef",
        extracted_text="some text",
        summary="a summary",
        sensitivity_tags=[],
        ingested_at=datetime.now(tz=timezone.utc),
    )
    assert r.artifact_id == 1
    assert r.kind == "pdf"
    assert not hasattr(r, "session_id")
    assert not hasattr(r, "turn_id")
    assert not hasattr(r, "turn_index")
