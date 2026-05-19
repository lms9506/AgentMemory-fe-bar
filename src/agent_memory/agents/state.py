"""LangGraph state for the wealth advisor agent."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AdvisorAgentState(TypedDict):
    """Minimal state for M4 (single-turn, no persisted memory yet)."""

    client_id: str
    advisor_id: str
    session_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    response: str | None
