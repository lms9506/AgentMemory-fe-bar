"""CLI and Databricks Job entry point for the MLflow eval harness (FR-8, M8)."""

from __future__ import annotations

import argparse
import json
import os
from importlib.resources import files


def _load_eval_cases() -> dict:
    """Load eval_cases.json packaged with agent_memory.eval.

    Shipped as package data so it resolves inside the wheel (a python_wheel_task
    has no repo root or CWD data dir). The canonical source lives here, not in
    data/synthetic, because these are eval fixtures rather than synthetic client data.
    """
    resource = files("agent_memory.eval") / "eval_cases.json"
    return json.loads(resource.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run retrieval recall + response quality evals and log to MLflow."
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--run-response-eval",
        action="store_true",
        help="Also run LLM-as-judge response quality eval (calls FM API, costs more).",
    )
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

    import mlflow

    from agent_memory.agents.llm import build_chat_model
    from agent_memory.config import (
        Settings,
        _token_from_workspace_client,
        ensure_databricks_auth,
        get_workspace_client,
    )
    from agent_memory.eval.response import ResponseCase, run_response_eval
    from agent_memory.eval.retrieval import RetrievalCase, run_retrieval_eval
    from agent_memory.memory.store import LakebaseArtifactStore

    settings = Settings.from_env()
    if not ensure_databricks_auth(settings):
        try:
            wc = get_workspace_client(settings)
            wc.current_user.me()
            host = getattr(wc.config, "host", None)
            token = _token_from_workspace_client(wc)
            if host:
                os.environ.setdefault("DATABRICKS_HOST", host)
            if token:
                os.environ.setdefault("DATABRICKS_TOKEN", token)
        except Exception as err:
            raise SystemExit(f"Databricks auth failed. {settings.auth_diagnostics()}") from err

    if settings.mlflow_experiment_name:
        mlflow.set_experiment(settings.mlflow_experiment_name)

    eval_data = _load_eval_cases()
    retrieval_cases = [
        RetrievalCase(
            client_id=c["client_id"],
            query=c["query"],
            gold_keywords=c.get("gold_keywords", []),
        )
        for c in eval_data.get("retrieval", [])
    ]
    response_cases = [
        ResponseCase(
            client_id=c["client_id"],
            scenario=c["scenario"],
            profile_context=c.get("profile_context", ""),
        )
        for c in eval_data.get("response", [])
    ]

    store = LakebaseArtifactStore()
    llm = build_chat_model(settings)

    with mlflow.start_run(run_name="eval"):
        mlflow.log_params(
            {
                "top_k": args.top_k,
                "retrieval_cases": len(retrieval_cases),
                "response_cases": len(response_cases) if args.run_response_eval else 0,
            }
        )

        # Retrieval recall eval
        retrieval_results = run_retrieval_eval(retrieval_cases, store, top_k=args.top_k)
        recall_scores = [r.keyword_recall for r in retrieval_results]
        avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0.0
        mlflow.log_metric("retrieval_keyword_recall_avg", avg_recall)
        for i, r in enumerate(retrieval_results):
            mlflow.log_metric(f"retrieval_recall_case_{i}", r.keyword_recall)
            print(
                f"[retrieval] {r.case.client_id!r} query={r.case.query!r:.50} "
                f"recall={r.keyword_recall:.2f}"
            )
        print(f"[retrieval] avg recall@{args.top_k} = {avg_recall:.3f}")

        # Response quality eval (optional — calls FM API)
        if args.run_response_eval and response_cases:
            # Stub responses: run the agent for each scenario in eval mode.
            # For the accelerator demo we score placeholder responses; replace with
            # actual agent runs once the serving endpoint is deployed.
            placeholder_responses = [c.scenario for c in response_cases]
            scores = run_response_eval(response_cases, placeholder_responses, model=llm)
            avg_grounding = sum(s.grounding for s in scores) / len(scores)
            avg_suitability = sum(s.suitability for s in scores) / len(scores)
            avg_tone = sum(s.tone for s in scores) / len(scores)
            violations = sum(1 for s in scores if s.advice_boundary == "VIOLATION")
            mlflow.log_metrics(
                {
                    "response_grounding_avg": avg_grounding,
                    "response_suitability_avg": avg_suitability,
                    "response_tone_avg": avg_tone,
                    "response_advice_boundary_violations": violations,
                }
            )
            for i, s in enumerate(scores):
                print(
                    f"[response] case_{i}: grounding={s.grounding:.2f} "
                    f"suitability={s.suitability:.2f} tone={s.tone:.2f} "
                    f"advice_boundary={s.advice_boundary}"
                )


if __name__ == "__main__":
    main()
