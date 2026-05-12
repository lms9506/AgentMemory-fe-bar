# Progress

> Single source of truth for "what is happening right now." Update on task start *and* finish. Convert relative dates to absolute. Keep dead entries — move them to `## Done`, don't delete.

**Last updated:** 2026-05-12

## North star

Ship a Databricks Solution Accelerator: *AI Wealth Advisor with persistent client memory*. Target: FE-IP entry + Industry GTM sign-off by **2026-Q3**.

## Active phase: Scoping & Definition

Repo just initialized. Architecture and requirements are drafted (see `architecture.md`, `requirements.md`). Next focus: industry co-owner sign-off, then implementation.

## Stakeholders

| Role | Person | Status |
|---|---|---|
| Project lead | Michael Egli | active |
| Co-developer | Linus | invited; needs repo access |
| FINS Industry GTM (target co-owner) | Antoine Amend *or* David Hackett | to ping 2026-05-12 |
| Lakebase adoption sponsor | Ryan DeCosmo, Lu Wang | informed via #agent-memory |
| Memory PM context | (from #agents — Zillow Oct 2025 ask) | reference only |

## Milestones

- [x] **M0** — Industry + use case decision: Financial Services / Wealth Advisor *(done 2026-05)*
- [x] **M1** — Repo created, context-engineering scaffold landed *(done 2026-05-12)*
- [ ] **M2** — FINS SA co-owner committed (Antoine or David)
- [ ] **M3** — Lakebase schema + synthetic data generator merged
- [ ] **M4** — Single-turn agent end-to-end (no memory) — proves stack wiring
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
| T2 | Michael | Share repo with Linus + grant write access | — |
| T3 | Linus | Draft `databricks/lakebase_schema.sql` (tables in `architecture.md` §1) | T2 |
| T4 | unassigned | Generate synthetic client + portfolio data in `data/synthetic/` | T3 |
| T5 | unassigned | Skeleton LangGraph agent that calls FM API, no memory yet (M4) | T2 |
| T6 | unassigned | Decide React vs Streamlit for Apps UI — write ADR | — |
| T7 | unassigned | Decide embedding model — write ADR | — |

## Decisions pending

- React vs Streamlit for the advisor UI (T6 → ADR)
- Embedding model choice (T7 → ADR)
- Audit log location: Lakebase table vs Delta table vs both → ADR

## Done

- 2026-05-12 — M0 industry/use case decided (FINS Wealth Advisor) — see `decisions.md` ADR-0001
- 2026-05-12 — M1 repo scaffolded with context-engineering setup
