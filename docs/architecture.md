# Architecture

The accelerator is composed of five Databricks-native layers. Nothing external.

## 1. Lakebase (Postgres + pgvector) — Live memory store

**Role:** Source of truth for *live* memory — both raw conversation turns (episodic) and their vector embeddings (semantic).

**Tables (see `databricks/lakebase_schema.sql`):**

| Table | Purpose | Key columns |
|---|---|---|
| `conversation_turns` | Append-only conversation log | `turn_id`, `client_id`, `advisor_id`, `session_id`, `role`, `content`, `ts` |
| `turn_embeddings` | pgvector index for semantic recall | `turn_id`, `embedding vector(1024)` |
| `audit_log` | Every memory write, including human edits | `event_id`, `actor`, `action`, `target_ref`, `payload_json`, `ts` |

**Why Lakebase (vs. a generic Postgres):**
- Governed by Unity Catalog
- Autoscaling + automatic OAuth rotation via the Databricks stateful-agents SDK
- Sits inside the lakehouse — no network egress, no extra credentials

## 2. Delta Tables (Unity Catalog) — Long-term profile + audit archive

**Role:** Distilled, structured client knowledge. Time-travel is the compliance audit trail.

**Tables:**

| Table | Purpose |
|---|---|
| `client_profile` | Current distilled view per client (risk tolerance, goals, family, preferences) — overwritten on each distillation run; prior versions accessible via Delta time travel |
| `client_profile_history` | Optional materialized history view for advisor UI ("how has this profile evolved?") |

A **nightly distillation job** (Databricks Workflow) reads the last N days of `conversation_turns`, runs an LLM summarizer, and upserts `client_profile`. Every upsert is a new Delta version.

## 3. Mosaic AI Agent Framework — Orchestration

**Role:** The agent runtime.

- **LangGraph** drives the stateful workflow:
  ```
  user_input → retrieve_memory → generate → write_memory → stream_response
  ```
- **LangChain** provides the tool-calling layer and retrievers
- The Databricks **stateful-agents SDK** wires Lakebase connections with OAuth rotation
- **Foundation Model API** is the LLM (no external keys; model choice in `docs/decisions.md`)

The agent is deployed as a Databricks Model Serving endpoint (registered via MLflow).

## 4. Databricks Apps — Advisor UI

**Role:** The demo surface — what customers see.

- Python backend (FastAPI or the Apps default) → calls the Model Serving endpoint
- Frontend: React or Streamlit (TBD in `docs/decisions.md`)
- Panels: live transcript, retrieved-memory inspector, distilled-profile viewer, human-in-the-loop edit form
- Hosted entirely inside Databricks — zero infrastructure for the customer

## 5. MLflow — Evaluation + Tracing

**Role:** What makes this a "credible 50% solution" — customers can run evals before going to production.

- **Tracing:** Every agent run logs spans (retrieve → generate → write) to MLflow Tracing
- **Eval:** Two suites
  - *Retrieval eval* — given a query and a labeled gold memory, did we surface it in top-k?
  - *Response eval* — LLM-as-judge on synthetic client scenarios, scoring grounding, suitability framing, and tone
- Eval runs in CI on `src/agent_memory/` changes

---

## Data flow (one sentence)

> Client message → LangGraph agent → reads episodic + semantic memory from Lakebase via pgvector → generates response grounded in client history → writes new episodic memory to Lakebase + audit row → nightly distillation job updates the Delta Table client profile.

## Sequence

```
┌─────────┐   ┌─────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────┐
│ Advisor │──▶│ Apps Front  │──▶│  LangGraph   │──▶│   Lakebase   │   │  Delta   │
│   UI    │   │   (Python)  │   │    Agent     │   │  + pgvector  │   │ Profile  │
└─────────┘   └─────────────┘   └──────────────┘   └──────────────┘   └──────────┘
                                       │  retrieve top-k │                  ▲
                                       │◀────────────────│                  │
                                       │                                    │
                                       │   FM API (generate)                │
                                       │                                    │
                                       │  append turn + audit               │
                                       │────────────────▶│                  │
                                       │                                    │
                                       │                                    │  nightly
                                       │                                    │ distillation
                                       │                                    │  (Workflow)
                                       └────────────────────────────────────┘
```

## Repository structure

```
src/agent_memory/
├── agents/        ← LangGraph graph definitions, system prompts
├── memory/        ← Lakebase clients, retrievers, distillation logic
├── tools/         ← LangChain tools the agent can call
└── ui/            ← Databricks App backend + frontend bridge

src/jobs/         ← Distillation workflow entry points
databricks/       ← databricks.yml (DABs), app.yaml, lakebase_schema.sql
notebooks/        ← Demo + exploration notebooks (read by humans, not imported)
tests/            ← pytest suite
data/synthetic/   ← Dummy client + portfolio generators
```

## Key invariants (don't break these)

1. **Lakebase = live, Delta = archived.** Don't query Delta in the hot path. Don't write to Delta from the agent directly — only the distillation job writes.
2. **Every long-term write has an audit row.** No exceptions.
3. **The agent never reads cross-client memory.** Retrievers are always scoped by `client_id`.
4. **No PII in the repo.** Synthetic only.
5. **MLflow trace on every agent run.** No silent paths.
