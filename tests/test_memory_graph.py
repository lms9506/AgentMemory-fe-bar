"""Tests for M5 memory-enabled agent graph."""

from langchain_core.messages import HumanMessage

from agent_memory.agents.state import AdvisorAgentState
from agent_memory.memory.store import InMemoryMemoryStore


def test_memory_graph_retrieve_write_roundtrip():
    store = InMemoryMemoryStore()
    store.append_turn(
        client_id="client_0000",
        advisor_id="advisor_demo_01",
        session_id="session_prior",
        turn_index=0,
        role="user",
        content="Client wants tax-efficient retirement income.",
        embed=False,
    )

    from agent_memory.agents.graph import build_graph
    from agent_memory.agents.llm import build_chat_model_for_tests

    graph = build_graph(build_chat_model_for_tests(), memory_store=store)

    state: AdvisorAgentState = {
        "client_id": "client_0000",
        "advisor_id": "advisor_demo_01",
        "session_id": "session_test",
        "messages": [HumanMessage(content="What did we discuss about retirement?")],
        "response": None,
        "retrieved_turns": [],
        "agent_run_id": None,
    }
    final = graph.invoke(state)
    assert final["response"]
    assert len(final.get("retrieved_turns") or []) >= 1
    assert store.next_turn_index("session_test") >= 2
