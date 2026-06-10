"""Tests for Lakebase connection string handling."""

from unittest.mock import patch

from agent_memory.config import Settings
from agent_memory.memory.connection import _parse_postgres_uri, lakebase_conninfo


def test_parse_postgres_uri_without_password():
    uri = (
        "postgresql://linus.meister%40databricks.com@"
        "ep-odd-term.database.eu-central-1.cloud.databricks.com/"
        "databricks_postgres?sslmode=require"
    )
    parsed = _parse_postgres_uri(uri)
    assert parsed["host"] == "ep-odd-term.database.eu-central-1.cloud.databricks.com"
    assert parsed["user"] == "linus.meister@databricks.com"
    assert parsed["database"] == "databricks_postgres"
    assert parsed["password"] == ""


def test_lakebase_credential_endpoint_from_connect_fields(monkeypatch):
    monkeypatch.setenv("LAKEBASE_PROJECT", "agent-memory")
    monkeypatch.setenv("LAKEBASE_BRANCH", "production")
    monkeypatch.setenv("LAKEBASE_COMPUTE", "primary")
    monkeypatch.delenv("LAKEBASE_CREDENTIAL_ENDPOINT", raising=False)
    from agent_memory.memory.connection import _lakebase_credential_endpoint

    assert (
        _lakebase_credential_endpoint()
        == "projects/agent-memory/branches/production/endpoints/primary"
    )


def test_lakebase_conninfo_autoscale_refresh(monkeypatch):
    monkeypatch.setenv(
        "LAKEBASE_CREDENTIAL_ENDPOINT",
        "projects/demo/branches/production/endpoints/primary",
    )
    monkeypatch.delenv("LAKEBASE_INSTANCE_NAME", raising=False)
    monkeypatch.delenv("LAKEBASE_DATABASE", raising=False)

    settings = Settings(
        databricks_host="https://e2-demo-field-eng.cloud.databricks.com",
        databricks_token=None,
        databricks_profile="e2-demo-field-eng",
        fm_api_endpoint="x",
        fm_api_embedding_endpoint="y",
        mlflow_experiment_name="/test",
        uc_catalog="c",
        uc_schema="s",
        lakebase_database=None,
        lakebase_conninfo="postgresql://user@host.example.com/mydb?sslmode=require",
        databricks_client_id=None,
        databricks_client_secret=None,
    )

    with patch("agent_memory.memory.connection.load_local_env"), patch(
        "agent_memory.memory.connection._lakebase_oauth_token_autoscale",
        return_value="fresh-token",
    ):
        info = lakebase_conninfo(settings)

    assert "host=host.example.com" in info
    assert "user=user" in info
    assert "dbname=mydb" in info
    assert "password=fresh-token" in info


def test_lakebase_conninfo_provisioned_refresh(monkeypatch):
    monkeypatch.setenv("LAKEBASE_INSTANCE_NAME", "my-instance")
    monkeypatch.delenv("LAKEBASE_CREDENTIAL_ENDPOINT", raising=False)

    settings = Settings(
        databricks_host="https://e2-demo-field-eng.cloud.databricks.com",
        databricks_token=None,
        databricks_profile="e2-demo-field-eng",
        fm_api_endpoint="x",
        fm_api_embedding_endpoint="y",
        mlflow_experiment_name="/test",
        uc_catalog="c",
        uc_schema="s",
        lakebase_database="agent_memory",
        lakebase_conninfo="postgresql://u@h.example.com/databricks_postgres",
        databricks_client_id=None,
        databricks_client_secret=None,
    )

    with patch("agent_memory.memory.connection.load_local_env"), patch(
        "agent_memory.memory.connection._lakebase_oauth_token_provisioned",
        return_value="tok",
    ):
        info = lakebase_conninfo(settings)

    assert "dbname=agent_memory" in info
    assert "password=tok" in info
