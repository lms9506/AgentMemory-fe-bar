"""Execute SQL on a Databricks SQL warehouse (UC Delta DDL/DML)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from agent_memory.config import Settings, get_workspace_client

if TYPE_CHECKING:
    from databricks.sdk import WorkspaceClient


def _workspace(settings: Settings | None = None) -> WorkspaceClient:
    cfg = settings or Settings.from_env()
    if not cfg.databricks_configured:
        msg = f"Databricks auth required for SQL. {cfg.auth_diagnostics()}"
        raise RuntimeError(msg)
    return get_workspace_client(cfg)


def resolve_sql_warehouse_id(
    client: WorkspaceClient,
    *,
    warehouse_id: str | None = None,
) -> str:
    """Use explicit id or the first RUNNING warehouse in the workspace."""
    if warehouse_id:
        return warehouse_id
    for wh in client.warehouses.list():
        state = getattr(wh.state, "value", wh.state)
        if state == "RUNNING" and wh.id:
            return wh.id
    msg = (
        "No RUNNING SQL warehouse found. Set DATABRICKS_SQL_WAREHOUSE_ID "
        "or start a warehouse in the workspace."
    )
    raise RuntimeError(msg)


def fetch_sql(
    statement: str,
    *,
    settings: Settings | None = None,
    warehouse_id: str | None = None,
    wait_timeout: str = "50s",
) -> list[list[str | None]]:
    """Run a SELECT (or other row-returning statement) and return result rows."""
    cfg = settings or Settings.from_env()
    client = _workspace(cfg)
    wh_id = resolve_sql_warehouse_id(
        client,
        warehouse_id=warehouse_id or _warehouse_id_from_env(),
    )
    response = client.statement_execution.execute_statement(
        warehouse_id=wh_id,
        statement=statement,
        wait_timeout=wait_timeout,
    )
    statement_id = response.statement_id
    if not statement_id:
        msg = "SQL execution did not return a statement_id"
        raise RuntimeError(msg)
    _wait_for_statement(client, statement_id)
    result = client.statement_execution.get_statement(statement_id)
    if result.result and result.result.data_array:
        return [
            [cell if cell is None or isinstance(cell, str) else str(cell) for cell in row]
            for row in result.result.data_array
        ]
    return []


def execute_sql(
    statement: str,
    *,
    settings: Settings | None = None,
    warehouse_id: str | None = None,
    wait_timeout: str = "50s",
) -> str:
    """Run one statement and block until it finishes. Returns the statement id."""
    cfg = settings or Settings.from_env()
    client = _workspace(cfg)
    wh_id = resolve_sql_warehouse_id(
        client,
        warehouse_id=warehouse_id or _warehouse_id_from_env(),
    )
    response = client.statement_execution.execute_statement(
        warehouse_id=wh_id,
        statement=statement,
        wait_timeout=wait_timeout,
    )
    statement_id = response.statement_id
    if not statement_id:
        msg = "SQL execution did not return a statement_id"
        raise RuntimeError(msg)
    _wait_for_statement(client, statement_id)
    return statement_id


def _warehouse_id_from_env() -> str | None:
    import os

    from agent_memory.config import load_local_env

    load_local_env()
    return os.getenv("DATABRICKS_SQL_WAREHOUSE_ID")


def _wait_for_statement(client: WorkspaceClient, statement_id: str, *, max_wait_s: int = 120) -> None:
    deadline = time.monotonic() + max_wait_s
    while time.monotonic() < deadline:
        status = client.statement_execution.get_statement(statement_id)
        state = status.status.state if status.status else None
        if state and state.value in ("SUCCEEDED", "FAILED", "CANCELED"):
            if state.value != "SUCCEEDED":
                err = status.status.error if status.status else None
                msg = f"SQL failed ({state.value}): {err}"
                raise RuntimeError(msg)
            return
        time.sleep(1.0)
    msg = f"SQL statement {statement_id} timed out after {max_wait_s}s"
    raise RuntimeError(msg)


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_array_strings(values: list[str]) -> str:
    if not values:
        return "array()"
    parts = ", ".join(_sql_string(v) for v in values)
    return f"array({parts})"


def _sql_array_bigints(values: list[int]) -> str:
    if not values:
        return "array()"
    return "array(" + ", ".join(str(v) for v in values) + ")"
