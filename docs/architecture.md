# Architecture

The accelerator is Databricks-native end to end. Memory lives in three governed tiers, fed by a synchronous ingest pipeline and read by a query/brainstorm agent.

## The storage triad

| Tier | Home | Holds | Role |
|---|---|---|---|
| **Raw bytes** | **UC Volume** | the original uploaded files, unchanged | immutable books-and-records artifact |
| **Live memory** | **Lakebase (Postgres + pgvector)** | artifacts (episodic) + chunk embeddings (semantic) + current profile pointer + audit + proposals | the agent-memory store, hot path |
| **Archive** | **Delta (Unity Catalog)** | immutable distilled-profile versions | point-in-time "what did we believe on date T?" via time travel |

**Invariant:** Lakebase = live, Delta = archived, Volume = raw. Don't query Delta in the hot path; don't write Delta from the agent directly (only distillation writes it).

## 1. Ingest pipeline (synchronous)

The advisor drops a file into the app. The request runs four steps and returns once the summary + any proposal are ready (some lag is acceptable; the UI shows progress):

```
upload ──▶ 1. raw save (UC Volume) + content hash  ──▶ dedup check
       └─▶ 2. ai_parse_document → extracted text → chunk → embed → Lakebase pgvector
       └─▶ 3. summarize this artifact → Lakebase (timeline entry)
       └─▶ 4. distill (if new content) → propose profile delta → profile_proposals
```

- **Step 1 — raw save.** Bytes go to `/Volumes/<catalog>/<schema>/dossier_raw/<client_id>/<artifact_id>.<ext>`. A SHA-256 of the bytes is the dedup key; a re-upload of identical bytes short-circuits.
- **Step 2 — extraction.** `ai_parse_document` (PDF, images, scans). Plain text skips parsing; `.docx` may pre-convert to PDF. Extracted text is chunked and embedded with `databricks-bge-large-en` (1024-d) into pgvector.
- **Step 3 — summary.** An LLM summary of just this artifact, auto-committed. Low-stakes.
- **Step 4 — profile delta.** Triggered distillation runs *if* this client has new artifacts since its last distillation; the result is a **proposal**, not a commit (FR-6). High-stakes → human-in-the-loop.

## 2. Lakebase (Postgres + pgvector) — live memory store

Source of truth for *live* memory. Governed by Unity Catalog; autoscaling + automatic OAuth rotation via the stateful-agents SDK; sits inside the lakehouse (no egress, no extra credentials).

**Target tables** (see `databricks/lakebase_schema.sql`):

| Table | Purpose | Key columns |
|---|---|---|
| `artifacts` | Episodic memory — one row per ingested dossier item | `artifact_id`, `client_id`, `advisor_id`, `kind`, `original_filename`, `volume_path`, `content_hash`, `extracted_text`, `summary`, `sensitivity_tags`, `ingested_at` |
| `artifact_chunks` | Semantic memory — pgvector recall | `artifact_id`, `client_id`, `chunk_index`, `content`, `embedding vector(1024)` |
| `audit_log` | Every memory write, incl. HITL actions | `event_id`, `actor`, `actor_kind`, `action`, `target_ref`, `payload`, `agent_run_id`, `ts` |
| `profile_proposals` | Distilled profiles pending advisor review | `proposal_id`, `client_id`, `proposed_profile`, `source_artifact_ids`, `status`, `reviewed_by` |
| `clients` | Client registry (display names) | `client_id`, `display_name` |

> **Migration note:** v1 shipped a turn/session schema (`conversation_turns`, `turn_embeddings`, `source_turn_ids`). The dossier model replaces it with `artifacts` / `artifact_chunks` / `source_artifact_ids`. Tracked in `docs/progress.md`.

## 3. Delta Tables (Unity Catalog) — long-term profile archive

`client_profile` holds the current distilled view per client (risk tolerance, goals, family, preferences, summary, `source_artifact_ids`). Each accepted proposal is a new Delta version; prior versions are reachable via **Delta time travel** — the compliance answer to "what did we believe on date T?" without duplicating narrative audit payloads (see ADR on audit). See `databricks/delta_schema.sql`.

