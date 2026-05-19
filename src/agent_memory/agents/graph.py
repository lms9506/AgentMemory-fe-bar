"""LangGraph definition for the wealth advisor (M4: generate only)."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from agent_memory.agents.nodes import make_generate_node
from agent_memory.agents.state import AdvisorAgentState


def build_graph(model: BaseChatModel):
    """Compile the advisor agent graph.

    Exported as module-level `graph` for MLflow / databricks-agents packaging.
    """
    builder = StateGraph(AdvisorAgentState)
    builder.add_node("generate", make_generate_node(model))
    builder.add_edge(START, "generate")
    builder.add_edge("generate", END)
    return builder.compile()


def build_default_graph():
    """Graph using FM API credentials from the environment."""
    from agent_memory.agents.llm import build_chat_model

    return build_graph(build_chat_model())
