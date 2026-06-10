# Agent Memory — Databricks Solution Accelerator

A reference implementation showing how to give a Databricks-hosted AI agent **durable, governed, longitudinal memory** — built entirely on Lakebase (Postgres + pgvector), UC Volumes, Delta in Unity Catalog, `ai_parse_document`, the Mosaic AI Agent Framework (LangGraph), Databricks Apps, and MLflow.

**Industry focus:** Financial Services — an **AI Wealth Advisor with persistent client memory**.

## What it is (and isn't)

It's an **advisor-facing** tool, not a client chatbot (Databricks Apps are internal/workspace-authenticated). The advisor **feeds a client dossier** — meeting notes, scanned statements, PDFs, photos of handwritten notes, typed notes — by drag-and-drop. The agent:

1. saves the original file **unchanged** to a UC Volume (the compliance record),
2. extracts it with **`ai_parse_document`**, then chunks + embeds it into **Lakebase pgvector**,
3. **summarizes** the artifact, and
4. when warranted, **proposes** an update to the client's distilled long-term **profile** for the advisor to accept/edit/reject.

Over weeks and months the dossier becomes a governed, longitudinal profile the advisor **queries and brainstorms against** before a meeting — with every belief traceable back to a source document.

> Why it's *memory*, not RAG: knowledge **accrues** (every ingest is written + audited), is **consolidated** (distillation), and is **recalled** (semantic search) and **governed** (provenance + audit). That loop is the point. See `docs/requirements.md`.

## Repo map

```
AgentMemory/
├── CLAUDE.md              ← Project context for AI assistants (read this first)
├── docs/
│   ├── requirements.md    ← Product + functional/non-functional requirements
│   ├── architecture.md    ← Databricks architecture (storage triad + ingest/query)
│   ├── decisions.md        ← ADR-style decision log
│   ├── progress.md         ← Status, milestones, open tasks
│   ├── conventions.md      ← Code, commit, branching conventions
│   └── glossary.md         ← Memory taxonomy + domain terms
├── src/agent_memory/       ← Python package: agents, memory, tools, UI
├── databricks/             ← databricks.yml (DABs), app.yaml, Lakebase + Delta schema
├── notebooks/              ← Setup + demo notebooks (the non-expert deploy path)
├── tests/                  ← pytest suite
├── data/synthetic/         ← Synthetic client + dossier-artifact generators
└── .mcp.json               ← Databricks MCP server config
```

## Deploy it (no deep platform expertise required)

The intended path is **DABs + the setup notebooks**:

1. **Configure** — `cp .env.shared .env` and set your workspace values (catalog, schema, profile — comments in `.env.shared` explain each).
2. **Authenticate** — `databricks auth login --profile <your-profile>`.
3. **Deploy infra + app** — from the repo root:
   ```bash
   databricks bundle deploy --target dev
   ```
4. **Provision + seed** — open the `notebooks/` in order (`00_setup_*` → `01_*_synthetic_*` → `99_demo_*`). They create the Lakebase schema, the UC Volume, the Delta profile table, and load synthetic clients + dossier artifacts.
5. **Open the app** — the Databricks App URL from the deploy output.

> **Status:** the docs above describe the **target dossier design**. The implementation is mid-pivot from the v1 turn/session model (milestones M1–M9) to the dossier model — see `docs/progress.md` for exactly what's built vs. pending. Setup commands and notebook names settle as the rewrite lands.

### Local development

```bash
uv sync --extra dev
uv run pytest                  # runs without a workspace
uv run ruff check src/ tests/
./scripts/build_frontend.sh    # build the React bundle
uv run agent-memory-app        # FastAPI app locally (Vite proxies /api in dev)
```

On the Databricks network, `frontend/.npmrc` points at the npm proxy. If `npm install` hangs in an IDE terminal, run `./scripts/build_frontend.sh` from Terminal.app, or `unset npm_config_devdir NPM_CONFIG_DEVDIR` first.

**`openpgp: key expired` during deploy:** Hashicorp's signing key rotated (Apr 2026). Upgrade the CLI (`brew upgrade databricks`, ≥0.295.1) — see [databricks/cli#5022](https://github.com/databricks/cli/issues/5022). Workaround: `export DATABRICKS_TF_EXEC_PATH="$(which terraform)" DATABRICKS_TF_VERSION=1.5.5` before `bundle deploy`.

## Related work

`databricks-industry-solutions/banking-agent-accelerator` is a **complementary** sibling: a deterministic transactional-workflow agent that uses Lakebase as a LangGraph *checkpoint*. It owns the "workflow execution" lane; this project owns the "longitudinal governed memory" lane. See `docs/requirements.md` § Positioning.

## Stakeholders

See `docs/progress.md` for current owners and the FE-IP / Solution Accelerator nomination track.
