"""Create/refresh the Genie space over the governed dossier tables (ADR-0020).

Reads the version-controlled space definition (`databricks/genie/dossier_space.json`),
templates in the target catalog/schema/warehouse, and provisions a Genie space via
the Genie Spaces REST API. The space is the natural-language query surface required
by the accelerator's end-to-end journey — it sits on the UC-governed Delta tables the
Lakeflow pipeline and distillation job produce.

The Genie Spaces API is in preview; if the POST is unavailable this script prints
the exact manual setup (title, tables, instructions, sample questions) so the space
can be created in the Genie UI from the same committed definition.

Usage:
    uv run python scripts/setup_genie.py            # create/update from the JSON def
    uv run python scripts/setup_genie.py --print     # just print the resolved config
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_memory.config import Settings, ensure_databricks_auth, get_workspace_client
from agent_memory.memory.sql_warehouse import _warehouse_id_from_env, resolve_sql_warehouse_id

_DEF_PATH = Path(__file__).resolve().parents[1] / "databricks" / "genie" / "dossier_space.json"


def _resolve_def(settings: Settings) -> dict:
    raw = _DEF_PATH.read_text(encoding="utf-8")
    resolved = raw.replace("${catalog}", settings.uc_catalog).replace("${schema}", settings.uc_schema)
    return json.loads(resolved)


def _serialized_space(spec: dict) -> str:
    """Build the inner `serialized_space` JSON string (version-2 export shape).

    Tables MUST be sorted by identifier (the API rejects unsorted). Opaque ids are
    freshly minted 32-hex tokens. See the genie-rooms skill's example export.
    """
    import secrets

    def oid() -> str:
        return secrets.token_hex(16)

    tables = sorted(spec["tables"])
    serialized = {
        "version": 2,
        "config": {
            "sample_questions": [{"id": oid(), "question": [q]} for q in spec.get("sample_questions", [])]
        },
        "data_sources": {"tables": [{"identifier": t} for t in tables]},
        "instructions": {
            "text_instructions": [{"id": oid(), "content": [spec.get("instructions", "")]}]
        },
    }
    return json.dumps(serialized)


def _create_space(wc, warehouse_id: str, spec: dict) -> dict:
    """POST the space to the Genie Spaces API. Returns the API response.

    The create body wraps a JSON-encoded `serialized_space` string alongside the
    outer metadata (title/description/warehouse/parent). warehouse_id lives only in
    the outer body, never inside serialized_space.
    """
    home = wc.current_user.me().user_name
    body = {
        "title": spec["title"],
        "description": spec.get("description", ""),
        "parent_path": f"/Workspace/Users/{home}",
        "warehouse_id": warehouse_id,
        "serialized_space": _serialized_space(spec),
    }
    return wc.api_client.do("POST", "/api/2.0/genie/spaces", body=body)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Create/refresh the dossier Genie space.")
    parser.add_argument("--warehouse-id", default=None)
    parser.add_argument("--print", dest="print_only", action="store_true", help="Print resolved config and exit")
    args = parser.parse_args(argv)

    cfg = Settings.from_env()
    spec = _resolve_def(cfg)

    if args.print_only:
        print(json.dumps(spec, indent=2))
        return

    if not ensure_databricks_auth(cfg):
        raise SystemExit(f"Databricks auth failed. {cfg.auth_diagnostics()}")
    wc = get_workspace_client(cfg)
    warehouse_id = resolve_sql_warehouse_id(
        wc, warehouse_id=args.warehouse_id or _warehouse_id_from_env()
    )

    try:
        resp = _create_space(wc, warehouse_id, spec)
        space_id = resp.get("space_id") or resp.get("id") if isinstance(resp, dict) else None
        print(f"Genie space created/updated. space_id={space_id}")
        if space_id:
            host = cfg.databricks_host or ""
            print(f"Open: {host}/genie/rooms/{space_id}")
    except Exception as exc:  # preview API may be unavailable in this workspace
        print(f"Genie Spaces API call failed ({type(exc).__name__}: {exc}).")
        print("Create the space manually in the Genie UI with this definition:\n")
        print(f"  Title:       {spec['title']}")
        print(f"  Warehouse:   {warehouse_id}")
        print("  Tables:")
        for t in spec["tables"]:
            print(f"    - {t}")
        print("  Instructions:")
        print(f"    {spec.get('instructions', '')}")
        print("  Sample questions:")
        for q in spec.get("sample_questions", []):
            print(f"    - {q}")


if __name__ == "__main__":
    main()
