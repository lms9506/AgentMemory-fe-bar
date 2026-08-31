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

## ADR-0016 — Rebrand to Smart Advise + Tailwind CSS v4 restyle

**Date:** 2026-07-02 · **Status:** Accepted

**Context.** The deployed app is renamed from `wealth-advisor-${bundle.target}` to `smart-advise-${bundle.target}` for GTM reasons. The existing plain-CSS frontend is restyled with Tailwind CSS v4 (Vite plugin, no PostCSS config). Python package (`agent_memory`) and UC schema (`wealth_advisor`) are explicitly preserved.

**Decision.** Add `tailwindcss@4.3.1` + `@tailwindcss/vite@4.3.1` as pinned devDeps. Rewrite `styles.css` around `@import "tailwindcss";` + a CSS-first `@theme` block for brand color tokens. Enable Preflight (full restyle scope). Rename `databricks.yml` resource key `wealth_advisor` → `smart_advise` and `name` field. Update both `app.yaml` files, `deploy_bundle.sh` (5 occurrences + `bundle run` target), and notebook APP_NAME/APP_URL constants. Old app left running during cutover; user deletes manually.

**Why.** GTM rename + Tailwind v4 is the minimum-viable diff: no `tailwind.config.js`, no PostCSS config, no component library. Pinning `4.3.1` avoids the insiders-tag on the Databricks npm proxy.

**Consequences.** New `smart-advise-*` App gets a new service principal — grants must be re-applied via `deploy_bundle.sh` on first deploy. Full Preflight requires auditing all raw HTML elements in `App.tsx`. Full ADR at `architecture/adr-0016-smart-advise-rebrand-and-tailwind.md`.

---

## ADR-0019 — Batch bulk-onboarding via a Lakeflow declarative pipeline

**Date:** 2026-08-28 · **Status:** Accepted

_Note: ADR-0017 and ADR-0018 are reserved by the unmerged `linus` branch (PR #7, managed-memory positioning); this work branched from `main` and takes the next free numbers._

**Context.** The accelerator had a single ingest surface: the interactive, synchronous one-file drag-drop (`agents/ingest_graph.py`). Two forces pushed for a second, batch surface: (1) the real advisor workflow of **inheriting a book of clients** — a pile of historical documents to onboard at once, which is a data-engineering job, not a series of clicks; (2) demonstrating the full Databricks data-journey — raw dataset → Lakeflow ingest → Unity Catalog governance → Gen AI enrichment → Lakebase serving — as an integrated pipeline.

**Decision.** Add a **Lakeflow declarative pipeline** (`databricks/pipelines/dossier_ingest.py`) that Auto Loads raw files from a UC Volume `_landing/{client_id}/` zone into `bronze_raw_artifacts` (binaryFile + SHA-256 hash + derived client_id/kind), then produces `silver_parsed_artifacts` by running `ai_parse_document` (extraction) and `ai_query` (per-artifact summary) inline — both UC-governed Delta tables. A downstream `hydrate` wheel task (`jobs/hydrate_entry.py`) reads silver and loads Lakebase pgvector reusing the existing store/embedding primitives, and a final `distill` task populates the Delta `client_profile`. The three run as one `dossier_ingest_job` (pipeline → hydrate → distill). Synthetic raw data is staged by `scripts/seed_landing.py` (personas' mixed-format fixtures + generated text clients at `client_1000+`).

**Why.** Lakeflow declarative pipelines are the canonical, lowest-effort way to get incremental ingest + lineage + UC governance for a raw file drop; Auto Loader handles new-file detection for free. Doing extraction/summary with native SQL AI functions (`ai_parse_document`, `ai_query`) keeps the "make it intelligent" step in-pipeline with no extra compute or Python. Keeping chunk/embed + Lakebase load in a separate wheel task preserves the three-tier discipline (Volume=bytes, Delta=governed batch, Lakebase=live serving) and reuses tested code. **Alternative rejected:** routing batch ingest through the interactive LangGraph one file at a time — wrong tool (no lineage, no incremental semantics, serial). **Trade-off accepted:** the pipeline inlines a copy of `extract_text_from_variant` (`variant_to_text`) so it deploys as a single `.py` with no wheel install on pipeline compute; `tests/test_pipeline_parser.py` asserts parity with the canonical parser so the two cannot silently diverge.

**Consequences.** A second ingest path to keep in sync with the artifact schema; the parity test guards the one duplicated function. The pipeline is validated live at deploy time (offline tests cover the pure helpers only, as is standard for DLT). Generated batch clients carry a derived display name (`Client 1000`) since the pipeline doesn't propagate the persona-style names.

---

## ADR-0020 — Genie space over the governed dossier tables

**Date:** 2026-08-28 · **Status:** Accepted

**Context.** The end-to-end journey needs a natural-language query surface. The advisor-facing value ("which clients are conservative?", "how many documents mention retirement?") sits on the governed Delta tables the pipeline and distillation job produce, not on the Lakebase live store (which is Postgres, not Genie-queryable).

**Decision.** Provision a **Genie space** over `silver_parsed_artifacts`, `client_profile`, and `bronze_raw_artifacts`, defined declaratively in `databricks/genie/dossier_space.json` (title, tables, instructions, sample questions) and created by `scripts/setup_genie.py` via the Genie Spaces REST API, with a printed manual-setup fallback since that API is in preview. Instructions bound the space to advisor-internal, no-financial-advice framing.

**Why.** Genie is the Databricks-native NL-over-SQL surface; pointing it at the UC Delta tables reuses the governance already in place and needs no new modeling. A version-controlled JSON definition keeps the space reproducible regardless of API drift. **Alternative rejected:** a bespoke text-to-SQL agent — redundant with Genie and outside the accelerator's scope. **Not chosen:** a DAB `genie` resource — no first-class bundle resource type exists yet, so a script + committed definition is the reproducible path.

**Consequences.** Genie sees only the Delta tables (client registry display names live in Lakebase, so NL answers key on `client_id`). The space is created out-of-band from `bundle deploy`; re-running `setup_genie.py` refreshes it.

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
