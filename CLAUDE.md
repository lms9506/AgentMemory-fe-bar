# CLAUDE.md — Project context for AI assistants

> This file is the **entry point** for Claude Code (and Cursor / Copilot if used). Keep it short. The deeper content lives in `docs/`. Update this file whenever the answer to "what would a new collaborator need to know on day one?" changes.

## What this project is

A Databricks Solution Accelerator for **agent memory** in regulated industries, anchored in an **AI Wealth Advisor**.

The app is **advisor-facing and internal** (Databricks Apps are workspace-authenticated — never client-facing). It is *not* a chatbot a client talks to. The advisor **feeds it a client dossier** — meeting notes, scanned statements, PDFs, photos of handwritten notes, the occasional typed note — and over weeks and months the agent distills that dossier into a governed, longitudinal **client profile** the advisor can query and brainstorm against before a meeting.

The unit is the **client dossier** (an append-only stream of dated artifacts), not a chat session.

The "memory" is not a side feature — in wealth management it's a **compliance artifact** (suitability assessments, audit trails, cross-advisor continuity). Frame every design choice through that lens. The technical spine of the story is **Lakebase as the agent-memory store**: artifacts accrue (episodic), are recalled by similarity (semantic, pgvector), and are consolidated into a long-term profile — the accrue → consolidate → recall loop is what makes this *memory*, not RAG over a folder.

## How a dossier item is ingested (the core loop)

Drag-and-drop, **synchronous** (some lag is fine; the UI shows ingestion feedback). Each ingest fires four steps:

1. **Raw save** — the original bytes land **unchanged** in a UC Volume. The legal books-and-records artifact. Immutable.
2. **Extraction** — `ai_parse_document` turns the bytes into text; chunks are embedded into Lakebase pgvector (the retrieval substrate). Plain text skips parsing.
3. **Per-artifact summary** — a summary of just that input, auto-committed (low-stakes). It's the dossier-timeline entry.
4. **Profile delta — if warranted, as a PROPOSAL** — when an artifact justifies a profile change, the agent proposes one; the advisor accepts / edits / rejects (high-stakes + built on fallible OCR → stays human-in-the-loop).

## Stack (load-bearing only)

- **Python 3.10+** — the only application language (floor is 3.10 to match Databricks Serverless compute, which runs 3.10)
- **LangGraph + LangChain** — agent orchestration (ingest pipeline + query graph)
- **Lakebase (Postgres + pgvector)** — agent-memory store: artifacts (episodic) + chunk embeddings (semantic)
- **UC Volumes** — immutable raw-file storage for ingested dossier artifacts
- **`ai_parse_document`** — native Databricks document/OCR extraction (PDF, images, scans)
- **Delta Tables in Unity Catalog** — distilled long-term profile + audit archive (via time travel)
- **Mosaic AI Agent Framework** — agent runtime; uses the Databricks stateful-agents SDK
- **Foundation Model API** — LLM + `databricks-bge-large-en` embeddings (no external API keys)
- **Databricks Apps** — advisor UI (FastAPI + React)
- **MLflow** — eval + tracing
- **Databricks Asset Bundles (DABs)** — deployment (`databricks.yml`)

Anything outside this list needs an ADR in `docs/decisions.md`.

## Where to look first

| If you're about to… | Read |
|---|---|
| Understand the product | `docs/requirements.md` |
| Understand the system | `docs/architecture.md` |
| Pick up work | `docs/progress.md` |
| Make a non-trivial design choice | `docs/decisions.md` (add a new ADR) |
| Name a memory concept | `docs/glossary.md` |
| Open a PR | `docs/conventions.md` |

## House rules for AI assistants

1. **Prefer editing over creating.** Don't add a new module if an existing one fits. Don't add a new doc if a section in an existing doc fits.
2. **No silent scope creep.** Bug fixes don't get refactors. One-shot tasks don't get helper modules. Found a real adjacent issue? Open a follow-up in `docs/progress.md` — don't bundle.
3. **Memory is a compliance artifact.** Every write to long-term memory needs a corresponding audit row. Every profile field traces to the artifact(s) that justified it. Don't optimize away the audit trail or the provenance.
4. **Lakebase = live memory; Delta = archived profile; UC Volume = raw bytes.** Three tiers, don't blur them.
5. **No external services.** No Pinecone, Redis, Mem0; no external OCR/LLM. We showcase the Databricks-native path. New dependencies need an ADR.
6. **Synthetic data only.** Real client data never goes near this codebase. Generators live in `data/synthetic/`.
7. **MLflow traces on every agent run.** Don't add code paths that bypass tracing.
8. **Deployable by a non-expert.** The target user clones, configures, and runs `databricks bundle deploy` + the setup notebooks — no deep technical knowledge required. Keep the structure legible and the happy path short.
9. **Update `docs/progress.md` when you start and finish a task.**
10. **Don't push to `main`.** Branch + PR. See `docs/conventions.md`.

## Related work

`databricks-industry-solutions/banking-agent-accelerator` is a sibling FINS agent accelerator. It is a **deterministic transactional-workflow agent** and uses Lakebase only as a LangGraph **checkpoint** — it has no semantic recall, no distillation, no long-term profile, no document ingestion. It is **complementary**: it owns the "workflow execution" lane, this project owns the "longitudinal governed memory" lane. See `docs/requirements.md` § Positioning.

## MCP tools available

This repo configures **only the Databricks MCP server** (see `.mcp.json`). Use it for Lakebase / UC queries, job + pipeline state, running notebooks, workspace file ops. Need a capability outside Databricks MCP? Ask before adding another server — we keep the MCP surface small.

## Quick commands

```bash
uv sync --extra dev                     # install deps
uv run pytest                           # run tests (no workspace needed)
uv run ruff check src/ tests/           # lint
databricks bundle deploy --target dev   # from repo root (databricks.yml)
```

## Out of scope (don't build these without an ADR)

- A generic cross-industry "memory framework" — this is the FINS accelerator, not a library
- A custom vector index — pgvector is the choice
- A client-facing surface — the app is advisor-internal only
- A non-Databricks UI — React inside Databricks Apps only
- The agent giving advice — it surfaces considerations and what the file says; the advisor is the fiduciary
- Multi-tenant SaaS hosting — this is reference code, not a product
