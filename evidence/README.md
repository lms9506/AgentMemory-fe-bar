# Execution evidence — batch bulk-onboarding journey

Text-readable proof that the Lakeflow batch journey (ADR-0019) actually ran on a
live Databricks workspace. The FE-bar evaluator reads **text only** — every file
here is committed Markdown containing real row counts, query results, and model
output (not screenshots).

The journey, and where each stage's evidence lives:

| Stage | Tool | Evidence file |
|---|---|---|
| Ingest raw + govern | Lakeflow pipeline → Unity Catalog Delta | `01_lakeflow_tables.md` |
| Make intelligent | `ai_parse_document` + `ai_query` (in-pipeline) | `01_lakeflow_tables.md` (OCR samples) |
| Operational serving | Lakebase Postgres + pgvector | `02_lakebase_hydration.md` |
| Distill long-term memory | Delta `client_profile` | `03_client_profiles.md` |
| Query in natural language | Genie | `04_genie_transcript.md` |
| Pipeline run status | Lakeflow job | `00_pipeline_run.md` |

## Regenerating

After a successful `agent-memory-dossier-ingest` job run (see
`notebooks/03_bulk_onboard.py`):

```bash
# Delta + Lakebase evidence (01–03), programmatically:
uv run python evidence/generate_evidence.py
```

- `00_pipeline_run.md` — paste the job/pipeline run summary (state, task results,
  tables updated, event-log excerpt) from `databricks bundle run dossier_ingest_job`
  or the Jobs UI run page.
- `04_genie_transcript.md` — the Genie space's natural-language Q → generated SQL →
  result rows, captured from the Genie space created by `scripts/setup_genie.py`.

All data is synthetic (CLAUDE.md rule 6) — the personas and generated clients carry
no real PII.
