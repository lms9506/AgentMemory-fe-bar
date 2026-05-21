"""Postgres connection helpers for Lakebase."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from agent_memory.config import Settings, load_local_env

if TYPE_CHECKING:
    import psycopg


def lakebase_conninfo(settings: Settings | None = None) -> str:
    """Build a libpq conninfo string from environment."""
    load_local_env()
    cfg = settings or Settings.from_env()
    if cfg.lakebase_conninfo:
        return cfg.lakebase_conninfo

    host = os.getenv("LAKEBASE_HOST")
    database = cfg.lakebase_database or os.getenv("LAKEBASE_DATABASE", "agent_memory")
    user = os.getenv("LAKEBASE_USER")
    password = os.getenv("LAKEBASE_PASSWORD")
    port = os.getenv("LAKEBASE_PORT", "5432")

    if not host or not user or not password:
        msg = (
            "Set LAKEBASE_CONNINFO or LAKEBASE_HOST, LAKEBASE_USER, "
            "LAKEBASE_PASSWORD (and optionally LAKEBASE_DATABASE)."
        )
        raise RuntimeError(msg)

    return f"host={host} port={port} dbname={database} user={user} password={password} sslmode=require"


@contextmanager
def lakebase_connection(settings: Settings | None = None) -> Iterator[psycopg.Connection]:
    """Open a Lakebase connection with pgvector types registered."""
    import psycopg
    from pgvector.psycopg import register_vector

    conninfo = lakebase_conninfo(settings)
    with psycopg.connect(conninfo) as conn:
        register_vector(conn)
        yield conn
