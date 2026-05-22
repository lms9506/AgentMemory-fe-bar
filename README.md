# Agent Memory — Databricks Solution Accelerator

A reference implementation showing how to give a Databricks-hosted AI agent **durable, governed, multi-session memory** using Lakebase (Postgres + pgvector), Delta Tables in Unity Catalog, the Mosaic AI Agent Framework (LangGraph), Databricks Apps, and MLflow.

**Industry focus:** Financial Services — AI Wealth Advisor with persistent client memory.

> The "50% solution" — get a wealth-management team from zero to a client-memory-enabled AI advisor PoC in under two weeks.

## Repo map

```
AgentMemory/
├── CLAUDE.md              ← Project memory for Claude Code (read this first)
├── docs/
│   ├── requirements.md    ← Functional + non-functional requirements
│   ├── architecture.md    ← 5-layer Databricks architecture
│   ├── progress.md        ← Current sprint / task status
│   ├── decisions.md       ← ADR-style decision log
│   ├── conventions.md     ← Code, commit, branching conventions
│   └── glossary.md        ← Memory taxonomy + domain terms
├── src/agent_memory/      ← Python package: agents, memory, tools, UI
├── databricks/            ← databricks.yml (DABs), app.yaml, Lakebase schema
├── notebooks/             ← Exploration + demo notebooks
├── tests/                 ← pytest suite
├── data/synthetic/        ← Dummy client + portfolio data
└── .mcp.json              ← Databricks MCP server config
```

## Getting started

1. `cp .env.shared .env` and adjust for your workspace (see comments in `.env.shared`)
2. `databricks auth login --profile <your-profile>` if using CLI OAuth
3. `uv sync --extra dev`
4. Read `CLAUDE.md` → `docs/architecture.md` → `docs/requirements.md`
5. Pick an open task from `docs/progress.md`

**Quick local checks:** `uv run pytest` (no workspace); `uv run agent-memory-chat --no-memory` (FM API only); with Lakebase configured and schema applied, `uv run agent-memory-chat` (full M5 path).

## Stakeholders

See `docs/progress.md` for current owners and the FE-IP / Solution Accelerator nomination track.
