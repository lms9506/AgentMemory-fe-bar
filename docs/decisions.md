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
- Memory: **Lakebase (Postgres + pgvector)** for live; **Delta Tables in Unity Catalog** for distilled long-term + time-travel audit
- Orchestration: **LangGraph + LangChain** on the **Mosaic AI Agent Framework**, using the Databricks stateful-agents SDK
- LLM: **Foundation Model API** (no external keys)
- UI: **Databricks Apps**
- Eval/Trace: **MLflow**

**Why.** Everything is Databricks-native, governed by Unity Catalog, deployable via DABs. Eliminates external dependencies and keeps the demo's value proposition coherent: *the lakehouse is the agent platform*. Lakebase autoscaling + automatic OAuth rotation in the stateful-agents SDK is the load-bearing differentiator over a hand-rolled Postgres.

**Consequences.**
- We commit to whatever LangGraph + Mosaic AI ship in the relevant Databricks Runtime
- Any new memory service (Pinecone, Redis, Mem0) requires a new ADR
- Frontend framework choice (React vs Streamlit) is deferred — see open task T6

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
