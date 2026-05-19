"""Local entrypoint for a single advisor turn (M4 smoke run)."""

from __future__ import annotations

import argparse
import os

import mlflow
from langchain_core.messages import HumanMessage

from agent_memory.agents.graph import build_default_graph
from agent_memory.agents.state import AdvisorAgentState
from agent_memory.config import Settings


def run_turn(
    *,
    client_id: str,
    advisor_id: str,
    session_id: str,
    user_message: str,
    settings: Settings | None = None,
) -> str:
    """Run one advisor turn under MLflow tracing."""
    cfg = settings or Settings.from_env()
    graph = build_default_graph()

    initial: AdvisorAgentState = {
        "client_id": client_id,
        "advisor_id": advisor_id,
        "session_id": session_id,
        "messages": [HumanMessage(content=user_message)],
        "response": None,
    }

    if cfg.mlflow_experiment_name:
        mlflow.set_experiment(cfg.mlflow_experiment_name)

    with mlflow.start_run(run_name="advisor_single_turn"):
        mlflow.set_tags(
            {
                "client_id": client_id,
                "advisor_id": advisor_id,
                "session_id": session_id,
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
    args = parser.parse_args()

    if not os.getenv("DATABRICKS_HOST") or not os.getenv("DATABRICKS_TOKEN"):
        raise SystemExit(
            "Set DATABRICKS_HOST and DATABRICKS_TOKEN (see .env.example) to call the FM API."
        )

    reply = run_turn(
        client_id=args.client_id,
        advisor_id=args.advisor_id,
        session_id=args.session_id,
        user_message=args.message,
    )
    print(reply)


if __name__ == "__main__":
    main()
