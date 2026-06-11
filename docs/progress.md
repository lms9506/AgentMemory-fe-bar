# Progress

> Single source of truth for "what is happening right now." Update on task start *and* finish. Convert relative dates to absolute. Keep dead entries — move them to `## Done`, don't delete.

**Last updated:** 2026-06-10

## North star

Ship a Databricks Solution Accelerator: *AI Wealth Advisor with persistent client memory*. Target: FE-IP entry + Industry GTM sign-off by **2026-Q3**.

## Active phase: Pivot to the dossier model

**Decision (2026-06-04):** the product pivots from a client-chatbot / conversation-turn model to an **advisor-fed client dossier** model. The app is advisor-facing (Databricks Apps are internal); the advisor drag-drops artifacts (notes, PDFs, scans, images), which are saved raw to a UC Volume, parsed by `ai_parse_document`, embedded into Lakebase pgvector, summarized, and — when warranted — distilled into a **proposed** profile update (HITL). See ADR-0002 and `docs/requirements.md`.

**Documentation rewritten** to the dossier model (CLAUDE.md, README, all `docs/`); ADR log clean-rewritten. **Code migrated** (2026-06-04, D1–D9): `src/`, the Lakebase + Delta schemas, the React UI, synthetic generator, notebooks, and eval all implement the dossier model. Gates: ruff clean, pyright strict 0 errors, 244 tests passing. Validated offline (workspace-dependent paths are stubbed); live FEVM-dev validation happens on first `bundle deploy` + `00_setup`/`01_seed` notebook run.

**Sibling project:** `databricks-industry-solutions/banking-agent-accelerator` exists — a deterministic transactional-workflow agent using Lakebase as a LangGraph checkpoint (no managed memory). Complementary, not competing; useful evidence for M11. See `requirements.md` § Positioning.

## v1 status (turn/session model — being superseded)

M0–M9 shipped and validated on FEVM dev; they prove the stack wiring (Lakebase + pgvector, Delta profile, audit, HITL proposals, MLflow eval/trace, Apps). The retrieval/distillation/audit machinery carries over; the turn/session-specific pieces are replaced by the dossier model.

## Dossier-model milestones (target)

- [x] **D0** — Docs + ADRs rewritten to the dossier model *(done 2026-06-04)*
- [x] **D1** — Lakebase schema migration: `conversation_turns`/`turn_embeddings` → `artifacts`/`artifact_chunks`; `source_turn_ids` → `source_artifact_ids` *(done 2026-06-04)*
- [x] **D2** — UC Volume raw-artifact storage + content-hash dedup (FR-2) *(done 2026-06-04)*
- [x] **D3** — `ai_parse_document` extraction + chunk/embed pipeline (ADR-0005) *(done 2026-06-04; handwriting validated live 2026-06-09 (T22) — ≥94% word recall incl. cursive, multimodal fallback dropped; `.docx` still unvalidated)*
- [x] **D4** — Synchronous ingest endpoint + drag-drop UI with SSE progress feedback (FR-1) *(done 2026-06-04)*
- [x] **D5** — Per-artifact summary (FR-4) + triggered/incremental distillation rewired to artifacts (FR-5, ADR-0009) *(done 2026-06-04)*
- [x] **D6** — Per-field provenance (field → artifact → raw file) surfaced in UI (FR-7) *(done 2026-06-04)*
- [x] **D7** — Synthetic dossier-artifact generator (notes, statements, docs; `kind='text'` + `category`) (NFR-3) *(done 2026-06-04)*
- [x] **D8** — Setup + demo notebooks authored (`00_setup`/`01_seed`/`02_demo`, the non-expert deploy path) (NFR-2) *(done 2026-06-04)*
- [x] **D9** — Eval refreshed for dossier scenarios incl. advice-boundary adherence (FR-13) *(done 2026-06-04)*
- [ ] **M10** — FE-IP entry submitted
- [ ] **M11** — Solution Accelerator nomination submitted

## Stakeholders

