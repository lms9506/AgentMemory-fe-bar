#!/usr/bin/env python3
"""Apply `databricks/lakebase_schema.sql` to a Lakebase database (T8)."""

from __future__ import annotations

from agent_memory.memory.connection import lakebase_connection
from agent_memory.memory.lakebase_ddl import schema_sql_path, split_sql_statements


def main() -> None:
    schema_path = schema_sql_path()
    sql = schema_path.read_text(encoding="utf-8")
    statements = split_sql_statements(sql)
    with lakebase_connection(register_pgvector=False) as conn, conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
        conn.commit()
    print(f"Applied {len(statements)} statements from {schema_path}")


if __name__ == "__main__":
    main()
