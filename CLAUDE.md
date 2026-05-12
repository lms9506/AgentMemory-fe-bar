# CLAUDE.md — Project context for AI assistants

> This file is the **entry point** for Claude Code (and Cursor / Copilot if used). Keep it short. The deeper content lives in `docs/`. Update this file whenever the answer to "what would a new collaborator need to know on day one?" changes.

## What this project is

A Databricks Solution Accelerator for **agent memory** in regulated industries. Concretely: an AI Wealth Advisor that remembers client conversations across sessions, distills them into a governed long-term profile, and exposes the memory state in an advisor-facing Databricks App.

The "memory" is not a side feature — in wealth management it's a **compliance artifact** (suitability assessments, audit trails, cross-advisor continuity). Frame design choices through that lens.

## Stack (load-bearing only)

- **Python 3.11+** — the only application language
- **LangGraph + LangChain** — stateful agent orchestration
- **Lakebase (Postgres + pgvector)** — episodic store + semantic vector store
- **Delta Tables in Unity Catalog** — distilled long-term profiles + audit trail (via time travel)
- **Mosaic AI Agent Framework** — agent runtime; uses the Databricks stateful-agents SDK
- **Foundation Model API** — LLM (no external API keys)
- **Databricks Apps** — advisor UI
- **MLflow** — eval + tracing
- **Databricks Asset Bundles (DABs)** — deployment (`databricks/databricks.yml`)

Anything outside this list needs an ADR in `docs/decisions.md`.

## Where to look first

| If you're about to… | Read |
|---|---|
| Implement a feature | `docs/requirements.md` then `docs/architecture.md` |
| Pick up work | `docs/progress.md` |
| Make a non-trivial design choice | `docs/decisions.md` (add a new ADR) |
| Name a memory concept | `docs/glossary.md` |
| Open a PR | `docs/conventions.md` |

## House rules for AI assistants

1. **Prefer editing over creating.** Don't add a new module if an existing one fits. Don't add a new doc if a section in an existing doc fits.
2. **No silent scope creep.** Bug fixes don't get refactors. One-shot tasks don't get helper modules. If you find a real adjacent issue, open a follow-up task in `docs/progress.md` — don't bundle.
3. **Memory is a compliance artifact.** Every write to long-term memory needs a corresponding audit row. Don't optimize away the audit trail.
4. **Lakebase is the source of truth for live memory; Delta is the source of truth for archived profiles.** Don't blur the two.
5. **No external memory services.** No Pinecone, no Redis, no Mem0. We are showcasing the Databricks-native path. New dependencies need an ADR.
6. **Synthetic data only in the repo.** Real client data never goes near this codebase. Generators live in `data/synthetic/`.
7. **MLflow traces on every agent run.** Don't add code paths that bypass tracing.
8. **Update `docs/progress.md` when you start and finish a task.** Future-you and your teammates rely on it.
9. **Comments explain *why*, not *what*.** No "// added for the May 12 review" comments — that belongs in the commit message.
10. **Don't push to `main`.** Branch + PR. See `docs/conventions.md`.

## MCP tools available

This repo configures **only the Databricks MCP server** (see `.mcp.json`). Use it for:
- Querying Lakebase / Unity Catalog tables
- Reading job + pipeline state
- Running notebooks
- Workspace file ops

If you need a capability outside Databricks MCP, ask the user before adding another server — we deliberately keep the MCP surface small.

## Quick commands

```bash
uv sync                                 # install deps
uv run pytest                           # run tests
uv run ruff check src/ tests/           # lint
databricks bundle deploy --target dev   # deploy DAB to dev workspace
databricks bundle run wealth_advisor    # run the agent job
```

## Out of scope (don't build these without an ADR)

- A generic "memory framework" abstraction across industries — this is the FINS accelerator, not a library
- A custom vector index — pgvector is the choice
- A non-Databricks UI — Streamlit/React inside Databricks Apps only
- Multi-tenant SaaS hosting — this is reference code, not a product
