"""Tests for environment loading."""

from agent_memory.config import (
    Settings,
    _infer_profile_from_host,
    _normalize_host,
    _normalize_token,
)


def test_normalize_token_strips_angle_brackets():
    assert _normalize_token("<abc123>") == "abc123"


def test_normalize_token_empty():
    assert _normalize_token("") is None
    assert _normalize_token('""') is None
    assert _normalize_token(None) is None


def test_normalize_host_strips_query():
    assert (
        _normalize_host("https://e2-demo-field-eng.cloud.databricks.com/?o=123")
        == "https://e2-demo-field-eng.cloud.databricks.com"
    )


def test_infer_profile_from_host():
    assert (
        _infer_profile_from_host("https://e2-demo-field-eng.cloud.databricks.com")
        == "e2-demo-field-eng"
    )


def test_settings_configured_with_profile_only():
    s = Settings(
        databricks_host="https://e2-demo-field-eng.cloud.databricks.com",
        databricks_token=None,
        databricks_profile="e2-demo-field-eng",
        fm_api_endpoint="x",
        fm_api_embedding_endpoint="y",
        mlflow_experiment_name="/test",
        uc_catalog="c",
        uc_schema="s",
        lakebase_database=None,
        lakebase_conninfo=None,
    )
    assert s.databricks_configured
