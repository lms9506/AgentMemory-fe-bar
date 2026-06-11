"""CLI and Databricks Job entrypoint for nightly profile distillation (M6)."""

from __future__ import annotations

import argparse
import os

import mlflow

from agent_memory.config import (
    Settings,
    _token_from_workspace_client,
    ensure_databricks_auth,
    get_workspace_client,
)
from agent_memory.memory.distillation import run_distillation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Distill recent Lakebase turns into UC Delta client_profile."
    )
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--client-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    # Parsed as a value (not store_true): DAB named_parameters is a dict, so the job
    # spec must emit --hitl=true. Accept the truthy string; default off for CLI/dry-run.
    parser.add_argument(
        "--hitl",
        type=lambda v: str(v).strip().lower() in ("true", "1", "yes"),
        default=False,
        help="Write proposals to Lakebase instead of committing directly to Delta (FR-6).",
    )
    # Named params injected by the DAB job spec (serverless has no spark_env_vars).
    parser.add_argument("--databricks-host")
    parser.add_argument("--uc-catalog")
    parser.add_argument("--uc-schema")
    parser.add_argument("--warehouse-id")
    parser.add_argument("--fm-endpoint")
    parser.add_argument("--fm-embedding-endpoint")
    parser.add_argument("--mlflow-experiment")
    parser.add_argument("--lakebase-instance-name")
    parser.add_argument("--lakebase-project")  # legacy autoscale model; unset for provisioned
    parser.add_argument("--lakebase-branch")
    parser.add_argument("--lakebase-url")
    parser.add_argument("--lakebase-database")
    args = parser.parse_args()

    # Apply job-injected config to the environment BEFORE Settings.from_env() so the
    # serverless compute doesn't need spark_env_vars (unsupported for env-key tasks).
    _setenv = lambda k, v: os.environ.setdefault(k, v) if v else None  # noqa: E731
    _setenv("DATABRICKS_HOST", args.databricks_host)
    _setenv("UC_CATALOG", args.uc_catalog)
    _setenv("UC_SCHEMA", args.uc_schema)
    _setenv("DATABRICKS_SQL_WAREHOUSE_ID", args.warehouse_id)
    _setenv("FM_API_ENDPOINT", args.fm_endpoint)
    _setenv("FM_API_EMBEDDING_ENDPOINT", args.fm_embedding_endpoint)
    _setenv("MLFLOW_EXPERIMENT_NAME", args.mlflow_experiment)
    _setenv("LAKEBASE_INSTANCE_NAME", args.lakebase_instance_name)
    _setenv("LAKEBASE_PROJECT", args.lakebase_project)
    _setenv("LAKEBASE_BRANCH", args.lakebase_branch)
    _setenv("LAKEBASE_URL", args.lakebase_url)
    _setenv("LAKEBASE_DATABASE", args.lakebase_database)

    settings = Settings.from_env()
    if not ensure_databricks_auth(settings):
        # In serverless job context there is no .env or CLI profile — rely on the
        # SDK's runtime credential provider (injected automatically by the platform).
        try:
            wc = get_workspace_client(settings)
            wc.current_user.me()
            # Backfill env vars that LangChain reads directly from the environment.
            host = getattr(wc.config, "host", None)
            token = _token_from_workspace_client(wc)
            if host:
                os.environ.setdefault("DATABRICKS_HOST", host)
            if token:
                os.environ.setdefault("DATABRICKS_TOKEN", token)
        except Exception as err:
            raise SystemExit(f"Databricks auth failed. {settings.auth_diagnostics()}") from err

    if not args.dry_run and not settings.lakebase_configured:
        raise SystemExit(
            "Lakebase not configured (required for turn reads and audit). "
            "Use --dry-run only for LLM parse tests with injected sources in unit tests."
        )

    if settings.mlflow_experiment_name:
        mlflow.set_experiment(settings.mlflow_experiment_name)

    proposal_store = None
    if args.hitl and not args.dry_run:
        from agent_memory.memory.proposal_store import LakebaseProposalStore

        proposal_store = LakebaseProposalStore(settings)

    with mlflow.start_run(run_name="distillation") as run:
        mlflow.log_params(
            {
                "lookback_days": args.lookback_days,
                "client_id": args.client_id or "all",
                "dry_run": str(args.dry_run),
                "hitl": str(args.hitl),
            }
        )
        artifact_source = None
        if not args.dry_run:
            from agent_memory.memory.distillation import LakebaseArtifactSource
            artifact_source = LakebaseArtifactSource(settings)

        results = run_distillation(
            lookback_days=args.lookback_days,
            client_id=args.client_id,
            settings=settings,
            artifact_source=artifact_source,
            use_delta=not args.dry_run,
            hitl=args.hitl and not args.dry_run,
            proposal_store=proposal_store,
            mlflow_run_id=run.info.run_id,
        )
        upserted = sum(1 for r in results if r.status == "upserted")
        proposed = sum(1 for r in results if r.status == "proposed")
        errors = sum(1 for r in results if r.status == "error")
        mlflow.log_metrics(
            {
                "clients_upserted": upserted,
                "clients_proposed": proposed,
                "clients_error": errors,
            }
        )

    for r in results:
        line = f"{r.client_id}: {r.status}"
        if r.delta_version is not None:
            line += f" (delta_version={r.delta_version})"
        if r.proposal_id is not None:
            line += f" (proposal_id={r.proposal_id})"
        if r.error:
            line += f" — {r.error}"
        print(line)

    if any(r.status == "error" for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
