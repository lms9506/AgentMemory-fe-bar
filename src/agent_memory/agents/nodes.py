"""LangGraph nodes for the wealth advisor agent."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent_memory.agents.prompts import WEALTH_ADVISOR_SYSTEM
from agent_memory.agents.state import AdvisorAgentState
from agent_memory.memory.store import MemoryStore


def _format_retrieved(turns: list[dict]) -> str:
    if not turns:
        return ""
    lines = ["Relevant prior conversation for this client:"]
    for t in turns:
        lines.append(f"- [{t['role']}, score={t['score']:.2f}] {t['content']}")
    return "\n".join(lines)


def _last_user_text(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = msg.content
            return content if isinstance(content, str) else str(content)
    return ""


def make_retrieve_node(store: MemoryStore):
    def retrieve(state: AdvisorAgentState) -> dict:
        query = _last_user_text(state["messages"])
        if not query:
            return {"retrieved_turns": []}
        hits = store.retrieve_similar(client_id=state["client_id"], query=query, top_k=5)
        return {
            "retrieved_turns": [
                {
                    **asdict(h),
                    "ts": h.ts.isoformat() if isinstance(h.ts, datetime) else h.ts,
                }
                for h in hits
            ]
        }

    return retrieve


def make_generate_node(model: BaseChatModel):
    def generate(state: AdvisorAgentState) -> dict:
        system = WEALTH_ADVISOR_SYSTEM
        retrieved = _format_retrieved(state.get("retrieved_turns") or [])
        if retrieved:
            system = f"{system}\n\n{retrieved}"
        messages = [SystemMessage(content=system), *state["messages"]]
        result = model.invoke(messages)
        text = result.content if isinstance(result.content, str) else str(result.content)
        return {
            "response": text,
            "messages": [AIMessage(content=text)],
        }

    return generate


def make_write_memory_node(store: MemoryStore):
    def write_memory(state: AdvisorAgentState) -> dict:
        session_id = state["session_id"]
        user_text = _last_user_text(state["messages"])
        assistant_text = state.get("response") or ""
        agent_run_id = state.get("agent_run_id")

        if user_text:
            idx = store.next_turn_index(session_id)
            store.append_turn(
                client_id=state["client_id"],
                advisor_id=state["advisor_id"],
                session_id=session_id,
                turn_index=idx,
                role="user",
                content=user_text,
                agent_run_id=agent_run_id,
            )
        if assistant_text:
            idx = store.next_turn_index(session_id)
            store.append_turn(
                client_id=state["client_id"],
                advisor_id=state["advisor_id"],
                session_id=session_id,
                turn_index=idx,
                role="assistant",
                content=assistant_text,
                agent_run_id=agent_run_id,
            )
        return {}

    return write_memory
