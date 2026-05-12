# Requirements

## Vision

Deliver a **Databricks Solution Accelerator** that demonstrates governed, durable agent memory for regulated industries, anchored in a Financial Services Wealth Advisor scenario. The accelerator should let a customer team go from zero to a working PoC in under two weeks.

## Personas

| Persona | Goal | Pain |
|---|---|---|
| **Wealth advisor** | Pick up a client conversation in 30s, regardless of who spoke to them last | Re-reading CRM notes; losing context across sessions |
| **Compliance officer** | Prove every advice given was suitable, with an auditable trail | Black-box agents; no traceable memory state |
| **Databricks SA (accelerator user)** | Stand up the demo against their own workspace in <2 weeks | Generic memory demos that ignore governance |

## Functional requirements

### FR-1 — Episodic memory
The agent persists every client conversation turn to **Lakebase** with: `client_id`, `advisor_id`, `session_id`, `turn_index`, `role`, `content`, `timestamp`. Conversations are queryable by client and time range.

### FR-2 — Semantic memory (vector recall)
Conversation turns are embedded and stored in a **pgvector** index in Lakebase. The agent can retrieve top-k similar past turns for a given query ("what have we discussed about retirement?").

### FR-3 — Long-term semantic profile
A scheduled distillation job reads recent episodic memory and updates a **Delta Table** in Unity Catalog with a structured client profile: risk tolerance, investment goals, family context, stated preferences. Each update is a new Delta version (time-travel audit).

### FR-4 — Shareable memory
Two advisors working with the same client see the same memory state. Memory is keyed on `client_id`, not `advisor_id`. Per-advisor private scratchpad is out of scope for v1.

### FR-5 — Audit trail
Every write to long-term memory emits a row to an `audit_log` table (Lakebase or Delta — see ADR) with: `who`, `what changed`, `source turns`, `timestamp`, `agent run id`. The audit log is append-only.

### FR-6 — Human-in-the-loop memory edits
The advisor UI surfaces "the agent thinks X about this client." The advisor can confirm, reject, or edit. Edits write to memory the same way agent-derived facts do, but flagged `source = human`.

### FR-7 — Advisor-facing app
A **Databricks App** (Python backend, React or Streamlit frontend — TBD in ADR) shows:
- Live conversation transcript
- Currently-retrieved memory snippets (with relevance scores)
- The distilled client profile (with last-updated, source attribution)
- A "memory edit" panel for human-in-the-loop

### FR-8 — Evaluation harness
**MLflow**-tracked eval suite scoring (a) retrieval recall against labeled gold memories and (b) response quality on synthetic client scenarios. Runs in CI on every PR that touches `src/agent_memory/`.

### FR-9 — Streaming responses
The agent streams tokens to the UI. Memory retrieval happens before generation; memory writes happen after.

## Non-functional requirements

### NFR-1 — Databricks-native
No external services for memory, vector search, LLM, or hosting. Everything inside the Databricks platform. New dependencies require an ADR.

### NFR-2 — Reproducible deployment
A new SA clones the repo, runs `databricks bundle deploy --target <their-workspace>`, and has a working demo. All infra in DABs; no manual UI clicks required.

### NFR-3 — Synthetic data only
Repo ships with a generator for synthetic clients, portfolios, and conversation seeds. Real client PII never enters the repo or the demo workspaces.

### NFR-4 — Lakebase autoscaling
Production-shaped — autoscaling on, OAuth credential rotation via the stateful-agents SDK.

### NFR-5 — Solution Accelerator qualification
To qualify as a Databricks Solution Accelerator:
- Clear industry tie (Financial Services — Wealth Management)
- Uses current Databricks tech (Lakebase, Mosaic AI Agent Framework, Apps, MLflow)
- Updated at least every 6 months
- Industry GTM co-owner identified and signed off (see `docs/progress.md`)

### NFR-6 — Documentation
Every public-facing function has a docstring. Every architectural decision has an ADR. The repo README + `docs/` are sufficient onboarding without verbal tribal knowledge.

## Out of scope (v1)

- Per-advisor private memory (only shareable client memory)
- Real-time multi-agent collaboration on the same client session
- Multi-language UI (English only)
- Non-FINS industry adaptations (keep accelerator focused; clones can fork)
- Custom fine-tuned embedding models — use the Databricks default
- Mobile UI
