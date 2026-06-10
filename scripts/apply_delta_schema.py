#!/usr/bin/env python3
"""Apply `databricks/delta_schema.sql` to Unity Catalog via SQL warehouse."""

from __future__ import annotations

from pathlib import Path

from agent_memory.config import Settings
from agent_memory.memory.lakebase_ddl import split_sql_statements
from agent_memory.memory.sql_warehouse import execute_sql


def main() -> None:
    settings = Settings.from_env()
    schema_path = Path(__file__).resolve().parents[1] / "databricks" / "delta_schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    sql = sql.replace("${catalog}", settings.uc_catalog).replace(
        "${schema}", settings.uc_schema
    )
    for statement in split_sql_statements(sql):
        execute_sql(statement, settings=settings)
    print(
        f"Applied Delta schema to {settings.uc_catalog}.{settings.uc_schema}.client_profile"
    )


if __name__ == "__main__":
    main()
