# Glossary

Memory-system and domain terms. When you add a new concept to the codebase, add it here.

## Memory taxonomy

**Episodic memory** — The raw, time-ordered log of conversation turns. Stored in `conversation_turns` in Lakebase. Append-only. Source of truth for "what was said."

**Semantic memory** — Embeddings of conversation turns, stored in `turn_embeddings` (pgvector). Used for similarity search ("what have we discussed about X?"). Derived from episodic memory.

**Long-term profile** — Distilled, structured knowledge about a client (risk tolerance, goals, family context, preferences). Stored in `client_profile` Delta table in Unity Catalog. Overwritten by the nightly distillation job; prior versions accessible via Delta time travel.

**Shareable memory** — All memory is keyed on `client_id`, not `advisor_id`. Two advisors working with the same client see the same memory. Per-advisor private scratchpads are out of scope for v1.

**Working memory** — The in-context window of the current LangGraph run. Not persisted. Distinct from episodic memory, which is.

**Audit row** — A row in `audit_log` written every time long-term memory is touched. Contains who, what, source turns, timestamp, agent run id.

**Distillation** — The scheduled job that reads recent episodic memory and produces an updated long-term profile. Runs nightly.

**Retrieval** — The act of pulling top-k relevant memory items into the agent's working memory before generation. Scoped by `client_id`.

**Human-in-the-loop edit (HITL edit)** — An advisor accepts, rejects, or modifies a memory item via the UI. The edit is written to memory the same way agent-derived facts are, but flagged `source = human`.

## Domain terms (FINS / Wealth Management)

**Client** — The end customer the wealth advisor serves. Not "user" — "user" refers to the advisor in this repo.

**Advisor** — The wealth-management professional using the AI assistant. The UI "user."

**Suitability assessment** — Regulatory requirement to document that advice given matches the client's risk profile, goals, and circumstances. The memory system is designed to make suitability auditable.

**Portfolio** — The client's current holdings. Synthetic in this repo.

**Session** — One continuous advisor-client interaction. Multiple sessions per client over time.

## Databricks platform terms

**Lakebase** — Databricks-managed Postgres with autoscaling and OAuth rotation, governed by Unity Catalog.

**pgvector** — Postgres extension for vector similarity search. Enabled on Lakebase.

**Mosaic AI Agent Framework** — Databricks runtime for stateful agents.

**Stateful-agents SDK** — Python SDK that wires Lakebase connections with OAuth rotation into LangGraph workflows.

**Foundation Model API (FM API)** — Databricks-hosted LLM endpoints. No external API keys.

**Databricks Apps** — Python apps hosted natively in the Databricks workspace.

**Databricks Asset Bundles (DABs)** — Declarative deployment for jobs, pipelines, apps, models. `databricks.yml` is the config.

**Unity Catalog (UC)** — Databricks governance layer over data + AI assets.

**FE-IP** — Field Engineering Intellectual Property. The internal catalog of demos, accelerators, and reusable IP that SAs maintain.

**Solution Accelerator** — A Databricks-published, industry-anchored reference implementation. Qualification: clear industry tie, current Databricks tech, updated every 6 months, GTM co-owner.
