"""Job entrypoint: hydrate Lakebase from the Lakeflow silver table (ADR-0019).

This is the third tier of the batch bulk-onboarding journey. The Lakeflow
pipeline (`databricks/pipelines/dossier_ingest.py`) has already landed raw bytes
in the UC Volume and produced the governed `silver_parsed_artifacts` Delta table
(extracted text + per-artifact summary). This task reads that silver table and
loads Lakebase pgvector — the operational serving tier the advisor app queries.

For each silver row it reuses the SAME store/embedding primitives as the
interactive ingest path, so a batch-onboarded artifact is indistinguishable from
a drag-dropped one once it lands in Lakebase:

    upsert_client → find_by_hash (dedup) → ingest_artifact (row + audit)
    → chunk_text → embed_texts → write_chunks → job-attributed audit row

Idempotent: a re-run skips artifacts whose (client_id, content_hash) already
exist in Lakebase, so the job is safe to retry.
"""

from __future__ import annotations

import argparse
import logging
import os

from agent_memory.config import Settings, establish_runtime_auth
from agent_memory.memory.embeddings import embed_texts
from agent_memory.memory.extraction import chunk_text
from agent_memory.memory.sql_warehouse import fetch_sql
from agent_memory.memory.store import LakebaseArtifactStore

_LOG = logging.getLogger(__name__)

_BATCH_ADVISOR_ID = "batch_onboarding"


def _pretty_display_name(client_id: str) -> str:
    """`client_1000` -> `Client 1000`. Batch clients carry no name through the pipeline."""
    return client_id.replace("_", " ").strip().title() or client_id


def _read_silver(settings: Settings, *, catalog: str, schema: str) -> list[dict[str, str | None]]:
    """Pull the parsed silver rows the pipeline produced."""
    table = f"{catalog}.{schema}.silver_parsed_artifacts"
    sql = (
        "SELECT client_id, original_filename, kind, content_hash, path, "
        "extracted_text, summary "
        f"FROM {table} "
        "WHERE extracted_text IS NOT NULL AND length(extracted_text) > 0"
    )
    rows = fetch_sql(sql, settings=settings)
    cols = ["client_id", "original_filename", "kind", "content_hash", "path", "extracted_text", "summary"]
    return [dict(zip(cols, row, strict=False)) for row in rows]


def hydrate(settings: Settings | None = None) -> dict[str, int]:
    """Load every silver artifact into Lakebase. Returns run counts."""
    cfg = settings or Settings.from_env()
    establish_runtime_auth(cfg)  # covers serverless job (ambient creds) + local/notebook
    # establish_runtime_auth backfills DATABRICKS_HOST/TOKEN into the env; re-read
    # Settings so the (frozen) cfg reflects them for the SQL-warehouse auth gate.
    # Only when we built cfg ourselves — an explicit caller (tests) keeps its object.
    if settings is None:
        cfg = Settings.from_env()

    store = LakebaseArtifactStore()
    silver_rows = _read_silver(cfg, catalog=cfg.uc_catalog, schema=cfg.uc_schema)
    _LOG.info("hydrate: %d silver rows to consider", len(silver_rows))

    counts = {"seen": len(silver_rows), "ingested": 0, "deduped": 0, "chunks": 0, "clients": 0}
    seen_clients: set[str] = set()

    for row in silver_rows:
        client_id = row["client_id"]
        content_hash = row["content_hash"]
        if not client_id or not content_hash:
            continue

        if client_id not in seen_clients:
            store.upsert_client(client_id, _pretty_display_name(client_id))
            seen_clients.add(client_id)
            counts["clients"] += 1

        # Idempotent: skip artifacts already in Lakebase (safe re-runs).
        if store.find_by_hash(client_id=client_id, content_hash=content_hash) is not None:
            counts["deduped"] += 1
            continue

        kind = row["kind"] or "other"
        extracted_text = row["extracted_text"] or ""
        record = store.ingest_artifact(
            client_id=client_id,
            advisor_id=_BATCH_ADVISOR_ID,
            kind=kind,  # type: ignore[arg-type]
            original_filename=row["original_filename"] or "unknown",
            volume_path=row["path"] or "",
            content_hash=content_hash,
            extracted_text=extracted_text,
            summary=row["summary"],
        )
        counts["ingested"] += 1

        chunks = chunk_text(
            extracted_text,
            chunk_tokens=cfg.chunk_tokens,
            overlap_tokens=cfg.chunk_overlap_tokens,
        )
        if chunks:
            embeddings = embed_texts(chunks, settings=cfg)
            counts["chunks"] += store.write_chunks(
                artifact_id=record.artifact_id,
                client_id=client_id,
                chunks=chunks,
                embeddings=embeddings,
            )

        # Every LTM write needs an audit row (CLAUDE.md rule 3). ingest_artifact
        # already logs an advisor-attributed row; add a job-attributed one so the
        # batch provenance is explicit and distinguishable from interactive ingest.
        store.write_audit(
            actor="agent-memory-dossier-ingest",
            actor_kind="job",
            action="bulk_onboard_artifact",
            target_ref=f"client:{client_id}/artifact:{record.artifact_id}",
            payload={
                "artifact_id": record.artifact_id,
                "kind": kind,
                "content_hash": content_hash,
                "source": "lakeflow.silver_parsed_artifacts",
            },
        )

    _LOG.info("hydrate complete: %s", counts)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hydrate Lakebase from the Lakeflow silver_parsed_artifacts Delta table."
    )
    # Named params injected by the DAB job spec (serverless has no spark_env_vars).
    parser.add_argument("--databricks-host")
    parser.add_argument("--uc-catalog")
    parser.add_argument("--uc-schema")
    parser.add_argument("--warehouse-id")
    parser.add_argument("--fm-embedding-endpoint")
    parser.add_argument("--lakebase-instance-name")
    parser.add_argument("--lakebase-url")
    parser.add_argument("--lakebase-database")
    args = parser.parse_args()

    _setenv = lambda k, v: os.environ.setdefault(k, v) if v else None  # noqa: E731
    _setenv("DATABRICKS_HOST", args.databricks_host)
    _setenv("UC_CATALOG", args.uc_catalog)
    _setenv("UC_SCHEMA", args.uc_schema)
    _setenv("DATABRICKS_SQL_WAREHOUSE_ID", args.warehouse_id)
    _setenv("FM_API_EMBEDDING_ENDPOINT", args.fm_embedding_endpoint)
    _setenv("LAKEBASE_INSTANCE_NAME", args.lakebase_instance_name)
    _setenv("LAKEBASE_URL", args.lakebase_url)
    _setenv("LAKEBASE_DATABASE", args.lakebase_database)

    counts = hydrate()
    print(f"hydrate complete: {counts}")


if __name__ == "__main__":
    main()
