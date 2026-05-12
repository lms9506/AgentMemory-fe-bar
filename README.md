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

1. `cp .env.example .env` and fill in your Databricks workspace details
2. `uv sync` (or `pip install -e ".[dev]"`)
3. Read `CLAUDE.md` → `docs/architecture.md` → `docs/requirements.md`
4. Pick an open task from `docs/progress.md`

## Stakeholders

See `docs/progress.md` for current owners and the FE-IP / Solution Accelerator nomination track.
