"""Lakebase DDL helpers — idempotent schema pieces and statement splitting."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import psycopg


# Canonical schema: databricks/lakebase_schema.sql. Keep in sync.
AUDIT_LOG_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
    event_id    BIGSERIAL PRIMARY KEY,
    actor       TEXT      NOT NULL,
    actor_kind  TEXT      NOT NULL CHECK (actor_kind IN ('agent', 'advisor', 'job')),
    action      TEXT      NOT NULL,
    target_ref  TEXT      NOT NULL,
    payload     JSONB     NOT NULL,
    agent_run_id TEXT,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_log (target_ref, ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor  ON audit_log (actor, ts DESC);
"""


def schema_sql_path() -> Path:
    return Path(__file__).resolve().parents[3] / "databricks" / "lakebase_schema.sql"


def split_sql_statements(sql: str) -> list[str]:
    """Split a SQL file into executable statements (skips comment-only lines)."""
    parts: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            parts.append("\n".join(buf))
            buf = []
    if buf:
        parts.append("\n".join(buf))
    return parts


CLIENTS_DDL = """
CREATE TABLE IF NOT EXISTS clients (
    client_id    TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def ensure_clients_table(cur: psycopg.Cursor) -> None:
    """Create `clients` if missing (safe to call inside an open transaction)."""
    cur.execute(
        "SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'clients'"
    )
    if cur.fetchone():
        return
    cur.execute("SAVEPOINT _ensure_clients")
    try:
        cur.execute(CLIENTS_DDL)
        cur.execute("RELEASE SAVEPOINT _ensure_clients")
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT _ensure_clients")
        cur.execute("RELEASE SAVEPOINT _ensure_clients")


# source_turn_ids renamed to source_artifact_ids (type unchanged: BIGINT[]).
PROPOSAL_DDL = """
CREATE TABLE IF NOT EXISTS profile_proposals (
    proposal_id  TEXT        PRIMARY KEY,
    client_id    TEXT        NOT NULL,
    proposed_profile JSONB   NOT NULL,
    source_artifact_ids BIGINT[] NOT NULL DEFAULT '{}',
    status       TEXT        NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'accepted', 'rejected', 'superseded')),
    proposed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at  TIMESTAMPTZ,
    reviewed_by  TEXT,
    run_id       TEXT
);
CREATE INDEX IF NOT EXISTS idx_proposals_client_status ON profile_proposals (client_id, status);
"""


def ensure_profile_proposals(cur: psycopg.Cursor) -> None:
    """Create `profile_proposals` if missing; reconcile the status CHECK for T18.

    Safe to call inside an open transaction. When the table predates the
    'superseded' status, the CHECK is migrated once (no-op thereafter).
    Also migrates source_turn_ids -> source_artifact_ids if the old column name exists.
    """
    cur.execute(
        "SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'profile_proposals'"
    )
    if not cur.fetchone():
        for statement in split_sql_statements(PROPOSAL_DDL):
            cur.execute("SAVEPOINT _ensure_proposals")
            try:
                cur.execute(statement)  # type: ignore[arg-type]  # str from trusted DDL constant; psycopg wants LiteralString
                cur.execute("RELEASE SAVEPOINT _ensure_proposals")
            except Exception:
                cur.execute("ROLLBACK TO SAVEPOINT _ensure_proposals")
                cur.execute("RELEASE SAVEPOINT _ensure_proposals")
        return

    # Table exists: migrate source_turn_ids -> source_artifact_ids if needed.
    cur.execute("SAVEPOINT _mig_col_rename")
    try:
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'profile_proposals'
              AND column_name = 'source_turn_ids'
            """
        )
        if cur.fetchone():
            cur.execute(
                "ALTER TABLE profile_proposals RENAME COLUMN source_turn_ids TO source_artifact_ids"
            )
        cur.execute("RELEASE SAVEPOINT _mig_col_rename")
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT _mig_col_rename")
        cur.execute("RELEASE SAVEPOINT _mig_col_rename")

    # Migrate the status CHECK to allow 'superseded' once, if needed.
    cur.execute("SAVEPOINT _mig_proposals")
    try:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid = 'profile_proposals'::regclass
              AND contype = 'c' AND conname = 'profile_proposals_status_check'
            """
        )
        row = cur.fetchone()
        if row and "superseded" not in row[0]:
            cur.execute(
                "ALTER TABLE profile_proposals DROP CONSTRAINT profile_proposals_status_check"
            )
            cur.execute(
                "ALTER TABLE profile_proposals ADD CONSTRAINT profile_proposals_status_check "
                "CHECK (status IN ('pending', 'accepted', 'rejected', 'superseded'))"
            )
        cur.execute("RELEASE SAVEPOINT _mig_proposals")
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT _mig_proposals")
        cur.execute("RELEASE SAVEPOINT _mig_proposals")


def ensure_audit_log(cur: psycopg.Cursor) -> None:
    """Create `audit_log` if missing (safe to call inside an open transaction).

    When the app service principal doesn't own the table, CREATE INDEX fails
    with InsufficientPrivilege. Use a savepoint per statement so only that
    statement rolls back — not the surrounding transaction (which holds the
    artifacts insert we must not lose).
    """
    cur.execute(
        "SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'audit_log'"
    )
    if cur.fetchone():
        return  # table + indexes already exist; skip all DDL
    for statement in split_sql_statements(AUDIT_LOG_DDL):
        cur.execute("SAVEPOINT _ensure_audit_log")
        try:
            cur.execute(statement)  # type: ignore[arg-type]  # str from trusted DDL constant; psycopg wants LiteralString
            cur.execute("RELEASE SAVEPOINT _ensure_audit_log")
        except Exception:
            cur.execute("ROLLBACK TO SAVEPOINT _ensure_audit_log")
            cur.execute("RELEASE SAVEPOINT _ensure_audit_log")


# Episodic memory — dossier artifacts (D1).
ARTIFACTS_DDL = """
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id      BIGSERIAL    PRIMARY KEY,
    client_id        TEXT         NOT NULL,
    advisor_id       TEXT         NOT NULL,
    kind             TEXT         NOT NULL CHECK (kind IN ('pdf','image','docx','text','other')),
    original_filename TEXT        NOT NULL,
    volume_path      TEXT         NOT NULL,
    content_hash     TEXT         NOT NULL,
    extracted_text   TEXT,
    summary          TEXT,
    sensitivity_tags TEXT[]       NOT NULL DEFAULT '{}',
    ingested_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_hash   ON artifacts (client_id, content_hash);
