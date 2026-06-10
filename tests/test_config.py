"""Tests for environment loading and Settings fields.

Extended for dossier model: 6 new Settings fields per interfaces.md §Config.
"""

from unittest.mock import MagicMock, patch

import pytest

from agent_memory.config import (
    Settings,
    _infer_profile_from_host,
    _normalize_host,
    _normalize_token,
    _reset_auth_cache,
    ensure_databricks_auth,
)


@pytest.fixture(autouse=True)
def reset_auth(monkeypatch):
    _reset_auth_cache()
    yield
    _reset_auth_cache()


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
        databricks_client_id=None,
        databricks_client_secret=None,
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
        databricks_client_id=None,
        databricks_client_secret=None,
    )
    with patch("agent_memory.config._workspace_auth_ok", return_value=False), patch("databricks.sdk.WorkspaceClient") as mock_client:
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
        databricks_client_id=None,
        databricks_client_secret=None,
    )
    with patch("agent_memory.config._workspace_auth_ok", return_value=True):
        assert ensure_databricks_auth(settings) is True
    assert (
        __import__("os").environ["DATABRICKS_HOST"]
        == "https://e2-demo-field-eng.cloud.databricks.com"
    )
    assert __import__("os").environ["DATABRICKS_TOKEN"] == "good-token"


# ---------------------------------------------------------------------------
# 6 new Settings fields (dossier model — interfaces.md §Config)
# ---------------------------------------------------------------------------

def _base_settings(**overrides) -> Settings:
    defaults = dict(
        databricks_host="https://host.databricks.com",
        databricks_token="tok",
        databricks_profile=None,
        fm_api_endpoint="x",
        fm_api_embedding_endpoint="y",
        mlflow_experiment_name="/test",
        uc_catalog="c",
        uc_schema="s",
        lakebase_database=None,
        lakebase_conninfo=None,
        databricks_client_id=None,
        databricks_client_secret=None,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_settings_has_volume_name_field():
    s = _base_settings()
    assert hasattr(s, "volume_name")
    assert isinstance(s.volume_name, str)


def test_settings_has_max_upload_bytes_field():
    s = _base_settings()
    assert hasattr(s, "max_upload_bytes")
    assert isinstance(s.max_upload_bytes, int)


def test_settings_has_chunk_tokens_field():
    s = _base_settings()
    assert hasattr(s, "chunk_tokens")
    assert isinstance(s.chunk_tokens, int)


def test_settings_has_chunk_overlap_tokens_field():
    s = _base_settings()
    assert hasattr(s, "chunk_overlap_tokens")
    assert isinstance(s.chunk_overlap_tokens, int)


def test_settings_from_env_defaults(monkeypatch):
    """from_env() must provide correct defaults per interfaces.md §Config."""
    monkeypatch.setenv("DATABRICKS_HOST", "https://host.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "tok")
    # Clear any overrides that might interfere
    for key in ["VOLUME_NAME", "MAX_UPLOAD_BYTES", "CHUNK_TOKENS", "CHUNK_OVERLAP_TOKENS"]:
        monkeypatch.delenv(key, raising=False)

    s = Settings.from_env()

    assert s.volume_name == "dossier_raw"
    assert s.max_upload_bytes == 25 * 1024 * 1024
    assert s.chunk_tokens == 512
    assert s.chunk_overlap_tokens == 50


def test_settings_from_env_respects_overrides(monkeypatch):
    """from_env() must honour env var overrides for new fields."""
    monkeypatch.setenv("DATABRICKS_HOST", "https://host.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "tok")
    monkeypatch.setenv("VOLUME_NAME", "my_volume")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))
    monkeypatch.setenv("CHUNK_TOKENS", "256")
    monkeypatch.setenv("CHUNK_OVERLAP_TOKENS", "25")

    s = Settings.from_env()

    assert s.volume_name == "my_volume"
    assert s.max_upload_bytes == 10 * 1024 * 1024
    assert s.chunk_tokens == 256
    assert s.chunk_overlap_tokens == 25


def test_settings_max_upload_bytes_default_is_25mb():
    s = _base_settings()
    assert s.max_upload_bytes == 25 * 1024 * 1024


def test_settings_chunk_tokens_default():
    s = _base_settings()
    assert s.chunk_tokens == 512


def test_settings_chunk_overlap_tokens_default():
    s = _base_settings()
    assert s.chunk_overlap_tokens == 50


def test_settings_volume_name_default():
    s = _base_settings()
    assert s.volume_name == "dossier_raw"
