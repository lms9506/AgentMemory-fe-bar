"""Environment-backed settings for local runs and Databricks deployment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ENV_LOADED = False


def load_local_env() -> None:
    """Load `.env` from the repo root once per process (no-op in Databricks Apps/jobs)."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env", override=False)
    _ENV_LOADED = True


def _normalize_host(value: str | None) -> str | None:
    if not value:
        return None
    host = value.strip()
    if "?" in host:
        host = host.split("?", 1)[0]
    return host.rstrip("/") or None


def _normalize_token(value: str | None) -> str | None:
    if not value:
        return None
    token = value.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        token = token[1:-1].strip()
    if token.startswith("<") and token.endswith(">"):
        token = token[1:-1].strip()
    return token or None


def _infer_profile_from_host(host: str | None) -> str | None:
    """Map `https://e2-demo-field-eng.cloud.databricks.com` → profile `e2-demo-field-eng`."""
    if not host:
        return None
    clean = host.replace("https://", "").replace("http://", "").split("/")[0]
    suffix = ".cloud.databricks.com"
    if clean.endswith(suffix):
        return clean[: -len(suffix)]
    return None


def _workspace_auth_ok(host: str, token: str) -> bool:
    """Return True when credentials can call the workspace API."""
    try:
        from databricks.sdk import WorkspaceClient

        WorkspaceClient(host=host, token=token).current_user.me()
        return True
    except Exception:
        return False


def _set_workspace_env(host: str, token: str) -> None:
    os.environ["DATABRICKS_HOST"] = host
    os.environ["DATABRICKS_TOKEN"] = token


def _token_from_workspace_client(client: object) -> str | None:
    """OAuth CLI profiles often leave `config.token` empty; read the bearer header."""
    config = client.config  # type: ignore[attr-defined]
    if config.token:
        return config.token
    headers = dict(config.authenticate())
    auth = headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def ensure_databricks_auth(settings: Settings) -> bool:
    """Set `DATABRICKS_HOST` / `DATABRICKS_TOKEN` for LangChain from `.env` or CLI profile."""
    host = _normalize_host(settings.databricks_host)
    if not host:
        return False

    token = settings.databricks_token
    if token:
        if _workspace_auth_ok(host, token):
            _set_workspace_env(host, token)
            return True
        # Stale PAT exported in the shell can block CLI OAuth fallback.
        os.environ.pop("DATABRICKS_TOKEN", None)

    profile = settings.databricks_profile or _infer_profile_from_host(host)
    if not profile:
        return False

    try:
        from databricks.sdk import WorkspaceClient

        client = WorkspaceClient(profile=profile)
        client.current_user.me()
        resolved_host = _normalize_host(client.config.host) or host
        resolved_token = _token_from_workspace_client(client)
        if not resolved_token:
            return False
        _set_workspace_env(resolved_host, resolved_token)
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class Settings:
    """Load-bearing config from environment (see `.env.example`)."""

    databricks_host: str | None
    databricks_token: str | None
    databricks_profile: str | None
    fm_api_endpoint: str
    fm_api_embedding_endpoint: str
    mlflow_experiment_name: str
    uc_catalog: str
    uc_schema: str
    lakebase_database: str | None
    lakebase_conninfo: str | None

    @classmethod
    def from_env(cls) -> Settings:
        load_local_env()
        return cls(
            databricks_host=_normalize_host(os.getenv("DATABRICKS_HOST")),
            databricks_token=_normalize_token(os.getenv("DATABRICKS_TOKEN")),
            databricks_profile=os.getenv("DATABRICKS_PROFILE"),
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
            lakebase_conninfo=os.getenv("LAKEBASE_CONNINFO") or os.getenv("LAKEBASE_URL"),
        )

    @property
    def lakebase_configured(self) -> bool:
        load_local_env()
        if self.lakebase_conninfo and (
            os.getenv("LAKEBASE_CREDENTIAL_ENDPOINT")
            or os.getenv("LAKEBASE_PROJECT")
            or os.getenv("LAKEBASE_INSTANCE_NAME")
        ):
            return self.databricks_configured
        if self.lakebase_conninfo:
            return True
        return bool(
            os.getenv("LAKEBASE_HOST")
            and os.getenv("LAKEBASE_USER")
            and os.getenv("LAKEBASE_PASSWORD")
        )

    @property
    def databricks_configured(self) -> bool:
        if not self.databricks_host:
            return False
        if self.databricks_token:
            return True
        return bool(self.databricks_profile or _infer_profile_from_host(self.databricks_host))

    def auth_diagnostics(self) -> str:
        """Human-readable hint when auth fails (never includes secrets)."""
        raw = os.getenv("DATABRICKS_TOKEN")
        token_chars = len(_normalize_token(raw) or "")
        if token_chars == 0 and raw is not None and raw.strip() in ('""', "''"):
            token_note = "`.env` has DATABRICKS_TOKEN but the value is empty quotes — paste the token and save the file"
        elif token_chars == 0:
            token_note = "no DATABRICKS_TOKEN in `.env`"
        else:
            token_note = (
                f"DATABRICKS_TOKEN length {token_chars} in environment "
                "(remove stale `export DATABRICKS_TOKEN=...` or renew via "
                "`databricks auth login --profile <profile>`)"
            )
        profile = self.databricks_profile or _infer_profile_from_host(self.databricks_host)
        profile_note = f"CLI profile `{profile}`" if profile else "no CLI profile inferred from host"
        return f"{token_note}; fallback: {profile_note}"

