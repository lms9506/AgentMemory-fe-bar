"""Databricks UC Managed Memory client (Beta).

Thin wrapper around the `/api/2.1/unity-catalog/memory-stores/*` REST surface,
used as a second lane alongside Lakebase pgvector. Writes distilled client
profiles as entries scoped by client_id so downstream agents can retrieve them
without querying Lakebase directly.

Docs: https://learn.microsoft.com/en-us/azure/databricks/agents/agent-memory/managed-memory
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from databricks.sdk import WorkspaceClient

logger = logging.getLogger(__name__)

_ENABLED_ENV = "MANAGED_MEMORY_ENABLED"
_STORE_ENV = "MANAGED_MEMORY_STORE"


@dataclass(frozen=True)
class ManagedMemoryEntry:
    scope: str
    path: str
    contents: str
    description: str = ""  # short summary — improves recall (per docs)


def is_enabled() -> bool:
    return os.getenv(_ENABLED_ENV, "").lower() in {"1", "true", "yes"}


def store_full_name() -> str | None:
    return os.getenv(_STORE_ENV) or None


def _client() -> WorkspaceClient:
    return WorkspaceClient()


def write_entry(entry: ManagedMemoryEntry) -> None:
    """Upsert a managed memory entry. Best-effort; logs and returns on failure.

    Managed memory writes are complementary — a failure here MUST NOT break the primary
    Lakebase/Delta write path. Callers should treat this as a fire-and-log lane.

    POST is create-only per the docs (returns "already exists" on collision). On collision
    we fall back to PATCH with replace_all to overwrite contents + description.
    """
    if not is_enabled():
        return
    store = store_full_name()
    if not store:
        logger.debug("managed memory: %s unset; skip write", _STORE_ENV)
        return
    body_create = {"path": entry.path, "contents": entry.contents}
    if entry.description:
        body_create["description"] = entry.description
    wc = _client()
    try:
        wc.api_client.do(
            "POST",
            f"/api/2.1/unity-catalog/memory-stores/{store}/entries",
            query={"scope": entry.scope},
            body=body_create,
        )
        logger.info("managed_memory.write scope=%s path=%s (create)", entry.scope, entry.path)
        return
    except Exception as exc:  # noqa: BLE001
        if "already exists" not in str(exc).lower():
            logger.warning("managed memory create failed (non-fatal): %r", exc)
            return
    # Fall through: PATCH replace_all
    patch_body: dict[str, object] = {
        "scope": entry.scope,
        "path": entry.path,
        "replace_all": {"contents": entry.contents},
    }
    if entry.description:
        patch_body["description"] = entry.description
    try:
        wc.api_client.do(
            "PATCH",
            f"/api/2.1/unity-catalog/memory-stores/{store}/entries",
            body=patch_body,
        )
        logger.info("managed_memory.write scope=%s path=%s (update)", entry.scope, entry.path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("managed memory update failed (non-fatal): %r", exc)


def search(scope: str, query: str, top_k: int = 5) -> list[dict]:
    """Search entries in the configured store. Empty list on failure or when disabled.

    Returns a list of {memory_entry: {...}, score: N} objects per the API's `results`
    envelope. Callers can render `.memory_entry.description` / `.memory_entry.contents`
    and use `.score` for ranking display.
    """
    if not is_enabled():
        return []
    store = store_full_name()
    if not store:
        return []
    try:
        wc = _client()
        resp = wc.api_client.do(
            "POST",
            f"/api/2.1/unity-catalog/memory-stores/{store}/entries:search",
            body={"scope": scope, "query": query, "top_k": min(top_k, 50)},
        )
        return list((resp or {}).get("results", []))
    except Exception as exc:  # noqa: BLE001
        logger.warning("managed memory search failed: %r", exc)
        return []


def format_profile_entry(profile: object) -> str:
    """Render a DistilledClientProfile-like object as a markdown block for storage.

    Kept typing loose so this module has no import dependency on profile_models.
    """
    def _attr(name: str) -> str:
        v = getattr(profile, name, None)
        if v is None:
            return "—"
        if isinstance(v, (list, tuple)):
            return ", ".join(str(x) for x in v) if v else "—"
        return str(v)

    return (
        f"# Client Profile ({_attr('client_id')})\n\n"
        f"- **Risk tolerance:** {_attr('risk_tolerance')}\n"
        f"- **Investment goals:** {_attr('investment_goals')}\n"
        f"- **Family context:** {_attr('family_context')}\n"
        f"- **Stated preferences:** {_attr('stated_preferences')}\n\n"
        f"## Summary\n{_attr('summary')}\n"
    )


def format_profile_description(profile: object) -> str:
    """One-line summary used as the entry's `description` — improves search recall.

    Docs: "Use the `contents` field for the full memory text and the `description`
    as a short summary that improves retrieval."
    """
    def _attr(name: str) -> str:
        v = getattr(profile, name, None)
        if v is None:
            return ""
        if isinstance(v, (list, tuple)):
            return ", ".join(str(x) for x in v) if v else ""
        return str(v)

    parts = [
        f"Client {_attr('client_id')}",
        f"risk tolerance: {_attr('risk_tolerance')}" if _attr("risk_tolerance") else "",
        f"goals: {_attr('investment_goals')}" if _attr("investment_goals") else "",
        _attr("stated_preferences"),
    ]
    return "; ".join(p for p in parts if p)
