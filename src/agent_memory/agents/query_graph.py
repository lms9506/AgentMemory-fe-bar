"""LangGraph definition for the wealth advisor query/brainstorm agent."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from agent_memory.agents.nodes import (
    make_generate_node,
    make_retrieve_node,
)
from agent_memory.agents.state import AdvisorAgentState
from agent_memory.memory.store import ArtifactStore, InMemoryArtifactStore, LakebaseArtifactStore


def build_query_graph(
    model: BaseChatModel,
    artifact_store: ArtifactStore | None = None,
    *,
    with_memory: bool = True,
):
    """Compile the advisor query graph.

    Query surface never writes artifacts — it only retrieves and generates.
    Flow: retrieve → generate → END.
    """
    builder = StateGraph(AdvisorAgentState)
    store = artifact_store or (LakebaseArtifactStore() if with_memory else None)

    if store is not None:
        builder.add_node("retrieve", make_retrieve_node(store))
        builder.add_node("generate", make_generate_node(model))
        builder.add_edge(START, "retrieve")
        builder.add_edge("retrieve", "generate")
        builder.add_edge("generate", END)
    else:
        builder.add_node("generate", make_generate_node(model))
        builder.add_edge(START, "generate")
        builder.add_edge("generate", END)

    return builder.compile()


def build_default_graph(*, with_memory: bool = True):
    """Graph using FM API credentials from the environment."""
    from agent_memory.agents.llm import build_chat_model

    return build_query_graph(build_chat_model(), with_memory=with_memory)


def build_test_graph(model: BaseChatModel | None = None):
    """In-memory store + injectable fake LLM for unit tests."""
    from agent_memory.agents.llm import build_chat_model_for_tests

    return build_query_graph(
        model or build_chat_model_for_tests(),
        artifact_store=InMemoryArtifactStore(),
        with_memory=True,
    )
