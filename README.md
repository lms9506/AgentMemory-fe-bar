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
├── databricks.yml          ← DABs bundle (provisions Lakebase + warehouse + App + jobs)
├── .env.example            ← copy to .env; the single config source
├── src/agent_memory/       ← Python package: agents, memory, tools, UI
├── databricks/             ← Lakebase + Delta schema SQL
├── notebooks/              ← Setup + demo notebooks (the non-expert deploy path)
├── tests/                  ← pytest suite
├── data/synthetic/         ← Synthetic client + dossier-artifact generators
└── .mcp.json               ← Databricks MCP server config
```

## Deploy it on a fresh workspace

The bundle **provisions its own infrastructure** — the Lakebase instance and the SQL
warehouse are created by `bundle deploy`, not prerequisites you stand up first. The
only thing you configure by hand is a catalog and which CLI profile to use.

**Prerequisites:** the `databricks` CLI (≥ 0.295.1), [`uv`](https://docs.astral.sh/uv/),
and Node/npm (to build the React UI). A Unity Catalog **catalog** you can create a
schema in, and the Foundation Model endpoints `databricks-meta-llama-3-3-70b-instruct`
+ `databricks-gte-large-en` available in your workspace (default in most regions).

1. **Authenticate** — `databricks auth login --profile <your-profile>`.
2. **Configure (one file)** — `cp .env.example .env`, then set `DATABRICKS_PROFILE`
   and `UC_CATALOG` (everything else has sane defaults). This is the single source of
   truth; the deploy script feeds it into the bundle and writes the provisioned ids
   back into it.
3. **Deploy** — from the repo root:
   ```bash
   ./scripts/deploy_bundle.sh dev
   ```
   This builds the UI + wheel, deploys the bundle (Lakebase instance, SQL warehouse,
   the App, and the nightly jobs), and applies the service-principal grants.
4. **Set up + seed** — open the `notebooks/` in order and **Run all**:
   `00_setup` (Lakebase schema, UC Volume, Delta table, SP grants) → `01_seed` (three
   demo client dossiers, mixed formats, backdated history) → `02_demo` (walks the four
   UI panels). They derive everything from their own location — nothing to edit.
5. **Open the app** — the URL printed at the end of the deploy.

> **Note:** deploying to a target creates a Lakebase instance named
> `agent-memory-<target>`. Switching an existing deployment to this bundle means the
> new instance starts empty — re-run `00_setup` + `01_seed` to reseed.

See `docs/progress.md` for current build status and `docs/decisions.md` (ADR-0016) for
why the infra is bundle-provisioned.

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
