"""LangGraph definition for the wealth advisor agent."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from agent_memory.agents.nodes import (
    make_generate_node,
    make_retrieve_node,
    make_write_memory_node,
)
from agent_memory.agents.state import AdvisorAgentState
from agent_memory.memory.store import InMemoryMemoryStore, LakebaseMemoryStore, MemoryStore


def build_graph(
    model: BaseChatModel,
    memory_store: MemoryStore | None = None,
    *,
    with_memory: bool = True,
):
    """Compile the advisor agent graph.

    When `with_memory` is True, uses Lakebase unless a store is injected (tests).
    Flow: retrieve → generate → write_memory.
    """
    builder = StateGraph(AdvisorAgentState)
    store = memory_store or (LakebaseMemoryStore() if with_memory else None)

    if store is not None:
        builder.add_node("retrieve", make_retrieve_node(store))
        builder.add_node("generate", make_generate_node(model))
        builder.add_node("write_memory", make_write_memory_node(store))
        builder.add_edge(START, "retrieve")
        builder.add_edge("retrieve", "generate")
        builder.add_edge("generate", "write_memory")
        builder.add_edge("write_memory", END)
    else:
        builder.add_node("generate", make_generate_node(model))
        builder.add_edge(START, "generate")
        builder.add_edge("generate", END)

    return builder.compile()


def build_default_graph(*, with_memory: bool = True):
    """Graph using FM API credentials from the environment."""
    from agent_memory.agents.llm import build_chat_model

    return build_graph(build_chat_model(), with_memory=with_memory)


def build_test_graph(model: BaseChatModel | None = None):
    """In-memory memory + injectable fake LLM for unit tests."""
    from agent_memory.agents.llm import build_chat_model_for_tests

    return build_graph(
        model or build_chat_model_for_tests(),
        memory_store=InMemoryMemoryStore(),
        with_memory=True,
    )
