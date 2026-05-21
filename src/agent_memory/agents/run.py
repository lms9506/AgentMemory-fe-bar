"""Local entrypoint for advisor turns with optional Lakebase memory."""

from __future__ import annotations

import argparse

import mlflow
from langchain_core.messages import HumanMessage

from agent_memory.agents.graph import build_default_graph
from agent_memory.agents.state import AdvisorAgentState
from agent_memory.config import Settings, ensure_databricks_auth


def run_turn(
    *,
    client_id: str,
    advisor_id: str,
    session_id: str,
    user_message: str,
    settings: Settings | None = None,
    with_memory: bool = True,
) -> str:
    """Run one advisor turn under MLflow tracing."""
    cfg = settings or Settings.from_env()
    if not ensure_databricks_auth(cfg):
        raise RuntimeError(f"Databricks auth failed. {cfg.auth_diagnostics()}")

    if with_memory and not cfg.lakebase_configured:
        raise RuntimeError(
            "Lakebase not configured. Set LAKEBASE_CONNINFO or "
            "LAKEBASE_HOST/USER/PASSWORD, apply lakebase_schema.sql (T8)."
        )

    graph = build_default_graph(with_memory=with_memory)

    initial: AdvisorAgentState = {
        "client_id": client_id,
        "advisor_id": advisor_id,
        "session_id": session_id,
        "messages": [HumanMessage(content=user_message)],
        "response": None,
        "retrieved_turns": [],
        "agent_run_id": None,
    }

    if cfg.mlflow_experiment_name:
        mlflow.set_experiment(cfg.mlflow_experiment_name)

    with mlflow.start_run(run_name="advisor_turn"):
        active = mlflow.active_run()
        if active is not None:
            initial["agent_run_id"] = active.info.run_id
        mlflow.set_tags(
            {
                "client_id": client_id,
                "advisor_id": advisor_id,
                "session_id": session_id,
                "with_memory": str(with_memory),
            }
        )
        final = graph.invoke(initial)

    return final["response"] or ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one wealth-advisor agent turn.")
    parser.add_argument("--client-id", default="client_0000")
    parser.add_argument("--advisor-id", default="advisor_demo_01")
    parser.add_argument("--session-id", default="session_demo")
    parser.add_argument(
        "--message",
        default="Summarize what we should confirm before discussing retirement income.",
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="M4 mode: generate only, no Lakebase read/write",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    if not ensure_databricks_auth(settings):
        raise SystemExit(f"Databricks auth failed. {settings.auth_diagnostics()}")

    reply = run_turn(
        client_id=args.client_id,
        advisor_id=args.advisor_id,
        session_id=args.session_id,
        user_message=args.message,
        settings=settings,
        with_memory=not args.no_memory,
    )
    print(reply)


if __name__ == "__main__":
    main()
