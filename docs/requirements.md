# Requirements

## Vision

Deliver a **Databricks Solution Accelerator** that demonstrates governed, durable agent memory for regulated industries, anchored in a Financial Services **Wealth Advisor** scenario. A Databricks SA should be able to clone the repo and stand up a working PoC against their own workspace in under two weeks — deployable through **DABs + setup notebooks by someone without deep technical knowledge**.

## The model: advisor-fed client dossier

The app is **advisor-facing and internal**. Databricks Apps are workspace-authenticated, so this is never a client-facing chatbot. Advisors do not record sensitive client conversations; the system of record is **advisor-authored**.

The advisor **feeds a client dossier** — an append-only stream of dated artifacts (meeting notes, scanned statements, PDFs, photos of handwritten notes, typed notes). Over weeks and months the agent distills the dossier into a governed, longitudinal **client profile**. Before a meeting, the advisor **queries and brainstorms against** that memory.

The unit is the **client dossier**, not a chat session. There is no `session_id`.

Why this is *memory*, not RAG: RAG is stateless retrieval over a static corpus. Here, knowledge **accrues** (every ingest is written and audited), is **consolidated** (distillation folds artifacts into the profile over time), and is **recalled** (semantic search) and **governed** (provenance + audit). The write-and-consolidate loop is the differentiator.

## Personas

| Persona | Goal | Pain |
|---|---|---|
| **Wealth advisor** | Walk into a client meeting fully briefed in 30s, and brainstorm ideas against everything on file | Re-reading scattered CRM notes and PDFs; losing context across months and across colleagues |
| **Compliance officer** | Prove every belief the system holds about a client traces to a source document, with an audit trail | Black-box agents; no traceable memory state |
| **Databricks SA (accelerator user)** | Stand up the demo against their own workspace in <2 weeks, without deep platform expertise | Generic memory demos that ignore governance and are hard to deploy |

## Functional requirements

### FR-1 — Synchronous artifact ingestion
A drag-and-drop surface accepts common formats — **PDF, images (incl. photos of handwritten notes), Word docs, and plain typed text**. Ingestion is **synchronous**: the advisor drops a file, waits seconds, and sees the result. Some lag is acceptable; the UI **must** show ingestion feedback (progress state). Each ingest runs the pipeline in FR-2..FR-5.

### FR-2 — Raw artifact preservation (traceability)
The original input is stored **unchanged** in a **UC Volume**, keyed by client. This is the immutable books-and-records artifact. A **content hash** is computed at ingest; **duplicate** uploads (same bytes) are detected and short-circuited so the profile never double-counts.

### FR-3 — Extraction + semantic indexing
Each artifact is parsed with **`ai_parse_document`** (native Databricks; PDF, images, scans). Plain typed text skips parsing. Extracted text is **chunked, embedded** (`databricks-bge-large-en`), and stored in **Lakebase pgvector** — the retrieval substrate. The extracted text is shown next to the summary so the advisor can eyeball OCR errors before they propagate.
- Sole extractor: `ai_parse_document`, for every non-text kind incl. handwriting. Native `.docx` may require pre-conversion to PDF.
- No multimodal fallback: live validation (2026-06-09, T22) confirmed `ai_parse_document` handles handwriting — including connected cursive — at ≥94% word recall, so the planned vision-FM escalation was dropped. See `docs/decisions.md` ADR-0005.

### FR-4 — Per-artifact summary
Each ingest produces a concise summary of **just that artifact**, auto-committed (low-stakes). It is the dossier-timeline entry and an input to distillation.

### FR-5 — Long-term profile distillation (triggered)
Distillation reads a client's accrued artifacts and produces a structured profile: risk tolerance, investment goals, family context, stated preferences, narrative summary. It is **triggered whenever new content lands** for a client (not a nightly batch), and is **incremental** — a client with no new artifacts since its last distillation is skipped (re-running the non-deterministic LLM on unchanged input only churns wording). Each committed profile is a new **Delta** version (time-travel audit). A manual/backfill run remains available as a convenience.

### FR-6 — Profile changes are human-in-the-loop
A profile delta is **proposed**, never auto-committed — it is high-stakes, liability-adjacent, and built on fallible OCR. Proposals are written to Lakebase `profile_proposals`; the advisor UI surfaces each pending proposal, and the advisor can:
- **Accept** — commit to Delta as-is + audit row.
- **Edit then Accept** — modify fields inline, commit the edited version + audit row.
- **Reject** — no Delta write; audit row records the rejection.

A new proposal **supersedes** any prior pending proposal for the same client (one pending per client). All outcomes append an `audit_log` row (actor kind: `advisor`).

