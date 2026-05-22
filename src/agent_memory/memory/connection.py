"""Postgres connection helpers for Lakebase."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse

from agent_memory.config import Settings, _infer_profile_from_host, load_local_env

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


def _databricks_profile(cfg: Settings) -> str:
    profile = cfg.databricks_profile or _infer_profile_from_host(cfg.databricks_host)
    if not profile:
        raise RuntimeError(
            "Set DATABRICKS_PROFILE (or DATABRICKS_HOST) for Lakebase OAuth refresh."
        )
    return profile


def _token_from_cli_json(result: subprocess.CompletedProcess[str], context: str) -> str:
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Lakebase credential refresh failed for {context}: {stderr}")
    payload = json.loads(result.stdout)
    token = payload.get("token")
    if not token:
        raise RuntimeError(f"No token in credential response for {context}: {payload}")
    return token


def _lakebase_oauth_token_autoscale(endpoint: str, profile: str) -> str:
    """Mint OAuth password for autoscaling Lakebase (postgres API)."""
    result = subprocess.run(
        [
            "databricks",
            "postgres",
            "generate-database-credential",
            endpoint,
            "--profile",
            profile,
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return _token_from_cli_json(result, endpoint)


def _lakebase_oauth_token_provisioned(instance_name: str, profile: str) -> str:
    """Mint OAuth password for provisioned Lakebase (database API, fast)."""
    body = json.dumps({"instance_names": [instance_name]})
    result = subprocess.run(
        [
            "databricks",
            "database",
            "generate-database-credential",
            "--json",
            body,
            "--profile",
            profile,
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return _token_from_cli_json(result, instance_name)


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
        user = user or str(parsed["user"])
        port = int(os.getenv("LAKEBASE_PORT", str(parsed["port"])))
        database = database or str(parsed["database"])

    database = database or "agent_memory"

    if not host or not user:
        raise RuntimeError(
            "Lakebase OAuth refresh needs LAKEBASE_URL or LAKEBASE_HOST + LAKEBASE_USER."
        )
    return _build_conninfo(host, port, database, user, token)


def _lakebase_credential_endpoint() -> str | None:
    explicit = (os.getenv("LAKEBASE_CREDENTIAL_ENDPOINT") or "").strip()
    if explicit:
        return explicit
    project = (os.getenv("LAKEBASE_PROJECT") or "").strip()
    if not project:
        return None
    slug = project.strip("/")
    if slug.startswith("projects/"):
        return slug
    branch = (os.getenv("LAKEBASE_BRANCH") or "production").strip()
    compute = (os.getenv("LAKEBASE_COMPUTE") or "primary").strip()
    return f"projects/{slug}/branches/{branch}/endpoints/{compute}"


def _lakebase_instance_name() -> str | None:
    return (os.getenv("LAKEBASE_INSTANCE_NAME") or "").strip() or None


def lakebase_conninfo(settings: Settings | None = None) -> str:
    """Build a libpq conninfo string from environment."""
    load_local_env()
    cfg = settings or Settings.from_env()
    static = cfg.lakebase_conninfo
    profile = _databricks_profile(cfg)
    endpoint = _lakebase_credential_endpoint()
    instance = _lakebase_instance_name()

    if static and instance and not endpoint:
        try:
            token = _lakebase_oauth_token_provisioned(instance, profile)
            return _conninfo_from_template(cfg, token, static_uri=static)
        except RuntimeError:
            pass

    if static and endpoint:
        token = _lakebase_oauth_token_autoscale(endpoint, profile)
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
) -> Iterator[psycopg.Connection]:
    """Open a Lakebase connection; register pgvector types when the extension exists."""
    import psycopg

    conninfo = lakebase_conninfo(settings)
    with psycopg.connect(conninfo) as conn:
        if register_pgvector:
            from pgvector.psycopg import register_vector

            register_vector(conn)
        yield conn