## 4. Mosaic AI Agent Framework — orchestration

- **LangGraph** drives two graphs:
  - *Ingest* — `raw_save → extract → embed → summarize → (maybe) propose`
  - *Query* — `retrieve (pgvector, client-scoped) → generate (grounded, advice-bounded) → stream`
- **LangChain** provides the tool/retriever layer.
- The **stateful-agents SDK** wires Lakebase with OAuth rotation.
- **Foundation Model API** is the LLM + embedding endpoint (no external keys; model choices in `docs/decisions.md`).

## 5. Databricks Apps — advisor UI

FastAPI backend + React (TypeScript) SPA, hosted inside Databricks (zero infra for the customer). Panels:
- **Dossier timeline** — artifacts with summaries, raw-file links, "contributed to profile?" badges
- **Query / brainstorm** — natural-language Q&A over the dossier (advice-bounded)
- **Retrieval inspector** — what the agent pulled, with relevance scores
- **Distilled profile** — fields with clickable per-field provenance + HITL proposal review

## 6. MLflow — evaluation + tracing

- **Tracing:** every agent run (ingest and query) logs spans to MLflow Tracing.
- **Eval:** retrieval eval (did top-k surface the gold artifact?) + response eval (LLM-as-judge: grounding, suitability framing, tone, advice-boundary adherence). Runs in CI on `src/agent_memory/` changes.

## Data flow (one sentence)

> Advisor drops an artifact → it's saved raw to a UC Volume, parsed by `ai_parse_document`, chunked + embedded into Lakebase pgvector, and summarized → if new content exists, distillation proposes a profile delta the advisor reviews → accepted profiles version into Delta with an audit row → later, the advisor queries the dossier and the agent retrieves client-scoped memory to answer, grounded and advice-bounded.

## Sequence

```
┌─────────┐  drop file  ┌────────────┐   ┌──────────────┐   ┌──────────┐  ┌──────────┐
│ Advisor │────────────▶│ Apps (FE)  │──▶│   LangGraph  │──▶│ UC Volume│  │ Lakebase │
│   UI    │             │  + FastAPI │   │ ingest graph │   │ (raw)    │  │ +pgvector│
└─────────┘             └────────────┘   └──────────────┘   └──────────┘  └──────────┘
     ▲                                          │  ai_parse_document            │
     │   summary + proposal                     │  embed chunks ────────────────▶│
     │◀─────────────────────────────────────────                                │
     │                                          │  propose profile delta         │
     │   review proposal (accept/edit/reject)   │───────────────▶ profile_proposals
     │                                                                            │
     │   query dossier                          ┌──────────────┐   accept ──▶ ┌──────┐
     └─────────────────────────────────────────▶│ query graph  │── version ──▶│ Delta│
                                                 │ retrieve→gen │   + audit    │profile│
                                                 └──────────────┘              └──────┘
```

## Repository structure

```
src/agent_memory/
├── agents/        ← LangGraph graphs (ingest + query), system prompts
├── memory/        ← Lakebase clients, retrievers, extraction, distillation
├── tools/         ← LangChain tools the agent can call
└── ui/            ← Databricks App backend + React frontend

databricks/        ← databricks.yml (DABs), app.yaml, lakebase_schema.sql, delta_schema.sql
notebooks/         ← Setup + demo notebooks (the non-expert deploy path; read by humans)
tests/             ← pytest suite
data/synthetic/    ← Synthetic client + dossier-artifact generators
```

## Key invariants (don't break these)

1. **Lakebase = live, Delta = archived, Volume = raw.** Don't query Delta in the hot path; only distillation writes Delta.
2. **Every long-term write has an audit row, and every profile field has provenance.** No exceptions.
3. **The agent never reads cross-client memory.** Retrievers are always scoped by `client_id`.
4. **The agent never gives advice.** Considerations and what-the-file-says only.
5. **No PII in the repo.** Synthetic only.
6. **MLflow trace on every agent run.** No silent paths.
