# Lakeflow job run — end-to-end execution summary

_Captured 2026-08-28 from the FEVM `solacc` workspace (`databricks jobs get-run`)._

The `agent-memory-dossier-ingest` job runs the batch journey as three chained tasks.
Final successful run:

**Job:** `agent-memory-dossier-ingest-dev` (job_id `550242014432751`) · **Run** `375148961920963` · **Result: SUCCESS**

| Task | Type | Result | Task run_id |
| --- | --- | --- | --- |
| `run_pipeline` | Lakeflow declarative pipeline (`8ceb1936-15f7-46d4-85d0-5e320b7a5cd9`) | **SUCCESS** | 680914570441926 |
| `hydrate_lakebase` | Python wheel (`hydrate`) | **SUCCESS** | 1030385916695009 |
| `distill_profiles` | Python wheel (`distill`) | **SUCCESS** | 861865460190246 |

## What each task produced (see the other evidence files)

- **run_pipeline** — Auto Loader ingested 58 raw files from the UC Volume `_landing/` zone into
  `bronze_raw_artifacts` (58 rows), then `silver_parsed_artifacts` (58 rows) via `ai_parse_document`
  + `ai_query`. 15 scanned/printed/handwritten docs went through OCR at **0.971 mean confidence**;
  43 typed notes through the text path. → `01_lakeflow_tables.md`
- **hydrate_lakebase** — loaded all 58 silver rows into Lakebase Postgres + pgvector: 58 artifacts,
  58 embedded chunks (1024-d), 13 clients, 58 job-attributed audit rows. → `02_lakebase_hydration.md`
- **distill_profiles** — consolidated the hydrated dossier into the governed Delta `client_profile`
  table: 13 distilled long-term profiles. → `03_client_profiles.md`

Then queried in natural language via the Genie space → `04_genie_transcript.md`.

## Reproduce

```bash
uv run python scripts/seed_landing.py --extra-clients 10   # stage synthetic raw files
databricks bundle run dossier_ingest_job --target dev       # this 3-task run
```

Deployed to workspace `https://fevm-serverless-stable-solacc.cloud.databricks.com`,
catalog `serverless_stable_solacc_catalog`, schema `wealth_advisor`.
