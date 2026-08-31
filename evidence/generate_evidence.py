"""Generate text-readable execution evidence for the batch journey (ADR-0019).

The FE-bar evaluator reads TEXT only — screenshots don't count. This script runs
after the `agent-memory-dossier-ingest` job and captures, as committed Markdown:

  01_lakeflow_tables.md   bronze/silver row counts + a parsed OCR sample (model output)
  02_lakebase_hydration.md Lakebase artifact/chunk/audit counts + a sample chunk
  03_client_profiles.md    distilled client_profile rows (Delta, model output)

Genie transcripts are captured separately (see evidence/README.md) because they
need the Conversation API + a space id.

Run against the live workspace (needs the same .env as the app):
    uv run python evidence/generate_evidence.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agent_memory.config import Settings, ensure_databricks_auth
from agent_memory.memory.connection import lakebase_connection
from agent_memory.memory.sql_warehouse import fetch_sql

_OUT = Path(__file__).resolve().parent


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for r in rows:
        cells = [str(c).replace("|", "\\|").replace("\n", " ") if c is not None else "" for c in r]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def _sql(settings: Settings, statement: str) -> list[list[str | None]]:
    return fetch_sql(statement, settings=settings)


def _header(title: str) -> str:
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"# {title}\n\n_Generated {ts} by `evidence/generate_evidence.py` against the live FEVM workspace._\n"


def lakeflow_tables(settings: Settings) -> str:
    cat, sch = settings.uc_catalog, settings.uc_schema
    counts = _sql(
        settings,
        f"""SELECT 'bronze_raw_artifacts' t, count(*) n FROM {cat}.{sch}.bronze_raw_artifacts
            UNION ALL SELECT 'silver_parsed_artifacts', count(*) FROM {cat}.{sch}.silver_parsed_artifacts""",
    )
    by_method = _sql(
        settings,
        f"""SELECT extract_method, count(*) n, round(avg(mean_confidence),3) avg_conf
            FROM {cat}.{sch}.silver_parsed_artifacts GROUP BY extract_method ORDER BY extract_method""",
    )
    ocr = _sql(
        settings,
        f"""SELECT client_id, original_filename, kind, round(mean_confidence,3) conf,
                   substr(extracted_text,1,240), substr(summary,1,320)
            FROM {cat}.{sch}.silver_parsed_artifacts
            WHERE extract_method='ai_parse_document'
            ORDER BY mean_confidence DESC LIMIT 4""",
    )
    parts = [
        _header("Lakeflow pipeline — governed Delta output"),
        "The Lakeflow declarative pipeline landed raw Volume files into Unity Catalog "
        "Delta tables (`bronze_raw_artifacts` → `silver_parsed_artifacts`).\n",
        "## Row counts",
        _md_table(["table", "rows"], counts),
        "\n## Extraction method (GenAI: `ai_parse_document` vs plain text)",
        _md_table(["extract_method", "rows", "avg_ocr_confidence"], by_method),
        "\n## Parsed OCR samples (`ai_parse_document` model output)",
        "Scanned/handwritten documents, text extracted + summarized in-pipeline:\n",
        _md_table(["client", "file", "kind", "ocr_conf", "extracted_text (240c)", "summary (320c)"], ocr),
    ]
    return "\n".join(parts) + "\n"


def lakebase_hydration(settings: Settings) -> str:
    with lakebase_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM artifacts")
        n_artifacts = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM artifact_chunks")
        n_chunks = cur.fetchone()[0]
        cur.execute("SELECT count(DISTINCT client_id) FROM artifacts")
        n_clients = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM audit_log WHERE action='bulk_onboard_artifact'")
        n_audit = cur.fetchone()[0]
        cur.execute(
            "SELECT client_id, count(*) FROM artifacts GROUP BY client_id ORDER BY client_id LIMIT 20"
        )
        per_client = [[str(r[0]), str(r[1])] for r in cur.fetchall()]
        cur.execute(
            "SELECT artifact_id, chunk_index, array_length(embedding::real[], 1), left(content, 160) "
            "FROM artifact_chunks ORDER BY chunk_id LIMIT 3"
        )
        sample_chunks = [[str(r[0]), str(r[1]), str(r[2]), str(r[3])] for r in cur.fetchall()]
    parts = [
        _header("Lakebase (operational serving) — hydration output"),
        "The `hydrate` job task loaded the silver rows into Lakebase Postgres + pgvector "
        "(the tier the advisor app queries for recall).\n",
        "## Counts",
        _md_table(
            ["metric", "value"],
            [
                ["artifacts", str(n_artifacts)],
                ["artifact_chunks", str(n_chunks)],
                ["distinct clients", str(n_clients)],
                ["job-attributed audit rows (bulk_onboard_artifact)", str(n_audit)],
            ],
        ),
        "\n## Artifacts per client",
        _md_table(["client_id", "artifacts"], per_client),
        "\n## Sample embedded chunks (pgvector; embedding dimension shown)",
        _md_table(["artifact_id", "chunk_index", "embedding_dims", "content (160c)"], sample_chunks),
    ]
    return "\n".join(parts) + "\n"


def client_profiles(settings: Settings) -> str:
    cat, sch = settings.uc_catalog, settings.uc_schema
    rows = _sql(
        settings,
        f"""SELECT client_id, risk_tolerance,
                   array_join(investment_goals, ', '),
                   substr(summary,1,400)
            FROM {cat}.{sch}.client_profile ORDER BY client_id LIMIT 10""",
    )
    return "\n".join(
        [
            _header("Distilled client profiles (Delta long-term memory — model output)"),
            "The `distill` job task consolidated the hydrated dossier into the governed "
            "`client_profile` Delta table (versioned via time travel).\n",
            _md_table(["client_id", "risk_tolerance", "investment_goals", "summary (400c)"], rows),
        ]
    ) + "\n"


def main() -> None:
    settings = Settings.from_env()
    if not ensure_databricks_auth(settings):
        raise SystemExit(f"Databricks auth failed. {settings.auth_diagnostics()}")

    writers = {
        "01_lakeflow_tables.md": lakeflow_tables,
        "02_lakebase_hydration.md": lakebase_hydration,
        "03_client_profiles.md": client_profiles,
    }
    for filename, fn in writers.items():
        try:
            (_OUT / filename).write_text(fn(settings), encoding="utf-8")
            print(f"wrote evidence/{filename}")
        except Exception as exc:  # keep going so one failure doesn't lose the rest
            print(f"SKIP evidence/{filename}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