CREATE INDEX        IF NOT EXISTS idx_artifacts_client ON artifacts (client_id, ingested_at DESC);
"""

# Semantic memory — chunk embeddings (D1).
ARTIFACT_CHUNKS_DDL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS artifact_chunks (
    chunk_id    BIGSERIAL    PRIMARY KEY,
    artifact_id BIGINT       NOT NULL REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
    client_id   TEXT         NOT NULL,
    chunk_index INT          NOT NULL,
    content     TEXT         NOT NULL,
    embedding   VECTOR(1024) NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chunks_artifact ON artifact_chunks (artifact_id);
CREATE INDEX IF NOT EXISTS idx_chunks_client   ON artifact_chunks (client_id);
CREATE INDEX IF NOT EXISTS idx_chunks_ann      ON artifact_chunks
    USING hnsw (embedding vector_cosine_ops);
"""


def ensure_artifacts(cur: psycopg.Cursor) -> None:
    """Create `artifacts` table + indexes if missing (savepoint-per-statement, idempotent).

    The DDL uses ``CREATE TABLE/INDEX IF NOT EXISTS`` so this is safe to call
    repeatedly; the savepoint-per-statement pattern lets each statement fail
    independently (e.g. an index CREATE when the app SP lacks USAGE privilege)
    without aborting the surrounding transaction.
    """
    for statement in split_sql_statements(ARTIFACTS_DDL):
        cur.execute("SAVEPOINT _ensure_artifacts")
        try:
            cur.execute(statement)  # type: ignore[arg-type]  # str from trusted DDL constant; psycopg wants LiteralString
            cur.execute("RELEASE SAVEPOINT _ensure_artifacts")
        except Exception:
            cur.execute("ROLLBACK TO SAVEPOINT _ensure_artifacts")
            cur.execute("RELEASE SAVEPOINT _ensure_artifacts")


def ensure_artifact_chunks(cur: psycopg.Cursor) -> None:
    """Create `artifact_chunks` table + indexes if missing (savepoint-per-statement, idempotent).

    Depends on `artifacts` existing; call ensure_artifacts first.
    The DDL uses ``CREATE TABLE/INDEX IF NOT EXISTS`` so this is safe to call
    repeatedly; the savepoint-per-statement pattern lets each statement fail
    independently without aborting the surrounding transaction.
    """
    for statement in split_sql_statements(ARTIFACT_CHUNKS_DDL):
        cur.execute("SAVEPOINT _ensure_artifact_chunks")
        try:
            cur.execute(statement)  # type: ignore[arg-type]  # str from trusted DDL constant; psycopg wants LiteralString
            cur.execute("RELEASE SAVEPOINT _ensure_artifact_chunks")
        except Exception:
            cur.execute("ROLLBACK TO SAVEPOINT _ensure_artifact_chunks")
            cur.execute("RELEASE SAVEPOINT _ensure_artifact_chunks")
