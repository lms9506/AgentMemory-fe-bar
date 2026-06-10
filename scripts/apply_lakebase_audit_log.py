#!/usr/bin/env python3
"""Create Lakebase `audit_log` only (fix when full schema apply missed it)."""

from __future__ import annotations

from agent_memory.memory.connection import lakebase_connection
from agent_memory.memory.lakebase_ddl import ensure_audit_log


def main() -> None:
    with lakebase_connection(register_pgvector=False) as conn, conn.cursor() as cur:
        ensure_audit_log(cur)
        conn.commit()
    print("Ensured audit_log table and indexes exist.")


if __name__ == "__main__":
    main()
