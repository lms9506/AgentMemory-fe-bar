# Decisions (ADRs)

Architectural Decision Records, newest first. Add an entry whenever you make a non-trivial choice that future-you would want to understand.

**Format:** Each ADR is short — *Context → Decision → Consequences*. If you need more than half a page, you're overthinking it.

---

## ADR-0001 — Industry & use case: Financial Services / Wealth Advisor

**Date:** 2026-05-12
**Status:** Accepted

**Context.** The Agent Memory accelerator needs a concrete industry and use case to qualify as a Databricks Solution Accelerator (clear industry tie required). Candidates considered: FINS (wealth management), Healthcare (patient continuity), Retail (loyalty agent).

**Decision.** Financial Services — AI Wealth Advisor with persistent client memory.

**Why:**
- Documented demand: #agents channel (Zillow, Oct 2025) explicitly asked for managed agent memory; Lakebase single-thread example called out as insufficient
- Memory is *regulatory*, not UX — suitability + audit are compliance requirements, not nice-to-haves
- Strongest GTM bench: Junta Nakai, Antoine Amend, David Hackett, Anindita Mahapatra, Tina Harkness
- No existing FINS agent-memory accelerator (SherlockAML is AML detection, not memory)
- Aligned with the Lakebase adoption push (Ryan DeCosmo, Lu Wang)
- FY27 Industry Outcome Map frames FINS as entering the agentic era

**Consequences.** All domain modeling (client, portfolio, suitability, advisor) is FINS-flavored. Forks for other industries are expected later. We need an Industry GTM co-owner (Antoine or David) to mitigate the 6-month archive risk.

---

## ADR-0002 — Stack: Lakebase + LangGraph + Mosaic AI + Apps + MLflow

**Date:** 2026-05-12
**Status:** Accepted

**Context.** We need to choose memory storage, agent orchestration, LLM, UI hosting, and eval tooling.

**Decision.**
- Memory: **Lakebase (Postgres + pgvector)** for live; **Delta Tables in Unity Catalog** for distilled long-term profiles (time-travel snapshots; see ADR-0005 for audit event log vs profile history)
- Orchestration: **LangGraph + LangChain** on the **Mosaic AI Agent Framework**, using the Databricks stateful-agents SDK
- LLM: **Foundation Model API** (no external keys)
- UI: **Databricks Apps**
- Eval/Trace: **MLflow**

**Why.** Everything is Databricks-native, governed by Unity Catalog, deployable via DABs. Eliminates external dependencies and keeps the demo's value proposition coherent: *the lakehouse is the agent platform*. Lakebase autoscaling + automatic OAuth rotation in the stateful-agents SDK is the load-bearing differentiator over a hand-rolled Postgres.

**Consequences.**
- We commit to whatever LangGraph + Mosaic AI ship in the relevant Databricks Runtime
- Any new memory service (Pinecone, Redis, Mem0) requires a new ADR
- Frontend stack is fixed in ADR-0003 (supersedes the former T6 deferral)

---

## ADR-0003 — Advisor UI: React frontend + FastAPI backend in Databricks Apps

**Date:** 2026-05-12
**Status:** Accepted

**Context.** FR-7 calls for four UI panels (transcript, retrieval inspector, profile, HITL). ADR-0002 listed Apps without a frontend choice; `databricks/app.yaml` already targets a Python module server.

**Decision.** Ship the **wealth advisor** Databricks App as **FastAPI** (`agent_memory.ui.server`) serving a **React** (TypeScript) SPA for the browser UI, bundled as static assets alongside the backend.

**Why.** Multi-panel, streaming-friendly layouts and component reuse fit the accelerator’s “advisor console” story better than Streamlit’s page model. Streamlit is faster for one-off internal demos but weaker for a polished, navigable multi-surface HITL workflow. FastAPI matches the existing `app.yaml` command and keeps auth and SSE/WebSocket patterns explicit.

**Consequences.** Frontend build step enters the DAB/App packaging path (document in `docs/conventions.md` when CI is wired). **Streamlit is out of scope for the shipped App**; it was removed from the optional `app` extra in `pyproject.toml`.

---

## ADR-0004 — Embeddings: Foundation Model API `databricks-bge-large-en` (1024-d)

**Date:** 2026-05-12
**Status:** Accepted

**Context.** Semantic recall needs a Databricks-hosted embedding model (NFR: no external APIs). `turn_embeddings.embedding` is `VECTOR(1024)` in `databricks/lakebase_schema.sql`.

**Decision.** Use **`databricks-bge-large-en`** via **Foundation Model APIs** for all turn and query embeddings used in pgvector retrieval.

**Why.** Documented **1024-dimensional** output matches the schema without migration. BGE Large (En) is English-only for v1 (matches NFR: English-only UI). Normalized embeddings pair cleanly with cosine distance (`vector_cosine_ops` index). **`databricks-gte-large-en`** (also 1024-d) remains the documented alternative if retrieval eval favors it — switching models requires an ADR and a re-embedding plan.

**Consequences.** Code and eval fixtures assume 1024-d vectors. Instruction-style query prefixing (“Represent this sentence for searching relevant passages:”) may be adopted later per model guidance; document in retrieval module when implemented.

---

## ADR-0005 — Audit trail: Lakebase event log + Delta profile time travel

**Date:** 2026-05-12
**Status:** Accepted

**Context.** FR-5 requires an append-only audit of long-term memory writes with actor, change, source turns, timestamp, and agent run id. Live writes hit Lakebase first; distilled profiles live in Delta with time travel. Options: audit only in Lakebase, only in Delta, or split.

**Decision.**
- **Lakebase `audit_log`** is the **append-only system of record for audit events** — every memory-side effect (new turn, new embedding, advisor HITL action, distillation job completion) emits one row with `payload` carrying enough detail to reconstruct *what happened* (including pointers to Delta table identifier + version when a profile upsert completes).
- **Delta `client_profile`** (and optional history table) provides **immutable snapshot history** of the distilled profile via **Delta time travel** — the compliance answer to “what did we believe about this client on date *T*?” without duplicating full narrative audit payloads in UC.

**Why.** One operational log next to live data keeps hot-path and incident tooling simple; Delta remains optimized for profile shape and versioning. Duplicating the same JSON into a second Delta-only audit table was rejected as redundant for v1.

**Consequences.** The distillation job must append a Lakebase `audit_log` row on successful profile upsert. Access control: Lakebase roles restrict UPDATE/DELETE on `audit_log` (already noted in `lakebase_schema.sql`). Changing to a Delta-native-only audit stream would require a new ADR.

---

## ADR template (copy when adding a new one)

```
## ADR-XXXX — Short title

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Superseded by ADR-YYYY

**Context.** What forces are at play? What problem are we solving?

**Decision.** What did we choose? Be specific.

**Why.** The reasoning — including alternatives considered and why we rejected them.

**Consequences.** What does this lock us into? What follow-up work does it create?
```
