# Glossary

Memory-system and domain terms. When you add a new concept to the codebase, add it here.

## Memory taxonomy

**Dossier** — The append-only collection of all artifacts an advisor has fed about a client. The unit of memory in this accelerator (there is no chat "session").

**Artifact** — One ingested item: a note, PDF, scanned statement, image, or typed text. Raw bytes live in a UC Volume; the parsed text, summary, and metadata live in the `artifacts` table in Lakebase. Append-only.

**Episodic memory** — The time-ordered log of artifacts (`artifacts` in Lakebase). Source of truth for "what was observed/logged, and when."

**Semantic memory** — Embeddings of artifact text chunks (`artifact_chunks`, pgvector). Used for similarity recall ("what do we know about X?"). Derived from episodic memory.

**Long-term profile** — Distilled, structured knowledge about a client (risk tolerance, goals, family context, preferences, summary). Stored in `client_profile` Delta table; prior versions via Delta time travel.

**Working memory** — The in-context window of the current LangGraph run. Not persisted.

**Shareable memory** — All memory is keyed on `client_id`, not `advisor_id`. Two advisors working with the same client see the same memory. Per-advisor private scratchpads are out of scope for v1.

**Extraction** — Turning raw artifact bytes into text via `ai_parse_document` (OCR/parse). The extracted text is the substrate that gets chunked, embedded, and summarized.

**Distillation** — Folding a client's accrued artifacts into an updated long-term profile. **Triggered** when new content lands, **incremental** (skips clients with no new artifacts), and produces a **proposal**, not a direct commit.

**Profile proposal** — A machine-distilled profile pending advisor review (`profile_proposals`). The advisor accepts, edits-then-accepts, or rejects. A new proposal supersedes the prior pending one for that client.

**Retrieval** — Pulling top-k relevant artifact chunks into working memory before generation. Always scoped by `client_id`.

**Provenance** — The chain from a profile field → the artifact(s) that justified it (`source_artifact_ids`) → the raw bytes in the UC Volume. Answers "why does the system believe this?"

**Audit row** — A row in `audit_log` written on every long-term-memory write (ingest, summary, proposal, advisor action, distillation). Contains who, what, source artifacts, timestamp, agent run id. Append-only.

**Advice boundary** — The agent surfaces *considerations / things to check / what the file says*, never "I recommend X." The advisor remains the fiduciary.

## Domain terms (FINS / Wealth Management)

**Client** — The end customer the advisor serves. Not "user" — "user" means the advisor.

**Advisor** — The wealth-management professional using the app. The UI "user."

**Suitability assessment** — Regulatory requirement to document that advice matches the client's risk profile, goals, and circumstances. The memory system makes suitability auditable.

**Portfolio** — The client's holdings. Synthetic in this repo.

**Books and records** — The regulatory obligation (FINRA 4511 / SEC 17a-4) to retain client records. The raw artifacts in the UC Volume are the immutable record.

## Databricks platform terms

**Lakebase** — Databricks-managed Postgres with autoscaling and OAuth rotation, governed by Unity Catalog. Here: the live agent-memory store.

**pgvector** — Postgres extension for vector similarity search. Enabled on Lakebase.

**UC Volume** — Unity Catalog-governed storage for unstructured files. Here: immutable raw artifact bytes.

**`ai_parse_document`** — Native Databricks document-parsing/OCR AI function (PDF, images, scans).

**Mosaic AI Agent Framework** — Databricks runtime for stateful agents.

**Stateful-agents SDK** — Python SDK that wires Lakebase connections with OAuth rotation into LangGraph workflows.

**Foundation Model API (FM API)** — Databricks-hosted LLM + embedding endpoints. No external API keys.

**Databricks Apps** — Python apps hosted natively in the Databricks workspace.

**Databricks Asset Bundles (DABs)** — Declarative deployment for jobs, apps, models. `databricks.yml` is the config.

**Unity Catalog (UC)** — Databricks governance layer over data + AI assets (tables, Volumes, models).

**FE-IP** — Field Engineering Intellectual Property. The internal catalog of demos, accelerators, and reusable IP SAs maintain.

**Solution Accelerator** — A Databricks-published, industry-anchored reference implementation. Qualification: clear industry tie, current Databricks tech, updated every 6 months, GTM co-owner.
