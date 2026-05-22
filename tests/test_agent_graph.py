"""Tests for the M4 LangGraph advisor agent."""

from langchain_core.messages import HumanMessage

from agent_memory.agents.graph import build_graph
from agent_memory.agents.llm import build_chat_model_for_tests
from agent_memory.agents.state import AdvisorAgentState


def test_single_turn_graph_with_fake_llm():
    graph = build_graph(build_chat_model_for_tests(), with_memory=False)
    state: AdvisorAgentState = {
        "client_id": "client_0000",
        "advisor_id": "advisor_demo_01",
        "session_id": "session_test",
        "messages": [HumanMessage(content="What should we review for this client?")],
        "response": None,
        "retrieved_turns": [],
        "agent_run_id": None,
    }
    final = graph.invoke(state)
    assert final["response"]
    assert "risk profile" in final["response"].lower()
