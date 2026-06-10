# Setup notebooks — non-expert deploy path

Three notebooks that take a workspace from zero to a running demo. Run them in order.

## Run order

1. `00_setup.py` — Create UC Volume; apply Lakebase schema (`artifacts`, `artifact_chunks`, `audit_log`, `profile_proposals`, `clients`); apply Delta schema (`client_profile`); grant `READ VOLUME` + `WRITE VOLUME` to the app service principal.
2. `01_seed.py` — Register synthetic clients; generate dossier artifacts (meeting notes, statements, questionnaires) via the synthetic generator; ingest each one through the full ingest pipeline (raw save → extraction → chunk/embed → summary).
3. `02_demo.py` — Walk the four advisor UI panels: Dossier Timeline, Semantic Query, Distillation → Proposal, Provenance download.

## Prerequisites

- UC catalog and schema already created (e.g. `agent_memory_dev.wealth_advisor`).
- Lakebase instance provisioned and `LAKEBASE_CONNINFO` set in `.env` or notebook params.
- SQL warehouse running and set to **always-on** for the demo — warehouse cold-start adds 30–60s to the first `ai_parse_document` call. Set `DATABRICKS_SQL_WAREHOUSE_ID`.
- App service principal has `USE CATALOG`, `USE SCHEMA`, `SELECT`/`MODIFY` on the schema, and `READ VOLUME` + `WRITE VOLUME` on the Volume.

## Parameters

Each notebook has a `# Parameters` cell at the top. Edit `CATALOG`, `SCHEMA`, `LAKEBASE_CONNINFO`, and `APP_SERVICE_PRINCIPAL` before running. The defaults match the `dev` DABs target.

## Notes

- These notebooks are for humans running a deploy or customer demo — they are not imported by any module. Reusable logic belongs in `src/agent_memory/`.
- Notebook format is Databricks source (plain `.py` with `# Databricks notebook source` header and `# COMMAND ----------` separators) so they sync cleanly via `databricks bundle deploy`.
