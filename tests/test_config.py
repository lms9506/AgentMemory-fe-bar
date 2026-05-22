"""Tests for environment loading."""

from unittest.mock import MagicMock, patch

from agent_memory.config import (
    Settings,
    _infer_profile_from_host,
    _normalize_host,
    _normalize_token,
    ensure_databricks_auth,
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


def test_ensure_databricks_auth_rejects_invalid_env_token(monkeypatch):
    monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)
    monkeypatch.delenv("DATABRICKS_HOST", raising=False)
    settings = Settings(
        databricks_host="https://e2-demo-field-eng.cloud.databricks.com",
        databricks_token="stale-token",
        databricks_profile="e2-demo-field-eng",
        fm_api_endpoint="x",
        fm_api_embedding_endpoint="y",
        mlflow_experiment_name="/test",
        uc_catalog="c",
        uc_schema="s",
        lakebase_database=None,
        lakebase_conninfo=None,
    )
    with patch("agent_memory.config._workspace_auth_ok", return_value=False):
        with patch("databricks.sdk.WorkspaceClient") as mock_client:
            mock_client.return_value.current_user.me.return_value = MagicMock()
            mock_client.return_value.config.host = settings.databricks_host
            mock_client.return_value.config.token = "fresh-token"
            assert ensure_databricks_auth(settings) is True
    assert mock_client.call_args[1]["profile"] == "e2-demo-field-eng"


def test_ensure_databricks_auth_accepts_valid_env_token(monkeypatch):
    monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)
    monkeypatch.delenv("DATABRICKS_HOST", raising=False)
    settings = Settings(
        databricks_host="https://e2-demo-field-eng.cloud.databricks.com",
        databricks_token="good-token",
        databricks_profile=None,
        fm_api_endpoint="x",
        fm_api_embedding_endpoint="y",
        mlflow_experiment_name="/test",
        uc_catalog="c",
        uc_schema="s",
        lakebase_database=None,
        lakebase_conninfo=None,
    )
    with patch("agent_memory.config._workspace_auth_ok", return_value=True):
        assert ensure_databricks_auth(settings) is True
    assert (
        __import__("os").environ["DATABRICKS_HOST"]
        == "https://e2-demo-field-eng.cloud.databricks.com"
    )
    assert __import__("os").environ["DATABRICKS_TOKEN"] == "good-token"
