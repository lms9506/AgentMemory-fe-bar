# Decisions (ADRs)

Architectural Decision Records for the **current** design. This log was rewritten on 2026-06-04 when the project pivoted from a client-chatbot/turn model to the advisor-fed **dossier** model; it reflects what we build now, not the superseded history.

**Format:** each ADR is short — *Context → Decision → Why → Consequences*. More than half a page means you're overthinking it.

---

## ADR-0001 — Industry & use case: Financial Services / Wealth Advisor

**Date:** 2026-05-12 · **Status:** Accepted

**Context.** The accelerator needs a concrete industry to qualify as a Databricks Solution Accelerator. Candidates: FINS (wealth management), Healthcare (patient continuity), Retail (loyalty).

**Decision.** Financial Services — AI Wealth Advisor with persistent client memory.

**Why.** Documented demand (#agents channel, Zillow Oct 2025, asked for *managed* agent memory and called the Lakebase single-thread checkpoint example *insufficient*); memory here is *regulatory* (suitability + audit), not UX; strong GTM bench (Junta Nakai, Antoine Amend, David Hackett, Anindita Mahapatra, Tina Harkness); no existing FINS agent-memory accelerator. The sibling `banking-agent-accelerator` later confirmed the gap — it uses Lakebase as a checkpoint and has no managed memory (see `requirements.md` § Positioning).

**Consequences.** All domain modeling is FINS-flavored. Needs an Industry GTM co-owner (Antoine or David) to mitigate the 6-month archive risk.

---

## ADR-0002 — The dossier model: advisor-fed artifacts, not a client chatbot

**Date:** 2026-06-04 · **Status:** Accepted

**Context.** Databricks Apps are workspace-authenticated — they cannot be client-facing. A chatbot a client talks to was never deployable. Advisors also don't record sensitive client conversations; their notes, scans, and documents are the real system of record.

**Decision.** The app is **advisor-facing**. The advisor feeds a **client dossier** — an append-only stream of dated artifacts (notes, PDFs, statements, images, typed notes). The agent distills the dossier into a longitudinal profile the advisor queries against. The unit of memory is the **artifact / dossier**, not the conversation turn / session. `session_id` is retired.

**Why.** It matches reality (advisor as the user; low-friction document capture, not transcription), strengthens the compliance story (advisor-authored books-and-records vs. a client transcript), and gives a *purer* memory-formation arc (episodic artifacts → consolidated profile over months) than a chat thread. Keeps the accrue → consolidate → recall loop that distinguishes memory from RAG.

**Consequences.** Schema migrates from `conversation_turns`/`turn_embeddings` to `artifacts`/`artifact_chunks`; `source_turn_ids` → `source_artifact_ids`. The streaming "conversation" becomes a query/brainstorm surface. UI relabels (timeline, query, retrieval, profile). Supersedes the prior turn/session and client-chatbot decisions.

---

## ADR-0003 — Stack: Lakebase + UC Volumes + `ai_parse_document` + LangGraph/Mosaic AI + FM API + Apps + MLflow

**Date:** 2026-06-04 · **Status:** Accepted

**Context.** We need memory storage, raw-file storage, document extraction, agent orchestration, LLM/embeddings, UI hosting, eval, and deployment — all Databricks-native (NFR-1).

**Decision.**
- Live memory: **Lakebase (Postgres + pgvector)**; raw bytes: **UC Volumes**; archived profile: **Delta in Unity Catalog** (see ADR-0004).
- Extraction: **`ai_parse_document`** (see ADR-0005).
- Orchestration: **LangGraph + LangChain** on the **Mosaic AI Agent Framework** with the stateful-agents SDK.
- LLM + embeddings: **Foundation Model API** (see ADR-0006).
- UI: **Databricks Apps** (see ADR-0007). Eval/trace: **MLflow**. Deploy: **DABs**.

**Why.** Everything is governed by Unity Catalog and deployable via DABs — the demo's thesis is *the lakehouse is the agent platform*. Lakebase autoscaling + OAuth rotation is the load-bearing differentiator over hand-rolled Postgres; UC Volumes bring unstructured data under the same governance umbrella.

**Consequences.** Any new memory/vector/OCR/LLM service (Pinecone, Redis, Mem0, external OCR) requires a new ADR. **Not** showcased: the nightly distillation Workflow (replaced — ADR-0009) and a standalone Model Serving endpoint (the App calls FM API / `ai_parse_document` directly).

---

## ADR-0004 — Memory storage triad: Lakebase live / Delta archive / UC Volume raw

**Date:** 2026-06-04 · **Status:** Accepted

**Context.** The dossier model has three distinct durability needs: immutable original files, fast live recall, and versioned archived profiles.

**Decision.** Three tiers: **UC Volume** = raw uploaded bytes (immutable); **Lakebase** = artifacts (episodic) + chunk embeddings (semantic) + proposals + audit (hot path); **Delta** = distilled profile versions (time travel).

**Why.** Each store is used for what it's best at: Volumes for governed unstructured blobs, Postgres/pgvector for low-latency client-scoped recall, Delta for cheap immutable versioning. Blurring them breaks the hot-path/archive separation.

**Consequences.** Ingest writes all three within one synchronous request. The agent never writes Delta directly (only distillation does) and never queries Delta in the hot path.

---

## ADR-0005 — Document extraction: `ai_parse_document` for all non-text kinds

**Date:** 2026-06-04 (validated + fallback dropped 2026-06-09) · **Status:** Accepted

**Context.** Ingest must handle PDFs, images, scans, photos of handwritten notes, Word docs, and typed text — synchronously, staying Databricks-native, ideally cheaper than a multimodal FM.

**Decision.** Use **`ai_parse_document`** as the **sole** extractor for every non-text kind (PDF, images, scans, handwriting). Plain text skips parsing. Native `.docx` pre-converts to PDF. There is **no multimodal fallback** — an earlier design escalated low-confidence handwriting images to a vision FM, but live validation made that path unnecessary (see below).

**Why.** Native, UC-governed, in-lakehouse, and cheaper than routing any doc through a multimodal FM. The originally-planned fallback added a second code path, a config surface (`HANDWRITING_CONFIDENCE_THRESHOLD`, `FM_API_VISION_ENDPOINT`), and a `databricks-langchain` vision dependency — none of which earned their keep once `ai_parse_document` proved good enough on handwriting.

**Validation (2026-06-09, T22).** Ran live `ai_parse_document` v2.0 on FEVM dev against printed and handwriting samples (Bradley Hand, Chalkduster, connected Snell cursive) of a wealth-advisor meeting note. Results: word recall 100% printed, 100%/98%/94% handwriting; mean element confidence ≥0.97, min element confidence ≥0.92 — far above the proposed 0.6 fallback threshold, which would therefore never have fired. The residual errors (`6/9`→`619`, `529`→`S29`) occurred on *high*-confidence elements, so confidence-gating could not have caught them anyway. Conclusion: accept `ai_parse_document` as-is and delete the fallback.

**Consequences.** `.docx` remains validate-before-promising in a demo (untested here). The VARIANT shape is confirmed: per-element `confidence` float, page index in `bbox[].page_id`, authoritative `document.pages` list. Synchronous per-ingest extraction accepts some lag; the UI must show progress (FR-1).

---

## ADR-0006 — Embeddings: Foundation Model API `databricks-bge-large-en` (1024-d)

**Date:** 2026-05-12 · **Status:** Accepted

**Context.** Semantic recall needs a Databricks-hosted embedding model (NFR: no external APIs). The pgvector column is `VECTOR(1024)`.

**Decision.** Use **`databricks-bge-large-en`** via Foundation Model APIs for all artifact-chunk and query embeddings.

**Why.** 1024-d output matches the schema; English-only fits the English-only UI; normalized embeddings pair cleanly with cosine distance (`vector_cosine_ops`). `databricks-gte-large-en` (also 1024-d) is the documented alternative if retrieval eval favors it — switching requires a re-embedding plan and a new ADR.

**Consequences.** Code and eval fixtures assume 1024-d vectors.

---

## ADR-0007 — Advisor UI: React frontend + FastAPI backend in Databricks Apps

**Date:** 2026-05-12 · **Status:** Accepted

**Context.** The UI has four surfaces (timeline, query, retrieval inspector, profile + HITL). `app.yaml` targets a Python module server.

**Decision.** Ship the wealth-advisor Databricks App as **FastAPI** (`agent_memory.ui.server`) serving a **React** (TypeScript) SPA, bundled as static assets alongside the backend.

**Why.** Multi-panel, streaming-friendly layouts and component reuse fit the advisor console better than Streamlit's page model. FastAPI matches `app.yaml` and keeps auth + SSE explicit.

**Consequences.** The frontend build step is in the DAB/App packaging path. Streamlit is out of scope for the shipped App.

---

## ADR-0008 — Audit + provenance: Lakebase event log + Delta time travel + per-field source artifacts

**Date:** 2026-06-04 · **Status:** Accepted

**Context.** Compliance requires an append-only audit of long-term-memory writes (who, what, source, when, run id), point-in-time profile history, and the ability to answer "why does the system believe this?"

**Decision.**
- **Lakebase `audit_log`** is the append-only system of record for memory-write events (ingest, summary, proposal, advisor accept/edit/reject, distillation), each row carrying enough payload to reconstruct what happened (incl. Delta table + version on profile commit).
- **Delta `client_profile`** provides immutable snapshot history via time travel.
- **Per-field provenance**: every profile field carries the `source_artifact_ids` that justified it; each artifact links to its raw bytes in the UC Volume.

**Why.** One operational log next to live data keeps incident tooling simple; Delta stays optimized for profile shape + versioning; provenance is what turns "RAG over docs" into auditable memory. Duplicating audit JSON into a second Delta table was rejected as redundant.

**Consequences.** Distillation/accept appends an `audit_log` row on profile upsert. Lakebase roles restrict UPDATE/DELETE on `audit_log`. The UI exposes the provenance chain (field → artifact → raw file).

---

## ADR-0009 — Triggered, incremental, human-in-the-loop distillation

**Date:** 2026-06-04 · **Status:** Accepted

**Context.** Distillation runs a non-deterministic LLM. A nightly batch re-distilling unchanged input only churns wording (and superseded proposals) with no new signal. Profile changes are also high-stakes and built on fallible OCR.

**Decision.** Distillation is **triggered** when new content lands for a client (not nightly), **incremental** (skip clients with no new artifacts since their last distillation — high-water mark on `source_artifact_ids`), and **human-in-the-loop** (writes a `profile_proposals` row; advisor accepts/edits/rejects; a new proposal supersedes the prior pending one). A manual/backfill run stays available.

**Why.** Idempotence: identical input → no spurious proposal. HITL: a profile delta is liability-adjacent and OCR-derived, so it must not auto-commit. Event-driven matches the synchronous-ingest UX.

**Consequences.** The nightly Workflow is dropped from the showcase. The trigger surfaces ingestion feedback and, when nothing is warranted, tells the advisor "no new content to distill."

---

## ADR-0015 — Refined demo dossiers: hand-authored personas, rendered fixtures, seed-time backdating

**Date:** 2026-06-09 · **Status:** Accepted

**Context.** The seed produced 3 procedurally-random clients with 3 all-text artifacts each, ingested at "now" — a thin, single-day dossier that undersells the longitudinal-memory story. We want richer clients: more history, multiple input formats (handwriting, PDF, scans), and a believable timeline.

**Decision.** Three concrete moves: (1) **Hand-author 3 personas** (`synthetic/personas.py`) with continuous storylines across 6 mixed-format artifacts each. (2) **Render binary artifacts with Pillow** (`synthetic/render.py`) — handwritten PNG (cursive), printed PDF, scanned JPG — committed as fixtures under `data/synthetic/fixtures/` via `scripts/render_fixtures.py`. (3) **Backdate at seed time** — production ingest always stamps "now"; the seed calls a new `store.backdate_artifact` to spread each client's artifacts over ~8 months.

**Why.** Pre-rendered committed fixtures sidestep font availability on Serverless and need no egress, and they're deterministic. Pillow is a **dev/`synthetic`-extra** dependency only (never imported by the app or the ingest runtime). Backdating lives in the seed, not the ingest path, so production timestamps stay honest — the data-layer change is a single narrow `backdate_artifact` (artifact + its chunks). The procedural `generate_dataset` stays for tests/eval.

**Consequences.** A handful of small binary fixtures are committed (synthetic, no real data). Fixtures must be re-rendered (`scripts/render_fixtures.py`) when persona content changes. The seed depends on the fixtures being synced with the bundle (they're non-gitignored, so the default bundle sync includes them).

---

## ADR-0016 — Bundle-provisioned infrastructure + single-source config (NFR-2)

**Date:** 2026-06-10 · **Status:** Accepted

**Context.** Getting started on a *new* workspace required ~2 manual provisioning steps (create a Lakebase instance, create a SQL warehouse) and editing the same workspace values across three files (`databricks.yml`, `app.yaml`, `.env.shared`), with FEVM-specific literals (host, profile, warehouse id, the `ep-odd-term…` Lakebase URL) hardcoded throughout. That undercuts NFR-2 ("deployable by a non-expert").

**Decision.** (1) **Provision in the bundle** — add `resources.database_instances.lakebase` (`agent-memory-${target}`) and `resources.sql_warehouses.warehouse`; the app + jobs reference them via `${resources.database_instances.lakebase.read_write_dns}` / `${resources.sql_warehouses.warehouse.id}`. No pre-existing infra, no ids to copy. (2) **Single config source = `.env`** — the user sets `DATABRICKS_PROFILE` + `UC_CATALOG` (rest defaulted); `deploy_bundle.sh` feeds them to the bundle as `BUNDLE_VAR_*`, generates the workspace-synced `.env.shared` notebooks read, and writes the resolved warehouse id + Lakebase endpoint back into `.env`. (3) **App env moved into the bundle** — the hand-maintained root `app.yaml` is deleted; the app's env is the bundle app resource's inline `config.env`, templated from `${var}`/`${resources}`. (4) **App↔Lakebase binding** gives the app SP a Postgres role; the app mints OAuth tokens at runtime via the existing provisioned-instance path (`LAKEBASE_INSTANCE_NAME`). Notebooks derive the instance name from their target and look the host up via the SDK. Lakebase table grants moved from a `psql` block in the deploy script into `00_setup` (removes the local `psql` prerequisite).

**Why.** `bundle deploy` already builds a dependency graph, so `${resources…}` references resolve in-deploy — the Databricks-native way to wire an app to infra it creates. Keeping `.env` as the one input and propagating it (BUNDLE_VAR → bundle; generated `.env.shared` → notebooks; write-back → local) removes the three-file triplication without asking any consumer to read a file it can't reach. Inline app `config.env` was chosen over a rendered `app.yaml` because it lets the app env reference created resources directly (a static `app.yaml` can't). Alternatives rejected: keep manual provisioning + documented prereqs (fails the "non-expert" bar); a `variable-overrides.json` input (less familiar than `.env`).

**Consequences.** Deploying a target creates a Lakebase instance + warehouse; switching an existing deployment to this bundle starts with an empty instance → re-run `00_setup` + `01_seed`. Two runtime behaviors are confirmed only on a live deploy: that `apps deploy` honors the inline `config.env`, and that `read_write_dns` populates via `${resources…}` (deploy script has a `get-database-instance` fallback for the latter). `.env.shared` is now generated (gitignored); `.env.example` is the committed template. Job entry points gained `--lakebase-instance-name`.

---

## ADR template (copy when adding a new one)

```
## ADR-XXXX — Short title
**Date:** YYYY-MM-DD · **Status:** Proposed | Accepted | Superseded by ADR-YYYY
**Context.** What forces are at play?
**Decision.** What did we choose? Be specific.
**Why.** Reasoning + alternatives rejected.
**Consequences.** What does this lock us into? What follow-up does it create?
```
