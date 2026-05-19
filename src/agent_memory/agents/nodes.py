"""LangGraph nodes for the wealth advisor agent."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage

from agent_memory.agents.prompts import WEALTH_ADVISOR_SYSTEM
from agent_memory.agents.state import AdvisorAgentState


def make_generate_node(model: BaseChatModel):
    """Bind an LLM to the generate node (memory retrieval/write come in M5+)."""

    def generate(state: AdvisorAgentState) -> dict:
        messages = [SystemMessage(content=WEALTH_ADVISOR_SYSTEM), *state["messages"]]
        result = model.invoke(messages)
        text = result.content if isinstance(result.content, str) else str(result.content)
        return {
            "response": text,
            "messages": [AIMessage(content=text)],
        }

    return generate
