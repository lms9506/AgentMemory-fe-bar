"""Environment-backed settings for local runs and Databricks deployment."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Load-bearing config from environment (see `.env.example`)."""

    databricks_host: str | None
    databricks_token: str | None
    fm_api_endpoint: str
    fm_api_embedding_endpoint: str
    mlflow_experiment_name: str
    uc_catalog: str
    uc_schema: str
    lakebase_database: str | None

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            databricks_host=os.getenv("DATABRICKS_HOST"),
            databricks_token=os.getenv("DATABRICKS_TOKEN"),
            fm_api_endpoint=os.getenv(
                "FM_API_ENDPOINT",
                "databricks-meta-llama-3-3-70b-instruct",
            ),
            fm_api_embedding_endpoint=os.getenv(
                "FM_API_EMBEDDING_ENDPOINT",
                "databricks-bge-large-en",
            ),
            mlflow_experiment_name=os.getenv(
                "MLFLOW_EXPERIMENT_NAME",
                "/Shared/agent-memory/dev",
            ),
            uc_catalog=os.getenv("UC_CATALOG", "agent_memory_dev"),
            uc_schema=os.getenv("UC_SCHEMA", "wealth_advisor"),
            lakebase_database=os.getenv("LAKEBASE_DATABASE"),
        )

    @property
    def databricks_configured(self) -> bool:
        return bool(self.databricks_host and self.databricks_token)
