"""Streaming advisor turns and ingest SSE events."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import mlflow
from langchain_core.messages import AIMessage, HumanMessage

from agent_memory.agents.llm import build_chat_model
from agent_memory.agents.nodes import (
    build_generation_messages,
    make_retrieve_node,
)
from agent_memory.agents.state import AdvisorAgentState
from agent_memory.config import Settings, ensure_databricks_auth, set_mlflow_experiment
from agent_memory.memory.store import LakebaseArtifactStore


def _chunk_text(chunk: object) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content) if content else ""


def stream_advisor_events(
    *,
    client_id: str,
    advisor_id: str,
    user_message: str,
    settings: Settings | None = None,
    with_memory: bool = True,
) -> Iterator[dict[str, Any]]:
    """Yield event dicts for SSE: retrieved, token, done, error."""
    cfg = settings or Settings.from_env()
    if not ensure_databricks_auth(cfg):
        yield {"type": "error", "message": f"Databricks auth failed. {cfg.auth_diagnostics()}"}
        return

    if with_memory and not cfg.lakebase_configured:
        yield {
            "type": "error",
            "message": "Lakebase not configured for memory-enabled chat.",
        }
        return

    store = LakebaseArtifactStore() if with_memory else None
    state: AdvisorAgentState = {
        "client_id": client_id,
        "advisor_id": advisor_id,
        "messages": [HumanMessage(content=user_message)],
        "response": None,
        "retrieved_chunks": [],
        "agent_run_id": None,
    }

    set_mlflow_experiment(cfg)

    try:
        with mlflow.start_run(run_name="advisor_turn_stream"):
            active = mlflow.active_run()
            agent_run_id = active.info.run_id if active is not None else None
            state["agent_run_id"] = agent_run_id
            mlflow.set_tags(
                {
                    "client_id": client_id,
                    "advisor_id": advisor_id,
                    "with_memory": str(with_memory),
                    "streaming": "true",
                }
            )

            if store is not None:
                state.update(make_retrieve_node(store)(state))
                yield {"type": "retrieved", "chunks": state.get("retrieved_chunks") or []}

            model = build_chat_model(cfg)
            messages = build_generation_messages(
                user_message=user_message,
                retrieved_chunks=state.get("retrieved_chunks"),
            )
            parts: list[str] = []
            for chunk in model.stream(messages):
                text = _chunk_text(chunk)
                if text:
                    parts.append(text)
                    yield {"type": "token", "text": text}

            response = "".join(parts)
            state["response"] = response
            state["messages"] = [
                HumanMessage(content=user_message),
                AIMessage(content=response),
            ]

            yield {
                "type": "done",
                "response": response,
                "agent_run_id": agent_run_id,
                "retrieved_chunks": state.get("retrieved_chunks") or [],
            }
    except Exception as exc:
        yield {"type": "error", "message": str(exc)}


def stream_ingest_events(
    *,
    client_id: str,
    advisor_id: str,
    original_filename: str,
    kind: str,
    raw_bytes: bytes,
    settings: Settings | None = None,
) -> Iterator[dict[str, Any]]:
    """Drive the ingest graph step-by-step and yield SSE event dicts.

    Each dict is one of IngestStepEvent | IngestDoneEvent | IngestErrorEvent shapes.
    Imported by server.py which wraps each dict in 'data: <json>\\n\\n'.
    """
    from agent_memory.agents.ingest_graph import run_ingest_graph

    yield from run_ingest_graph(
        client_id=client_id,
        advisor_id=advisor_id,
        original_filename=original_filename,
        kind=kind,
        raw_bytes=raw_bytes,
        settings=settings,
    )
