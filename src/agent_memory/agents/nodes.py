"""LangGraph nodes for the wealth advisor query agent."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent_memory.agents.prompts import WEALTH_ADVISOR_SYSTEM
from agent_memory.agents.state import AdvisorAgentState
from agent_memory.memory.store import ArtifactStore


def _format_retrieved(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    lines = ["Relevant passages from the client dossier:"]
    for c in chunks:
        score = c.get("score", 0.0)
        content = c.get("content", "")
        artifact_id = c.get("artifact_id", "")
        lines.append(f"- [artifact={artifact_id}, score={score:.2f}] {content}")
    return "\n".join(lines)


def _last_user_text(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = msg.content
            return content if isinstance(content, str) else str(content)
    return ""


def make_retrieve_node(store: ArtifactStore):
    def retrieve(state: AdvisorAgentState) -> dict:
        query = _last_user_text(state["messages"])
        if not query:
            return {"retrieved_chunks": []}
        hits = store.retrieve_chunks(client_id=state["client_id"], query=query, top_k=5)
        return {
            "retrieved_chunks": [
                {
                    "chunk_id": h.chunk_id,
                    "artifact_id": h.artifact_id,
                    "chunk_index": h.chunk_index,
                    "content": h.content,
                    "score": h.score,
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                }
                for h in hits
            ]
        }

    return retrieve


def build_generation_messages(
    *,
    user_message: str,
    retrieved_chunks: list[dict] | None = None,
) -> list[SystemMessage | HumanMessage]:
    """Messages for FM API generate/stream (retrieve already applied)."""
    system = WEALTH_ADVISOR_SYSTEM
    retrieved = _format_retrieved(retrieved_chunks or [])
    if retrieved:
        system = f"{system}\n\n{retrieved}"
    return [SystemMessage(content=system), HumanMessage(content=user_message)]


def make_generate_node(model: BaseChatModel):
    def generate(state: AdvisorAgentState) -> dict:
        user_text = _last_user_text(state["messages"])
        messages = build_generation_messages(
            user_message=user_text,
            retrieved_chunks=state.get("retrieved_chunks"),
        )
        result = model.invoke(messages)
        text = result.content if isinstance(result.content, str) else str(result.content)
        return {
            "response": text,
            "messages": [AIMessage(content=text)],
        }

    return generate
