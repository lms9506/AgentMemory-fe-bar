"""Tests for Lakebase DDL constants and ensure_* functions.

Contract source: interfaces.md §1 (Lakebase DDL).
Additions: ARTIFACTS_DDL, ARTIFACT_CHUNKS_DDL, ensure_artifacts, ensure_artifact_chunks,
           PROPOSAL_DDL uses source_artifact_ids (not source_turn_ids).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent_memory.memory.lakebase_ddl import grant_app_sp, split_sql_statements

# ---------------------------------------------------------------------------
# Existing: split_sql_statements (unchanged)
# ---------------------------------------------------------------------------

def test_split_sql_statements_includes_audit_log():
    sql = """
    -- comment
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE TABLE IF NOT EXISTS audit_log (event_id BIGSERIAL PRIMARY KEY);
    CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_log (target_ref);
    """
    statements = split_sql_statements(sql)
    assert len(statements) == 3
    assert "audit_log" in statements[1]


# ---------------------------------------------------------------------------
# ARTIFACTS_DDL constant presence and correctness
# ---------------------------------------------------------------------------

def test_artifacts_ddl_constant_exists():
    from agent_memory.memory.lakebase_ddl import ARTIFACTS_DDL

    assert isinstance(ARTIFACTS_DDL, str)
    assert len(ARTIFACTS_DDL) > 0


def test_artifacts_ddl_creates_artifacts_table():
    from agent_memory.memory.lakebase_ddl import ARTIFACTS_DDL

    assert "artifacts" in ARTIFACTS_DDL.lower()
    assert "CREATE TABLE" in ARTIFACTS_DDL.upper()


def test_artifacts_ddl_has_required_columns():
    from agent_memory.memory.lakebase_ddl import ARTIFACTS_DDL

    ddl_upper = ARTIFACTS_DDL.upper()
    required_cols = [
        "ARTIFACT_ID",
        "CLIENT_ID",
        "ADVISOR_ID",
        "KIND",
        "ORIGINAL_FILENAME",
        "VOLUME_PATH",
        "CONTENT_HASH",
        "EXTRACTED_TEXT",
        "SUMMARY",
        "SENSITIVITY_TAGS",
        "INGESTED_AT",
    ]
    for col in required_cols:
        assert col in ddl_upper, f"Missing column: {col}"


def test_artifacts_ddl_has_kind_check_constraint():
    from agent_memory.memory.lakebase_ddl import ARTIFACTS_DDL

    assert "pdf" in ARTIFACTS_DDL
    assert "image" in ARTIFACTS_DDL
    assert "docx" in ARTIFACTS_DDL
    assert "text" in ARTIFACTS_DDL
    assert "other" in ARTIFACTS_DDL


def test_artifacts_ddl_has_content_hash_unique_index():
    from agent_memory.memory.lakebase_ddl import ARTIFACTS_DDL

    # Must have a unique index on (client_id, content_hash) for dedup
    assert "UNIQUE" in ARTIFACTS_DDL.upper() or "idx_artifacts_hash" in ARTIFACTS_DDL


# ---------------------------------------------------------------------------
# ARTIFACT_CHUNKS_DDL constant
# ---------------------------------------------------------------------------

def test_artifact_chunks_ddl_constant_exists():
    from agent_memory.memory.lakebase_ddl import ARTIFACT_CHUNKS_DDL

    assert isinstance(ARTIFACT_CHUNKS_DDL, str)
    assert len(ARTIFACT_CHUNKS_DDL) > 0


def test_artifact_chunks_ddl_creates_artifact_chunks_table():
    from agent_memory.memory.lakebase_ddl import ARTIFACT_CHUNKS_DDL

    assert "artifact_chunks" in ARTIFACT_CHUNKS_DDL.lower()
    assert "CREATE TABLE" in ARTIFACT_CHUNKS_DDL.upper()


def test_artifact_chunks_ddl_has_required_columns():
    from agent_memory.memory.lakebase_ddl import ARTIFACT_CHUNKS_DDL

    ddl_upper = ARTIFACT_CHUNKS_DDL.upper()
    required_cols = ["CHUNK_ID", "ARTIFACT_ID", "CLIENT_ID", "CHUNK_INDEX", "CONTENT", "EMBEDDING", "CREATED_AT"]
    for col in required_cols:
        assert col in ddl_upper, f"Missing column: {col}"


def test_artifact_chunks_ddl_has_1024d_vector():
    from agent_memory.memory.lakebase_ddl import ARTIFACT_CHUNKS_DDL

    assert "1024" in ARTIFACT_CHUNKS_DDL
    assert "VECTOR" in ARTIFACT_CHUNKS_DDL.upper()


def test_artifact_chunks_ddl_has_hnsw_index():
    from agent_memory.memory.lakebase_ddl import ARTIFACT_CHUNKS_DDL

    assert "hnsw" in ARTIFACT_CHUNKS_DDL.lower()
    assert "vector_cosine_ops" in ARTIFACT_CHUNKS_DDL.lower()


def test_artifact_chunks_ddl_has_foreign_key_to_artifacts():
    from agent_memory.memory.lakebase_ddl import ARTIFACT_CHUNKS_DDL

    assert "REFERENCES" in ARTIFACT_CHUNKS_DDL.upper()
    assert "artifacts" in ARTIFACT_CHUNKS_DDL.lower()


# ---------------------------------------------------------------------------
# PROPOSAL_DDL uses source_artifact_ids (not source_turn_ids)
# ---------------------------------------------------------------------------

def test_proposal_ddl_uses_source_artifact_ids():
    from agent_memory.memory.lakebase_ddl import PROPOSAL_DDL

    assert "source_artifact_ids" in PROPOSAL_DDL
    assert "source_turn_ids" not in PROPOSAL_DDL


def test_proposal_ddl_status_check_constraint_unchanged():
    from agent_memory.memory.lakebase_ddl import PROPOSAL_DDL

    # The constraint name and valid statuses must be preserved
    assert "pending" in PROPOSAL_DDL
    assert "accepted" in PROPOSAL_DDL
    assert "rejected" in PROPOSAL_DDL
    assert "superseded" in PROPOSAL_DDL


# ---------------------------------------------------------------------------
# ensure_artifacts function exists and calls cursor correctly
# ---------------------------------------------------------------------------

def test_ensure_artifacts_function_exists():
    from agent_memory.memory.lakebase_ddl import ensure_artifacts

    assert callable(ensure_artifacts)


def test_ensure_artifacts_calls_cursor():
    from agent_memory.memory.lakebase_ddl import ensure_artifacts

    mock_cur = MagicMock()
    # Must not raise and must call cursor methods (execute)
    ensure_artifacts(mock_cur)
    assert mock_cur.execute.called


def test_ensure_artifacts_uses_savepoint():
    """ensure_artifacts must follow the savepoint-per-statement pattern."""
    from agent_memory.memory.lakebase_ddl import ensure_artifacts

    mock_cur = MagicMock()
    ensure_artifacts(mock_cur)

    executed_statements = [call_args.args[0] for call_args in mock_cur.execute.call_args_list]
    # At least one SAVEPOINT statement must be present
    assert any("SAVEPOINT" in s.upper() for s in executed_statements)


# ---------------------------------------------------------------------------
# ensure_artifact_chunks function exists and calls cursor correctly
# ---------------------------------------------------------------------------

def test_ensure_artifact_chunks_function_exists():
    from agent_memory.memory.lakebase_ddl import ensure_artifact_chunks

    assert callable(ensure_artifact_chunks)


def test_ensure_artifact_chunks_calls_cursor():
    from agent_memory.memory.lakebase_ddl import ensure_artifact_chunks

    mock_cur = MagicMock()
    ensure_artifact_chunks(mock_cur)
    assert mock_cur.execute.called


def test_ensure_artifact_chunks_uses_savepoint():
    from agent_memory.memory.lakebase_ddl import ensure_artifact_chunks

    mock_cur = MagicMock()
    ensure_artifact_chunks(mock_cur)

    executed_statements = [call_args.args[0] for call_args in mock_cur.execute.call_args_list]
    assert any("SAVEPOINT" in s.upper() for s in executed_statements)


# ---------------------------------------------------------------------------
# Invariant: dead table DDL must be absent (no conversation_turns / turn_embeddings)
# ---------------------------------------------------------------------------

def test_no_conversation_turns_ddl():
    """Lakebase DDL must not contain the old table names."""
    from agent_memory.memory.lakebase_ddl import ARTIFACTS_DDL

    assert "conversation_turns" not in ARTIFACTS_DDL.lower()
    assert "turn_embeddings" not in ARTIFACTS_DDL.lower()


def test_no_turn_embeddings_ddl():
    from agent_memory.memory.lakebase_ddl import ARTIFACT_CHUNKS_DDL

    assert "turn_embeddings" not in ARTIFACT_CHUNKS_DDL.lower()
    assert "conversation_turns" not in ARTIFACT_CHUNKS_DDL.lower()


# ---------------------------------------------------------------------------
# grant_app_sp — app service-principal Lakebase grants (setup gap fix)
# ---------------------------------------------------------------------------

_APP_SP = "2ba28921-47d1-4dfa-a37e-b8be9dded04b"


def _executed_sql(cur: MagicMock) -> list[str]:
    return [c.args[0] for c in cur.execute.call_args_list]


def test_grant_app_sp_emits_expected_grants():
    cur = MagicMock()
    grant_app_sp(cur, _APP_SP)
    sql = " ".join(_executed_sql(cur))
    role = f'"{_APP_SP}"'
    # schema usage + sequence usage + rw tables + append-only audit_log
    assert f"GRANT USAGE ON SCHEMA public TO {role}" in sql
    assert f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}" in sql
    for t in ("artifacts", "artifact_chunks", "profile_proposals", "clients"):
        assert f"GRANT SELECT, INSERT, UPDATE, DELETE ON {t} TO {role}" in sql
    # audit_log is append-only: SELECT+INSERT only, never UPDATE/DELETE
    assert f"GRANT SELECT, INSERT ON audit_log TO {role}" in sql
    assert "UPDATE, DELETE ON audit_log" not in sql


def test_grant_app_sp_uses_savepoints():
    cur = MagicMock()
    grant_app_sp(cur, _APP_SP)
    sql = _executed_sql(cur)
    assert sql.count("SAVEPOINT _grant_app_sp") == sql.count("RELEASE SAVEPOINT _grant_app_sp")
    assert any(s.startswith("SAVEPOINT") for s in sql)


@pytest.mark.parametrize("bad", ["", "not-a-uuid", "robert'); DROP TABLE clients;--", "abc"])
def test_grant_app_sp_rejects_non_uuid_role(bad):
    cur = MagicMock()
    with pytest.raises(ValueError, match="UUID role name"):
        grant_app_sp(cur, bad)
    cur.execute.assert_not_called()  # nothing executed on invalid input
