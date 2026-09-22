# Agent Memory — Databricks Solution Accelerator

**An AI Wealth Advisor that gives every advisor a full, current, governed picture of every client — so time goes to clients instead of hunting for context, and no opportunity is missed because the firm couldn't see the whole relationship.**

**Industry:** Financial Services — Wealth & Private-Banking Advisory.

## The business problem

Wealth-management firms want to deliver private-banking-quality advice to far more clients than the traditional high-touch model can economically serve. Two things block that, and both trace to one root cause: **advisors rarely have a complete, current picture of the client in front of them.** Context is scattered across CRM notes, PDFs, statements, and email — and across colleagues and months.

**1. Advisor time is burned reassembling context instead of advising.**
Lead advisors spend only ~20% of the work week actually in front of clients, and ~5.3 hours/week just *preparing* for meetings — re-reading notes and documents to reconstruct what the firm already knows.¹ In banking, relationship managers spend only ~25–30% of their time in client dialogue, with administrative and compliance work often consuming more.²

**2. An incomplete client view leaks revenue and retention.**
Clients spread their assets across ~2.3 providers on average, so any one firm typically sees only a fraction of the wallet.³ Only ~17% of high-net-worth clients describe their advisory experience as seamless and personalized, and firms that lack a unified client view see measurably lower share-of-wallet and higher attrition.⁴ Meanwhile 29% of clients intend to switch their primary provider within three years, and "at-risk" clients say they would move ~40% of their assets.³

## The value

A governed, longitudinal client profile the advisor can query in seconds attacks both directly: it collapses meeting prep, and it surfaces the full relationship (held-away signals, life events, stated goals) so nothing suitability-relevant is missed.

> **Illustrative impact** for a mid-size book — **50 advisors, 10,000 clients, ~$5B in client investable assets** (benchmark-based estimate, not a measured customer result):
>
> - **Advisor capacity reclaimed:** replacing manual prep with a 30-second governed briefing recovers a conservative ~2 hrs/advisor/week¹ ≈ **~5,000 advisor-hours/year** redeployed from back-office context-hunting to client-facing advice — roughly **2.5 FTEs** of capacity, at no added headcount.
> - **Revenue recovered:** closing even a **5-point share-of-wallet gap** (a fraction of the observed multi-provider spread³) on $5B of investable assets at a 50 bps fee ≈ **~$1.25M/year** in recurring revenue; the full peer-benchmark gap runs several times higher. Reducing avoidable attrition among the 29% "at-risk" clients³ protects a materially larger base.
>
> *Every firm should re-run this with its own book size, fee rate, and advisor cost — the model is `10,000 × $500k × Δ share-of-wallet × fee bps` for revenue, and `advisors × hrs-saved/week × 46 weeks` for capacity.*

*Sources: ¹ Kitces Research, "How Do Financial Advisors Actually Spend Their Time" (2019). ² McKinsey, "Agentic AI and the bank frontline" (2025). ³ EY Global Wealth Research Report (2025). ⁴ Capgemini World Wealth Report (2026).*

## What it is (and isn't)

It's an **advisor-facing** tool, not a client chatbot (Databricks Apps are internal/workspace-authenticated). The advisor **feeds a client dossier** — meeting notes, scanned statements, PDFs, photos of handwritten notes, typed notes — by drag-and-drop. The agent:

1. saves the original file **unchanged** to a UC Volume (the compliance record),
2. extracts it with **`ai_parse_document`**, then chunks + embeds it into **Lakebase pgvector**,
3. **summarizes** the artifact, and
4. when warranted, **proposes** an update to the client's distilled long-term **profile** for the advisor to accept/edit/reject.

Over weeks and months the dossier becomes a governed, longitudinal profile the advisor **queries and brainstorms against** before a meeting — with every belief traceable back to a source document.

> Why it's *memory*, not RAG: knowledge **accrues** (every ingest is written + audited), is **consolidated** (distillation), and is **recalled** (semantic search) and **governed** (provenance + audit). That loop is the point. See `docs/requirements.md`.

## The end-to-end data journey

The accelerator is a single **integrated** journey — raw client documents in, a business-facing app and natural-language query surface out — spanning the full Databricks platform, not siloed demos:

```
Raw client documents (synthetic)
  →  Lakeflow  (Auto Loader ingest → ai_parse_document → ai_query)
  →  Unity Catalog  (bronze/silver Delta, governed; UC Volume holds immutable raw bytes)
  →  Lakebase  (Postgres + pgvector: live memory, chunks, HITL proposals, audit log)
  →  ML / GenAI  (embeddings + LLM distillation into a governed client profile)
  →  Genie Agent  (natural-language query over the governed tables)
  →  Databricks App  (advisor-facing dossier timeline, profile, brainstorm surface)
```

Committed, text-readable execution evidence for each stage lives in **`evidence/`** (pipeline run IDs + row counts, parsed OCR samples, distilled profiles, and a real Genie transcript).

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
├── evidence/               ← Committed, text-readable execution evidence (run output)
├── tests/                  ← pytest suite
├── data/synthetic/         ← Synthetic client + dossier-artifact generators
└── .mcp.json               ← Databricks MCP server config
```

## Deploy it (no deep platform expertise required)

The intended path is **DABs + the setup notebooks**:

1. **Configure** — `cp .env.example .env` and set your workspace values (catalog, schema, profile — comments in `.env.example` explain each).
2. **Authenticate** — `databricks auth login --profile <your-profile>`.
3. **Deploy infra + app** — from the repo root:
   ```bash
   databricks bundle deploy --target dev
   ```
4. **Provision + seed** — open the `notebooks/` in order (`00_setup_*` → `01_*_synthetic_*` → `99_demo_*`). They create the Lakebase schema, the UC Volume, the Delta profile table, and load synthetic clients + dossier artifacts.
5. **Open the app** — the Databricks App URL from the deploy output.

> **Status:** the dossier model is built and the batch journey below is deployed and verified end-to-end — see `docs/progress.md` for what's built vs. pending and `evidence/` for committed run output.

### Batch bulk-onboarding (Lakeflow)

Alongside the interactive drag-drop, the accelerator ships a **batch** ingest
surface for onboarding a whole book of clients at once (ADR-0019) — the full
Databricks data journey, integrated end to end:

```
UC Volume _landing/  →  Lakeflow pipeline (Auto Loader → ai_parse_document → ai_query)
  →  bronze/silver Delta (Unity Catalog)  →  Lakebase pgvector (hydrate)  →  Delta client_profile (distill)
  →  Genie space (natural-language)  →  Databricks App
```

```bash
uv run python scripts/seed_landing.py --extra-clients 10   # stage synthetic raw files
databricks bundle run dossier_ingest_job --target dev       # pipeline → hydrate → distill
uv run python scripts/setup_genie.py                        # Genie space over the Delta tables
uv run python evidence/generate_evidence.py                 # text-readable execution evidence → evidence/
```

Or run `notebooks/03_bulk_onboard.py` top-to-bottom. See `evidence/` for committed
run output (row counts, parsed OCR samples, distilled profiles, Genie transcript).

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
