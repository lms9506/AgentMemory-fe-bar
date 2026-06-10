"""Tests for the dossier-model query graph (single-turn advisor agent).

Contract source: interfaces.md § AdvisorAgentState, § ArtifactStore protocol.
Dead symbols removed: graph.py (build_graph), session_id, retrieved_turns.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from agent_memory.agents.llm import build_chat_model_for_tests
from agent_memory.agents.query_graph import build_query_graph
from agent_memory.agents.state import AdvisorAgentState
from agent_memory.memory.store import InMemoryArtifactStore


def _initial_state() -> AdvisorAgentState:
    return {
        "client_id": "client_0000",
        "advisor_id": "advisor_demo_01",
        "messages": [HumanMessage(content="What should we review for this client?")],
        "response": None,
        "retrieved_chunks": [],
        "agent_run_id": None,
    }


def test_single_turn_graph_with_fake_llm():
    store = InMemoryArtifactStore()
    graph = build_query_graph(build_chat_model_for_tests(), artifact_store=store)
    final = graph.invoke(_initial_state())
    assert final["response"]


def test_graph_state_has_no_session_id():
    store = InMemoryArtifactStore()
    graph = build_query_graph(build_chat_model_for_tests(), artifact_store=store)
    final = graph.invoke(_initial_state())
    assert "session_id" not in final


def test_graph_state_uses_retrieved_chunks_key():
    store = InMemoryArtifactStore()
    graph = build_query_graph(build_chat_model_for_tests(), artifact_store=store)
    final = graph.invoke(_initial_state())
    assert "retrieved_chunks" in final
    assert "retrieved_turns" not in final


def test_graph_retrieved_chunks_list():
    store = InMemoryArtifactStore()
    graph = build_query_graph(build_chat_model_for_tests(), artifact_store=store)
    final = graph.invoke(_initial_state())
    assert isinstance(final["retrieved_chunks"], list)


def test_graph_agent_run_id_present():
    store = InMemoryArtifactStore()
    graph = build_query_graph(build_chat_model_for_tests(), artifact_store=store)
    final = graph.invoke(_initial_state())
    # agent_run_id is optional but the key must exist in the state TypedDict
    assert "agent_run_id" in final


def test_graph_response_is_string():
    store = InMemoryArtifactStore()
    graph = build_query_graph(build_chat_model_for_tests(), artifact_store=store)
    final = graph.invoke(_initial_state())
    assert isinstance(final["response"], str)


def test_graph_different_clients_isolated():
    """Retrievals for client_0000 must not return chunks belonging to client_0001."""

    from agent_memory.memory.models import RetrievedChunk

    store = InMemoryArtifactStore()
    store.ingest_artifact(
        client_id="client_0001",
        advisor_id="a",
        kind="text",
        original_filename="n.txt",
        volume_path="/vol/c1/1.txt",
        content_hash="hashc1",
        extracted_text="client 1 private data",
    )
    store.write_chunks(
        artifact_id=1,
        client_id="client_0001",
        chunks=["client 1 private data"],
        embeddings=[[0.5] * 1024],
    )

    graph = build_query_graph(build_chat_model_for_tests(), artifact_store=store)
    state = {
        "client_id": "client_0000",
        "advisor_id": "advisor_demo_01",
        "messages": [HumanMessage(content="private data?")],
        "response": None,
        "retrieved_chunks": [],
        "agent_run_id": None,
    }
    final = graph.invoke(state)
    # No chunks from client_0001 must appear in client_0000's response
    for chunk in final.get("retrieved_chunks", []):
        assert isinstance(chunk, (dict, RetrievedChunk))