### FR-7 — Per-field provenance
Every field in the distilled profile traces to the **artifact(s)** that justified it, and each artifact traces back to its raw bytes in the UC Volume. A compliance officer can ask "why does the system believe this?" and get a chain to the original document. (Provenance is carried as `source_artifact_ids`.)

### FR-8 — Audit trail
Every write to long-term memory emits a row to the Lakebase `audit_log` (see ADR on audit) with: `who`, `what changed`, `source artifacts`, `timestamp`, `agent run id`. Distilled profile state is additionally versioned in Delta for time travel. The audit log is append-only.

### FR-9 — Shareable memory
Two advisors working with the same client see the same memory. Memory is keyed on `client_id`, not `advisor_id`. Per-advisor private scratchpad is out of scope for v1.

### FR-10 — Query / brainstorm surface
The advisor queries the dossier in natural language ("what do we know about their retirement timeline?", "does an estate review make sense given what's on file?"). Retrieval is semantic over artifact chunks, scoped by `client_id`. **Advice boundary:** outputs are framed as *considerations / things to check / what the file says* — never "I recommend X." The advisor remains the fiduciary. Responses may stream.

### FR-11 — Sensitivity tagging (optional v1)
Ingested artifacts carrying sensitive content (SSNs, account numbers) are flagged/tagged at ingest — a FINS-specific governance affordance generic RAG lacks.

### FR-12 — Advisor-facing app
A **Databricks App** (FastAPI backend, React frontend) shows: the **dossier timeline** (artifacts with summaries + raw-file links + "contributed to profile?" badges), the **query/brainstorm** surface, the **retrieval inspector** (what the agent pulled, with scores), and the **distilled profile** (with clickable per-field provenance + HITL proposal review).

### FR-13 — Evaluation harness
An **MLflow**-tracked eval suite scoring (a) retrieval recall against labeled gold memories and (b) response quality on synthetic scenarios (grounding, suitability framing, tone, advice-boundary adherence). Runs in CI on every PR touching `src/agent_memory/`.

## Non-functional requirements

### NFR-1 — Databricks-native
No external services for memory, vector search, extraction, LLM, or hosting. Everything inside the Databricks platform. New dependencies require an ADR.

### NFR-2 — Reproducible, non-expert deployment
A new SA clones the repo, sets a handful of config values, runs `databricks bundle deploy --target <workspace>`, and walks the **setup notebooks** to provision and seed. No manual UI clicks beyond documented one-time bindings; no deep platform expertise required.

### NFR-3 — Synthetic data only
The repo ships generators for synthetic clients, portfolios, and **dossier artifacts** (notes, statements, docs). Real client PII never enters the repo or the demo workspaces.

### NFR-4 — Lakebase production-shaped
Autoscaling on; OAuth credential rotation via the stateful-agents SDK.

### NFR-5 — Solution Accelerator qualification
Clear industry tie (FINS / Wealth Management); current Databricks tech (Lakebase, UC Volumes, `ai_parse_document`, Mosaic AI Agent Framework, Apps, MLflow); updated at least every 6 months; Industry GTM co-owner identified and signed off (see `docs/progress.md`).

### NFR-6 — Legible structure + documentation
The repo is structured so an interested newcomer can follow it. Every public function has a docstring; every architectural decision has an ADR; the README + `docs/` + setup notebooks are sufficient onboarding without tribal knowledge.

## Positioning — vs. `banking-agent-accelerator`

`databricks-industry-solutions/banking-agent-accelerator` ("Deterministic Stateful Agent with Async Human-in-the-Loop") is a sibling FINS agent accelerator. It is **complementary, not competing**, and the contrast sharpens what this project is:

| | banking-agent-accelerator | This accelerator |
|---|---|---|
| Core problem | Execute a transactional workflow safely (add beneficiary, credit-limit increase) | Remember & consolidate a client across time |
| Lakebase role | LangGraph **checkpoint** (durable working state to resume a paused workflow) | **Agent-memory store** (episodic artifacts + semantic recall) |
| Long-term memory / profile | None | Central |
| Semantic recall / distillation | None | Central |
| Document ingestion | None (stub tools) | The dossier model |
| "HITL" | Async compliance approval gate | Advisor reviews a proposed profile change |

Notably, its Lakebase usage is the **single-thread checkpoint** pattern that the #agents channel called *insufficient* for managed agent memory (see ADR on industry/use-case) — concrete evidence the agent-memory gap this accelerator fills is real. When engaging GTM, frame this project explicitly as **the memory layer** and cite the banking accelerator as the workflow-execution sibling.

## Out of scope (v1)

- Per-advisor private memory (only shareable client memory)
- A client-facing surface (advisor-internal only)
- The agent generating advice (considerations only; advisor is the fiduciary)
- Multi-language UI (English only)
- Non-FINS industry adaptations (clones can fork)
- Custom fine-tuned embedding models — use the Databricks default
- Mobile UI
