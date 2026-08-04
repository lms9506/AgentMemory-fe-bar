"""Postgres connection helpers for Lakebase."""

from __future__ import annotations

import functools
import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse

from agent_memory.config import (
    Settings,
    _infer_profile_from_host,
    get_workspace_client,
    load_local_env,
)

if TYPE_CHECKING:
    import psycopg


def _parse_postgres_uri(uri: str) -> dict[str, str | int]:
    """Extract libpq fields from a postgresql:// URI (password optional)."""
    parsed = urlparse(uri.strip())
    if parsed.scheme not in ("postgresql", "postgres"):
        msg = f"Unsupported LAKEBASE_URL scheme: {parsed.scheme!r}"
        raise RuntimeError(msg)
    database = (parsed.path or "/").lstrip("/").split("?")[0] or "postgres"
    return {
        "host": parsed.hostname or "",
        "port": parsed.port or 5432,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": database,
    }


@functools.lru_cache(maxsize=1)
def _resolve_lakebase_user(cfg: Settings) -> str:
    """Resolve the workspace user name once per process (cached to avoid per-connection HTTP probe)."""
    user_name = get_workspace_client(cfg).current_user.me().user_name
    if user_name is None:
        raise RuntimeError("Workspace identity returned no user_name; check authentication config.")
    return user_name


def clear_connection_caches() -> None:
    """Clear module-level caches. Called from _reset_auth_cache in config.py."""
    _resolve_lakebase_user.cache_clear()


def _databricks_profile(cfg: Settings) -> str:
    profile = cfg.databricks_profile or _infer_profile_from_host(cfg.databricks_host)
    if not profile:
        raise RuntimeError(
            "Set DATABRICKS_PROFILE (or DATABRICKS_HOST) for Lakebase OAuth refresh."
        )
    return profile


def _extract_credential_token(response: object, context: str) -> str:
    token = getattr(response, "token", None)
    if token:
        return token
    raise RuntimeError(f"No token in credential response for {context}")


def _lakebase_oauth_token_autoscale(endpoint: str, cfg: Settings) -> str:
    """Mint OAuth password for autoscaling Lakebase (via SDK, no CLI dependency)."""
    client = get_workspace_client(cfg)
    try:
        response = client.postgres.generate_database_credential(endpoint=endpoint)
    except Exception as exc:
        raise RuntimeError(f"Lakebase credential refresh failed for {endpoint}: {exc}") from exc
    return _extract_credential_token(response, endpoint)


def _lakebase_oauth_token_provisioned(instance_name: str, cfg: Settings) -> str:
    """Mint OAuth password for provisioned Lakebase (via SDK)."""
    client = get_workspace_client(cfg)
    try:
        response = client.database.generate_database_credential(instance_names=[instance_name])
    except Exception as exc:
        raise RuntimeError(f"Lakebase credential refresh failed for {instance_name}: {exc}") from exc
    return _extract_credential_token(response, instance_name)


def _build_conninfo(host: str, port: int, database: str, user: str, token: str) -> str:
    return (
        f"host={host} port={port} dbname={database} "
        f"user={user} password={token} sslmode=require"
    )


def _conninfo_from_template(
    cfg: Settings,
    token: str,
    *,
    static_uri: str | None = None,
) -> str:
    host = os.getenv("LAKEBASE_HOST")
    user = os.getenv("LAKEBASE_USER")
    port = int(os.getenv("LAKEBASE_PORT", "5432"))
    database = cfg.lakebase_database or os.getenv("LAKEBASE_DATABASE")

    if static_uri:
        parsed = _parse_postgres_uri(static_uri)
        host = host or str(parsed["host"])
        # URL user field may be empty after app.yaml strip; prefer env override.
        url_user = str(parsed["user"])
        if not user and url_user:
            user = url_user
        port = int(os.getenv("LAKEBASE_PORT", str(parsed["port"])))
        database = database or str(parsed["database"])

    database = database or "agent_memory"

    # When no explicit user override is set, derive from the authenticated token
    # identity so the Postgres role always matches the OAuth bearer (required for SP).
    # _resolve_lakebase_user is cached at module level to avoid a per-connection HTTP probe.
    if not user:
        user = _resolve_lakebase_user(cfg)

    if not host or not user:
        raise RuntimeError(
            "Lakebase OAuth refresh needs LAKEBASE_HOST and (LAKEBASE_USER or workspace auth)."
        )
    return _build_conninfo(host, port, database, user, token)


