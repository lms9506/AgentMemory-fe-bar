# Progress

> Single source of truth for "what is happening right now." Update on task start *and* finish. Convert relative dates to absolute. Keep dead entries — move them to `## Done`, don't delete.

**Last updated:** 2026-05-19

## North star

Ship a Databricks Solution Accelerator: *AI Wealth Advisor with persistent client memory*. Target: FE-IP entry + Industry GTM sign-off by **2026-Q3**.

## Active phase: Implementation

Architecture, requirements, and ADRs are settled. Building toward M4 (stack wiring) and M3 (schema + synthetic data).

## Stakeholders

| Role | Person | Status |
|---|---|---|
| Project lead | Michael Egli | active |
| Co-developer | Linus | active |
| FINS Industry GTM (target co-owner) | Antoine Amend *or* David Hackett | to ping 2026-05-12 |
| Lakebase adoption sponsor | Ryan DeCosmo, Lu Wang | informed via #agent-memory |
| Memory PM context | (from #agents — Zillow Oct 2025 ask) | reference only |

## Milestones

- [x] **M0** — Industry + use case decision: Financial Services / Wealth Advisor *(done 2026-05)*
- [x] **M1** — Repo created, context-engineering scaffold landed *(done 2026-05-12)*
- [ ] **M2** — FINS SA co-owner committed (Antoine or David)
- [x] **M3** — Lakebase schema + synthetic data generator merged *(done 2026-05-19)*
- [ ] **M4** — Single-turn agent end-to-end (no memory) — proves stack wiring *(in progress)*
- [ ] **M5** — Episodic memory + pgvector retrieval working
- [ ] **M6** — Distillation job + Delta profile working
- [ ] **M7** — Databricks App UI with all four panels
- [ ] **M8** — MLflow eval harness in CI
- [ ] **M9** — Human-in-the-loop edits
- [ ] **M10** — FE-IP entry submitted
- [ ] **M11** — Solution Accelerator nomination submitted

## Open tasks

| # | Owner | Task | Blocked by |
|---|---|---|---|
| T1 | Michael | Ping Antoine Amend / David Hackett with SA proposal doc, set meeting for week of 2026-05-18 | — |
| T5 | Linus | Validate skeleton LangGraph agent against live FM API in dev workspace (M4) | `.env` + workspace |
| T8 | unassigned | Apply `lakebase_schema.sql` to dev Lakebase via DAB | dev workspace |
| T9 | unassigned | Lakebase client module + episodic write path (M5) | T8 |

## Decisions pending

(none)

## Done

- 2026-05-12 — M0 industry/use case decided (FINS Wealth Advisor) — see `decisions.md` ADR-0001
- 2026-05-12 — M1 repo scaffolded with context-engineering setup
- 2026-05-12 — ADR-0003 (React + FastAPI Apps UI), ADR-0004 (`databricks-bge-large-en`), ADR-0005 (Lakebase audit + Delta time travel)
- 2026-05-19 — M3: `lakebase_schema.sql` + synthetic generator (`src/agent_memory/synthetic/`, `uv run agent-memory-synthetic`)
- 2026-05-19 — M4 scaffold: LangGraph single-turn agent (`src/agent_memory/agents/`), CI-tested with fake LLM