| Role | Person | Status |
|---|---|---|
| Project lead | Michael Egli | active |
| Co-developer | Linus | active |
| FINS Industry GTM (target co-owner) | Antoine Amend *or* David Hackett | to ping 2026-05-12 |
| Lakebase adoption sponsor | Ryan DeCosmo, Lu Wang | informed via #agent-memory |
| Memory PM context | (from #agents — Zillow Oct 2025 ask) | reference only |

## v1 milestones (shipped — turn/session model, now being superseded)

- [x] **M0** — Industry + use case decision: Financial Services / Wealth Advisor *(done 2026-05)*
- [x] **M1** — Repo created, context-engineering scaffold landed *(done 2026-05-12)*
- [x] **M2** — FINS SA co-owner committed (Antoine or David)
- [x] **M3** — Lakebase schema + synthetic data generator merged *(done 2026-05-19)*
- [x] **M4** — Single-turn agent end-to-end (no memory) — proves stack wiring *(done 2026-05-19)*
- [x] **M5** — Episodic memory + pgvector retrieval working *(done 2026-05-22)*
- [x] **M6** — Distillation job + Delta profile working *(done 2026-05-22)*
- [x] **M7** — Databricks App UI with all four panels *(done 2026-06-02)*
- [x] **M8** — MLflow eval harness in CI *(done 2026-06-03)*
- [x] **M9** — HITL proposal review; advisor accepts, edits, or cancels in UI *(done 2026-06-03)*

(M10 / M11 carry forward — see the dossier-model milestones above.)

## Open tasks

| # | Owner | Task | Blocked by |
|---|---|---|---|
| T1 | Michael | Ping Antoine Amend / David Hackett with SA proposal doc, set meeting for week of 2026-05-18 | — |
| T17 | Linus | Revisit `keyword_recall_score`: gold-keyword lists of mutually-exclusive alternatives (e.g. conservative/moderate/aggressive) deflate recall since all are required. Consider any-of groups. | — |
| T21 | — | Express the app-SP `READ VOLUME`/`WRITE VOLUME` grant in `databricks.yml` (currently comment-only there; executable grant lives in `00_setup.py` gated on `APP_SERVICE_PRINCIPAL`). | — |
| T23 | — | Close the ingest orphan window: INSERT→Volume upload→UPDATE isn't transactional (documented in `store.py`); a crash mid-ingest can leave a row whose `volume_path` was never written. Consider a reconcile/cleanup pass. | — |

## Decisions pending

(none)

## Done

- 2026-06-10 — **Bundle-provisioned infra + single-source config (ADR-0016, NFR-2)**: a new workspace no longer needs manual prereqs or multi-file edits. The bundle now **provisions** its own Lakebase instance (`database_instances`, `agent-memory-${target}`) + SQL warehouse (`sql_warehouses`); the app + jobs reference them via `${resources…read_write_dns/.id}` — all FEVM literals (host, profile, warehouse id, `ep-odd-term…` URL) removed. **`.env` is the single config source**: `deploy_bundle.sh` feeds it to the bundle (`BUNDLE_VAR_*`), generates the workspace-synced `.env.shared` (now gitignored) the notebooks read, and writes the resolved warehouse id + Lakebase endpoint back into `.env`. Root `app.yaml` **deleted** → app env is the bundle app resource's inline `config.env`, templated from `${var}`/`${resources}`. App↔Lakebase binding gives the app SP a Postgres role (runtime OAuth via the provisioned-instance path); notebooks derive the instance name from their target + look up the host via SDK; Lakebase table grants moved from the deploy script's `psql` block into `00_setup` (drops the local `psql` prereq). Job entry points gained `--lakebase-instance-name`. New `.env.example` (committed template); README quickstart rewritten for a fresh workspace. Gates: ruff + pyright(src) clean, 260 pass, `bundle validate` OK. **Not yet deployed live** — two runtime behaviors (inline `config.env` honored by `apps deploy`; `read_write_dns` via `${resources…}`) confirm only on a real `bundle deploy`; deploy script has a `get-database-instance` fallback for the host.
- 2026-06-10 — **Clone-and-run cleanup (PR #5 review follow-ups, NFR-2)**: removed the two things that undercut "deployable by a non-expert". (1) All three notebooks (`00_setup`/`01_seed`/`02_demo`) no longer hardcode `linus.meister@databricks.com` / `dev` — `REPO_ROOT` is now derived from the notebook's own workspace path (`notebookPath()` → two levels up), the package installs via the CWD-relative `%pip install ..`, `APP_NAME`/`TARGET` derive from the path, and `02_demo` looks up the live app URL from the SDK instead of a hardcoded workspace URL. Zero edit points: clone → `bundle deploy --target <target>` → Run all. (2) Deleted three stale/divergent config duplicates — `databricks/app.yaml`, `databricks/databricks.yml`, `src/agent_memory/ui/app.yaml`; the repo-root `app.yaml` + `databricks.yml` are authoritative (`source_code_path: .`). Fixed the `ui/__init__.py` docstring that pointed at the deleted `databricks/app.yaml`. (`databricks/*.sql` schema files stay — they're referenced by `00_setup` + scripts.) Gates: ruff + pyright(src) clean, 260 pass.
- 2026-06-09 — **Refined demo dossiers (ADR-0015)**: replaced the 3 procedurally-random, all-text, single-day clients with 3 **hand-authored personas** (Alex Santos, Sophia Hartmann, Marcus Delacroix), each a continuous storyline across 6 **mixed-format** artifacts — handwritten PNG (cursive), printed PDF, scanned JPG, and typed text — **backdated** over ~8 months. New `synthetic/personas.py` (personas + ground-truth content), `synthetic/render.py` (Pillow renderers), `scripts/render_fixtures.py` (regenerates the 15 committed fixtures under `data/synthetic/fixtures/`), and `store.backdate_artifact` (seed-only override of `ingested_at` + chunk `created_at`; production ingest still stamps "now"). `01_seed.py` rewritten to ingest personas (inline text + fixture bytes) through the real graph, then backdate. Pillow added as a dev/`synthetic` extra (not an app/runtime dep). Procedural `generate_dataset` kept for tests/eval. Tests: +`test_render.py`, +`test_personas.py` (incl. backdate). Not yet seeded live — needs `01_seed` re-run on FEVM dev.
- 2026-06-09 — **T22 closed**: validated `ai_parse_document` v2.0 live on FEVM dev against printed + handwriting (Bradley Hand, Chalkduster, connected Snell cursive) wealth-advisor meeting notes rendered from known ground truth. Word recall 94–100% (cursive 94%); mean element confidence ≥0.97, min ≥0.92. VARIANT shape confirmed: per-element `confidence` float, page index in `bbox[].page_id`, authoritative `document.pages` list. **Outcome (per decision): accepted `ai_parse_document` as good enough and removed the multimodal fallback entirely** — `_multimodal_fallback`, the `kind=='image'` confidence-gate, the `handwriting_confidence_threshold` + `fm_api_vision_endpoint` settings, and the ADR-0005 narrow-fallback decision (rewritten). Rationale: even cursive stayed ≥0.92, far above the 0.6 threshold (which would never fire), and the residual substitution errors landed on high-confidence elements anyway. Also fixed a latent bug: `page_count` was always `None` (parser read `element.get('page')`, a key that doesn't exist) — now reads `document.pages` / `bbox[].page_id`. Tests: +3 page_count, −2 config; **247 pass**, ruff + pyright strict clean.
- 2026-06-04 — D1–D9: dossier-model code migration landed (turn/session → artifact/chunk). New Lakebase `artifacts`/`artifact_chunks` schema (HNSW pgvector, SHA-256 dedup); `volume_store` (UC Volume raw bytes) + `extraction` (`ai_parse_document` via Statement Execution, 512/50 chunking, base64 multimodal fallback); `ingest_graph` (raw_save→extract→chunk_embed→summarize→maybe_propose) with SSE progress; sync ingest routes + 25 MB cap + `client_id` guard; distillation rewired to artifact high-water mark; per-field provenance UI; React dossier timeline + drag-drop upload (dist rebuilt); synthetic dossier generator (`kind='text'`+`category`); `00_setup`/`01_seed`/`02_demo` notebooks; advice-boundary eval. `source_turn_ids`→`source_artifact_ids` everywhere. Gates: ruff clean, pyright strict 0, 244 tests. Built via the michael-build swarm (scout→architect→3 parallel builders→AgentCoder test triad→critic/judge, final judge 0.85). Follow-ups: T21–T23.
- 2026-06-04 — D0: pivot to dossier model decided (ADR-0002); all docs + ADR log clean-rewritten to the dossier design; stale swarm scratch (`architecture/`, `research/`) removed. **Note:** the ADR log was renumbered on this date — ADR references in older Done entries below point to pre-rewrite numbers and no longer resolve; they're kept as a historical record of what happened, not as live links.
- 2026-05-12 — M0 industry/use case decided (FINS Wealth Advisor) — see `decisions.md` ADR-0001
- 2026-05-12 — M1 repo scaffolded with context-engineering setup
- 2026-05-12 — ADR-0003 (React + FastAPI Apps UI), ADR-0004 (`databricks-bge-large-en`), ADR-0005 (Lakebase audit + Delta time travel)
- 2026-05-19 — M3: `lakebase_schema.sql` + synthetic generator (`src/agent_memory/synthetic/`, `uv run agent-memory-synthetic`)
- 2026-05-19 — M4: LangGraph single-turn agent live against FM API (`agent-memory-chat`, CLI profile auth)
- 2026-05-22 — M5: Lakebase episodic + semantic memory (`LakebaseMemoryStore`, pgvector retrieval, audit on append), LangGraph `retrieve → generate → write_memory`, OAuth Lakebase + FM API embeddings, `agent-memory-chat` with MLflow tracing, `scripts/apply_lakebase_schema.py`, live E2E validated; `.env.shared` team defaults
- 2026-05-22 — M6: `agent-memory-distill`, Delta `client_profile` MERGE, Lakebase `audit_log` on profile upsert, `apply_delta_schema` / split Lakebase DDL apply + `ensure_audit_log`, DAB `distillation_nightly` wheel task; E2E validated
- 2026-05-27 — M7 (local): FastAPI + React four panels (`agent-memory-app`), chat/transcript/retrieval/profile/HITL paths; `build_frontend.sh` + Databricks npm proxy; SQL warehouse id in `.env.shared`
- 2026-05-27 — M7: FR-9 `POST /api/chat/stream` (SSE); DAB `source_code_path: ..`, dev catalog alignment, `deploy_bundle.sh`, repo-root `app.yaml`
- 2026-05-28 — M7 hosted debug: fixed Databricks App static/env deploy gaps (`sync.include` for `frontend/dist`, app Lakebase env wiring), SQL client auth conflict guard (`oauth` + `pat`), and API 503 dependency errors
- 2026-05-28 — M7 hosted debug: replaced Lakebase credential minting CLI dependency (`databricks postgres ...`) with SDK-based token minting and added explicit 503 mapping for UC permission failures
- 2026-05-27 — M7: fix hosted App 404 on `/` — bundle `sync.include` for gitignored `frontend/dist`, static path fallback in `server.py`
- 2026-06-02 — M7 done: hosted App validated (T13); all four panels live on FEVM dev workspace
- 2026-06-03 — M9 backend (T15): `proposal_store` (Lakebase + in-memory), `distillation --hitl`, `GET/accept/reject /api/proposals`, audit row on every accept/reject, DAB `distillation_hitl_nightly`; 15 tests
- 2026-06-03 — M9 UI (T16): React proposal-review panel (Accept / Edit-then-Accept / Cancel cards) replacing the free-text note form; manual trigger repointed to the HITL job and renamed "Propose update"
- 2026-06-03 — M9 hosted validation: fixed `/api/distill` to match the DABs `[dev <user>]` job-name prefix and `--hitl` value parsing (named_parameters emits `--hitl=true`, broke `store_true`); HITL job run produced 6 pending proposals on FEVM dev
- 2026-06-03 — M8 done (T14): eval harness (`agent_memory.eval`, `eval_entry.py`, DAB `eval_nightly`) validated on FEVM dev — `retrieval_keyword_recall_avg=0.583` logged to MLflow. Fix: shipped `eval_cases.json` as package data (importlib.resources) since a wheel task has no repo-root data dir. Follow-up T17 on recall metric semantics
- 2026-06-03 — T20 done: removed the "New session" button; session rollover is now implicit. Switching client or advisor rotates the session only when the current one holds a conversation (turns persist as they're sent, so an unused session has no DB rows — its id is carried over, never minting empty sessions). A hard browser refresh remains the explicit "force new session" path. Also dropped the Session id chip from the context bar — a UUID is meaningless to an advisor and there's nothing to act on now that rollover is implicit (session_id still drives the transcript view + audit trail). Dropped the now-orphaned `.context-actions` and `.session-id` CSS
- 2026-06-03 — T19 done: distillation is now incremental — a client is skipped (`skipped_no_new_turns`) unless a new episodic `turn_id` has landed since its last distillation. Re-running the LLM on unchanged turns only produced non-deterministic churn (reworded profiles, superseded proposals) with no new signal. High-water mark: proposals' `source_turn_ids` in HITL mode (the nightly job never commits to Delta), the committed profile's in direct-Delta mode. Gate applies to nightly *and* the manual UI trigger; the trigger poll now reads `GET /api/distill/{run_id}` and, when the run finishes with no new proposal, tells the advisor "no new conversations since the last proposal" instead of spinning to timeout
- 2026-06-03 — T18 done: distillation now supersedes prior pending proposals per client (new 'superseded' status, self-healing CHECK migration in `ensure_profile_proposals`, audit row per supersession). Validated on FEVM dev — 15 stale proposals superseded, pending-per-client capped at 1
- 2026-06-03 — M9 UI polish: app SP granted CAN_MANAGE_RUN on the HITL job (persisted in `deploy_bundle.sh`) so "Trigger distillation" works as the SP; proposal cards show word-level diff (changes only) vs the committed profile; source turns dropped from the UI; trigger auto-polls and surfaces the new card (no manual refresh); Refresh button removed; manual no-LLM "Edit profile" → `PUT /api/clients/{id}/profile` commits to Delta with an advisor-attributed audit row. Follow-up T18 (proposal supersession)
