"""LangGraph state for the wealth advisor agent."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AdvisorAgentState(TypedDict):
    """Advisor agent state including retrieved memory snippets (M5+)."""

    client_id: str
    advisor_id: str
    session_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    response: str | None
    retrieved_turns: list[dict[str, Any]]
    agent_run_id: str | None
