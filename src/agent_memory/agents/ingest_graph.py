"""LangGraph ingest pipeline: raw_save → extract → chunk_embed → summarize → maybe_propose."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any, get_args

import mlflow
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from agent_memory.agents.state import IngestGraphState
from agent_memory.config import Settings, ensure_databricks_auth, set_mlflow_experiment

# Module-level imports so tests can patch these names with mock.patch.
# WorkspaceClient construction is deferred to call time (inside node closures)
# so this module is safe to import in offline/test environments.
from agent_memory.memory.models import ArtifactKind
from agent_memory.memory.store import LakebaseArtifactStore
from agent_memory.memory.volume_store import (
    build_volume_path,
    ext_for,
    upload_raw,
)
from agent_memory.memory.volume_store import (
    content_hash as compute_hash,
)

_LOG = logging.getLogger(__name__)

_ARTIFACT_KIND_VALUES = get_args(ArtifactKind)


def _coerce_kind(raw: str) -> ArtifactKind:
    """Narrow an incoming str to the ArtifactKind literal; unknown values fall back to 'other'."""
    if raw in _ARTIFACT_KIND_VALUES:
        return raw  # type: ignore[return-value]
    return "other"

# ---------------------------------------------------------------------------
# Node factories
# ---------------------------------------------------------------------------

def _make_raw_save_node(settings: Settings):
    """Hash → dedup check → ingest_artifact row → Volume upload."""
    store = LakebaseArtifactStore()

    def raw_save(state: IngestGraphState) -> dict:
        raw = state["raw_bytes"]
        chash = compute_hash(raw)
        kind = _coerce_kind(state["kind"])

        existing = store.find_by_hash(client_id=state["client_id"], content_hash=chash)
        if existing is not None:
            return {
                "content_hash": chash,
                "artifact_id": existing.artifact_id,
                "volume_path": existing.volume_path,
                "deduped": True,
            }

        record = store.ingest_artifact(
            client_id=state["client_id"],
            advisor_id=state["advisor_id"],
            kind=kind,
            original_filename=state["original_filename"],
            volume_path="",
            content_hash=chash,
            agent_run_id=state.get("agent_run_id"),
        )
        ext = ext_for(kind=state["kind"], original_filename=state["original_filename"])
        vpath = build_volume_path(
            client_id=state["client_id"],
            artifact_id=record.artifact_id,
            ext=ext,
            settings=settings,
        )
        upload_raw(volume_path=vpath, raw_bytes=raw, settings=settings)
        # Persist where the bytes landed (the row was inserted with an empty
        # volume_path because the path embeds the freshly-minted artifact_id).
        store.update_volume_path(artifact_id=record.artifact_id, volume_path=vpath)
        # extracted_text is patched later by update_artifact_text in the extract node.

        return {
            "content_hash": chash,
            "artifact_id": record.artifact_id,
            "volume_path": vpath,
            "deduped": False,
        }

    return raw_save


def _make_extract_node(settings: Settings):
    from agent_memory.memory.extraction import extract_text

    store = LakebaseArtifactStore()

    def extract(state: IngestGraphState) -> dict:
        volume_path = state["volume_path"]
        assert volume_path is not None, "volume_path must be set after raw_save"
        artifact_id = state["artifact_id"]
        assert artifact_id is not None, "artifact_id must be set after raw_save"
        result = extract_text(
            volume_path=volume_path,
            kind=_coerce_kind(state["kind"]),
            raw_bytes=state["raw_bytes"],
            settings=settings,
        )
        store.update_artifact_text(
            artifact_id=artifact_id,
            extracted_text=result.text,
        )
        return {"extracted_text": result.text}

    return extract


def _make_chunk_embed_node(settings: Settings):
    from agent_memory.memory.embeddings import embed_texts
    from agent_memory.memory.extraction import chunk_text

    store = LakebaseArtifactStore()

    def chunk_embed(state: IngestGraphState) -> dict:
        artifact_id = state["artifact_id"]
        assert artifact_id is not None, "artifact_id must be set after raw_save"
        text = state.get("extracted_text") or ""
        chunks = chunk_text(
            text,
            chunk_tokens=settings.chunk_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
        )
        if not chunks:
            return {"chunk_count": 0}
        embeddings = embed_texts(chunks, settings=settings)
        count = store.write_chunks(
            artifact_id=artifact_id,
            client_id=state["client_id"],
            chunks=chunks,
            embeddings=embeddings,
        )
        return {"chunk_count": count}

    return chunk_embed


def _make_summarize_node(settings: Settings):
    from agent_memory.agents.llm import build_chat_model

    store = LakebaseArtifactStore()

    _SUMMARIZE_SYSTEM = (
        "You are an assistant that writes concise dossier summaries for a wealth advisor. "
        "Summarize the key facts from the document in 2-4 sentences. "
        "Do not recommend any financial action. "
        "Output plain text only."
    )

    def summarize(state: IngestGraphState) -> dict:
        artifact_id = state["artifact_id"]
        assert artifact_id is not None, "artifact_id must be set after raw_save"
        text = state.get("extracted_text") or ""
        if not text:
            return {"summary": None}
        model = build_chat_model(settings)
        result = model.invoke(
            [
                SystemMessage(content=_SUMMARIZE_SYSTEM),
                HumanMessage(content=f"Document ({state['original_filename']}):\n\n{text[:8000]}"),
            ]
        )
        summary = result.content if isinstance(result.content, str) else str(result.content)
        store.update_artifact_text(
            artifact_id=artifact_id,
            extracted_text=text,
            summary=summary,
        )
        # Every LTM write requires an audit row (interfaces.md §7).
        store.write_audit(
            actor=state.get("agent_run_id") or "ingest_agent",
            actor_kind="agent",
            action="summarize_artifact",
            target_ref=f"client:{state['client_id']}/artifact:{artifact_id}",
            payload={"artifact_id": artifact_id, "note": "per-artifact summary auto-committed"},
            agent_run_id=state.get("agent_run_id"),
        )
        return {"summary": summary}

    return summarize


def _make_maybe_propose_node(settings: Settings):
    """Inline distillation trigger — proposes only when high-water mark gate passes."""

    def maybe_propose(state: IngestGraphState) -> dict:
        try:
            from agent_memory.memory.distillation import (
                LakebaseArtifactSource,
                run_distillation,
            )
            from agent_memory.memory.proposal_store import LakebaseProposalStore

            proposal_store = LakebaseProposalStore(settings)
            results = run_distillation(
                client_id=state["client_id"],
                settings=settings,
                hitl=True,
                artifact_source=LakebaseArtifactSource(settings),
                proposal_store=proposal_store,
                mlflow_run_id=state.get("agent_run_id"),
            )
            for r in results:
                if r.status == "proposed" and r.proposal_id:
                    return {"proposal_id": r.proposal_id}
        except Exception:
            # A proposal failure must not abort the ingest — the artifact is already
            # saved + indexed. Log it (with the client_id) so the failure is
            # diagnosable rather than silent; the advisor can re-trigger distillation.
            _LOG.warning(
                "maybe_propose: distillation/proposal failed for client_id=%s; "
                "artifact ingested, no proposal created",
                state.get("client_id"),
                exc_info=True,
            )
        return {"proposal_id": None}

    return maybe_propose


# ---------------------------------------------------------------------------
# Graph compiler
# ---------------------------------------------------------------------------

def _build_ingest_graph(settings: Settings):
    builder = StateGraph(IngestGraphState)

    builder.add_node("raw_save", _make_raw_save_node(settings))
    builder.add_node("extract", _make_extract_node(settings))
    builder.add_node("chunk_embed", _make_chunk_embed_node(settings))
    builder.add_node("summarize", _make_summarize_node(settings))
    builder.add_node("maybe_propose", _make_maybe_propose_node(settings))

    builder.add_edge(START, "raw_save")
    builder.add_edge("raw_save", "extract")
    builder.add_edge("extract", "chunk_embed")
    builder.add_edge("chunk_embed", "summarize")
    builder.add_edge("summarize", "maybe_propose")
    builder.add_edge("maybe_propose", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# SSE generator — drives the graph step-by-step
# ---------------------------------------------------------------------------

def run_ingest_graph(
    *,
    client_id: str,
    advisor_id: str,
    original_filename: str,
    kind: str,
    raw_bytes: bytes,
    settings: Settings | None = None,
) -> Iterator[dict[str, Any]]:
    """Run the ingest LangGraph and yield SSE event dicts (ADR-0010).

    Drives the graph node-by-node: each node writes back into state, and after
    each step we inspect the updated state to emit the appropriate SSE event.
    Wrapped in a single MLflow run named 'artifact_ingest'.
    """
    cfg = settings or Settings.from_env()
    if not ensure_databricks_auth(cfg):
        yield {"type": "error", "message": f"Databricks auth failed. {cfg.auth_diagnostics()}"}
        return

    set_mlflow_experiment(cfg)

    initial: IngestGraphState = {
        "client_id": client_id,
        "advisor_id": advisor_id,
        "original_filename": original_filename,
        "kind": kind,
        "raw_bytes": raw_bytes,
        "content_hash": None,
        "volume_path": None,
        "artifact_id": None,
        "extracted_text": None,
        "summary": None,
        "chunk_count": None,
        "proposal_id": None,
        "deduped": False,
        "agent_run_id": None,
        "error": None,
    }

    try:
        with mlflow.start_run(run_name="artifact_ingest") as run:
            initial["agent_run_id"] = run.info.run_id
            mlflow.set_tags(
                {
                    "client_id": client_id,
                    "advisor_id": advisor_id,
                    "kind": kind,
                    # original_filename is omitted — it may carry PII (client name in filename).
                }
            )

            graph = _build_ingest_graph(cfg)

            # Stream node-by-node: LangGraph's stream(mode="updates") yields one dict
            # per completed node with {node_name: state_delta}.
            final_state = dict(initial)
            for node_updates in graph.stream(initial, stream_mode="updates"):
                for node_name, delta in node_updates.items():
                    final_state.update(delta)

                    if node_name == "raw_save":
                        if final_state.get("deduped"):
                            # Short-circuit: artifact already exists in the dossier.
                            yield {
                                "type": "done",
                                "artifact_id": final_state["artifact_id"],
                                "deduped": True,
                            }
                            return
                        yield {
                            "type": "step",
                            "step": "saved",
                            "artifact_id": final_state.get("artifact_id"),
                        }

                    elif node_name == "extract":
                        raw_text = final_state.get("extracted_text")
                        text: str = raw_text if isinstance(raw_text, str) else ""
                        yield {
                            "type": "step",
                            "step": "extracted",
                            "chars": len(text),
                        }

                    elif node_name == "chunk_embed":
                        yield {
                            "type": "step",
                            "step": "embedded",
                            "chunks": final_state.get("chunk_count"),
                        }

                    elif node_name == "summarize":
                        yield {
                            "type": "step",
                            "step": "summarized",
                            "summary": final_state.get("summary"),
                        }

                    elif node_name == "maybe_propose":
                        pid = final_state.get("proposal_id")
                        if pid:
                            yield {
                                "type": "step",
                                "step": "proposed",
                                "proposal_id": pid,
                            }

            mlflow.log_params(
                {
                    "artifact_id": str(final_state.get("artifact_id")),
                    "kind": kind,
                    "deduped": str(final_state.get("deduped", False)),
                    "chunk_count": str(final_state.get("chunk_count")),
                }
            )
            yield {
                "type": "done",
                "artifact_id": final_state["artifact_id"],
                "deduped": False,
            }

    except Exception as exc:
        yield {"type": "error", "message": str(exc)}