def _lakebase_credential_endpoint() -> str | None:
    explicit = (os.getenv("LAKEBASE_CREDENTIAL_ENDPOINT") or "").strip()
    if explicit:
        # Accept both full endpoint path and bare project/branch path.
        if "/endpoints/" in explicit:
            return explicit
        # Treat as branch path — append default endpoint.
        compute = (os.getenv("LAKEBASE_COMPUTE") or "primary").strip()
        return f"{explicit.rstrip('/')}/endpoints/{compute}"
    project = (os.getenv("LAKEBASE_PROJECT") or "").strip()
    if not project:
        return None
    slug = project.strip("/")
    # Normalise: strip a leading "projects/" prefix so slug is just the project ID.
    if slug.startswith("projects/"):
        slug = slug[len("projects/"):]
    branch = (os.getenv("LAKEBASE_BRANCH") or "production").strip()
    # LAKEBASE_BRANCH may be a full path like "projects/foo/branches/bar".
    branch_slug = branch.rstrip("/").split("/")[-1] if "/" in branch else branch
    compute = (os.getenv("LAKEBASE_COMPUTE") or "primary").strip()
    return f"projects/{slug}/branches/{branch_slug}/endpoints/{compute}"


def _lakebase_instance_name() -> str | None:
    return (os.getenv("LAKEBASE_INSTANCE_NAME") or "").strip() or None


def lakebase_conninfo(settings: Settings | None = None) -> str:
    """Build a libpq conninfo string from environment."""
    load_local_env()
    cfg = settings or Settings.from_env()
    static = cfg.lakebase_conninfo
    endpoint = _lakebase_credential_endpoint()
    instance = _lakebase_instance_name()

    if static and instance and not endpoint:
        try:
            token = _lakebase_oauth_token_provisioned(instance, cfg)
            return _conninfo_from_template(cfg, token, static_uri=static)
        except RuntimeError:
            pass

    if static and endpoint:
        token = _lakebase_oauth_token_autoscale(endpoint, cfg)
        return _conninfo_from_template(cfg, token, static_uri=static)

    if static:
        return static.strip()

    host = os.getenv("LAKEBASE_HOST")
    database = cfg.lakebase_database or os.getenv("LAKEBASE_DATABASE", "agent_memory")
    user = os.getenv("LAKEBASE_USER")
    password = os.getenv("LAKEBASE_PASSWORD")
    port = os.getenv("LAKEBASE_PORT", "5432")

    if not host or not user or not password:
        msg = (
            "Lakebase not configured for auto-refresh. Set LAKEBASE_URL plus either "
            "LAKEBASE_CREDENTIAL_ENDPOINT (autoscaling — copy from Lakebase UI → Connect) "
            "or LAKEBASE_INSTANCE_NAME (provisioned tier only)."
        )
        raise RuntimeError(msg)

    return f"host={host} port={port} dbname={database} user={user} password={password} sslmode=require"


@contextmanager
def lakebase_connection(
    settings: Settings | None = None,
    *,
    register_pgvector: bool = True,
) -> Generator[psycopg.Connection, None, None]:
    """Open a Lakebase connection; register pgvector types when the extension exists."""
    import psycopg

    conninfo = lakebase_conninfo(settings)
    with psycopg.connect(conninfo) as conn:
        if register_pgvector:
            from pgvector.psycopg import register_vector

            register_vector(conn)
        yield conn
