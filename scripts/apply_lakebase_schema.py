#!/usr/bin/env python3
"""Apply `databricks/lakebase_schema.sql` to a Lakebase database (T8)."""

from __future__ import annotations

from pathlib import Path

from agent_memory.memory.connection import lakebase_connection


def main() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "databricks" / "lakebase_schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    with lakebase_connection(register_pgvector=False) as conn, conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()
    print(f"Applied schema from {schema_path}")


if __name__ == "__main__":
    main()
