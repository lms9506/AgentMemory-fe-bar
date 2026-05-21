"""Foundation Model API embeddings (ADR-0004: databricks-bge-large-en)."""

from __future__ import annotations

from agent_memory.config import Settings, ensure_databricks_auth


def embed_texts(texts: list[str], settings: Settings | None = None) -> list[list[float]]:
    """Embed one or more strings; returns 1024-d vectors."""
    if not texts:
        return []
    cfg = settings or Settings.from_env()
    if not ensure_databricks_auth(cfg):
        msg = "Databricks auth required for embeddings."
        raise RuntimeError(msg)

    from langchain_community.embeddings import DatabricksEmbeddings

    model = DatabricksEmbeddings(endpoint=cfg.fm_api_embedding_endpoint)
    if len(texts) == 1:
        return [model.embed_query(texts[0])]
    return model.embed_documents(texts)
