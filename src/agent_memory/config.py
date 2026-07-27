"""Environment-backed settings for local runs and Databricks deployment."""

from __future__ import annotations

import contextlib
import functools
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from databricks.sdk import WorkspaceClient

from dotenv import load_dotenv

_ENV_LOADED = False
_AUTH_RESOLVED = False


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
    if not host or not token:
        return False
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
    """Set `DATABRICKS_HOST` / `DATABRICKS_TOKEN` for LangChain from `.env` or CLI profile.

    Auth priority: M2M (CLIENT_ID+SECRET) → PAT (TOKEN) → Profile → SDK default.
    M2M tokens are managed internally by the SDK; no token is written to env.
    """
    global _AUTH_RESOLVED
    if _AUTH_RESOLVED:
        return True
    host = _normalize_host(settings.databricks_host)
    if not host:
        # No explicit host/token/profile configured (e.g. inside a Databricks notebook
        # or serverless job, where .env isn't present but the runtime provides ambient
        # credentials). Fall back to the SDK default auth chain and adopt its host/token
        # so downstream LangChain/embeddings clients get DATABRICKS_HOST/TOKEN set.
        try:
            from databricks.sdk import WorkspaceClient

            client = WorkspaceClient()
            client.current_user.me()
            resolved_host = _normalize_host(client.config.host)
            resolved_token = _token_from_workspace_client(client)
            if resolved_host and resolved_token:
                _set_workspace_env(resolved_host, resolved_token)
                _AUTH_RESOLVED = True
                return True
        except Exception:
            return False
        return False

    # M2M path: CLIENT_ID + CLIENT_SECRET (Databricks Apps standard injection).
    # The SDK manages token refresh internally — we only need to set DATABRICKS_HOST.
    if settings.databricks_client_id and settings.databricks_client_secret:
        os.environ["DATABRICKS_HOST"] = host
        _AUTH_RESOLVED = True
        return True

    token = settings.databricks_token
    if token:
        if _workspace_auth_ok(host, token):
            _set_workspace_env(host, token)
            _AUTH_RESOLVED = True
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
        _AUTH_RESOLVED = True
        return True
    except Exception:
        return False


def set_mlflow_experiment(settings: Settings) -> None:
    """Set the MLflow experiment, creating its parent workspace directory first.

    `mlflow.set_experiment("/Shared/agent-memory/dev")` fails with NOT_FOUND if the
    parent `/Shared/agent-memory` directory doesn't exist yet (MLflow won't create
    nested parents). On a fresh workspace it never does, so we mkdir the parent (the
    SDK's `mkdirs` is recursive + idempotent) before setting the experiment.
    """
    import mlflow

    name = settings.mlflow_experiment_name
    if not name:
        return
    if name.startswith("/"):
        parent = name.rsplit("/", 1)[0]
        if parent:
            # best-effort; set_experiment will surface a real failure
            with contextlib.suppress(Exception):
                get_workspace_client(settings).workspace.mkdirs(parent)
    mlflow.set_experiment(name)


@functools.lru_cache(maxsize=1)
def get_workspace_client(settings: Settings) -> WorkspaceClient:
    """Single auth-resolution factory for the whole app.
    Auth priority: M2M (CLIENT_ID+SECRET) → PAT (TOKEN) → Profile → SDK default.
    Cached per process; SDK refreshes M2M tokens internally.
    """
    from databricks.sdk import WorkspaceClient

    cfg = settings
    if cfg.databricks_client_id and cfg.databricks_client_secret:
        return WorkspaceClient(
            host=cfg.databricks_host,
            client_id=cfg.databricks_client_id,
            client_secret=cfg.databricks_client_secret,
        )
    if cfg.databricks_token:
        return WorkspaceClient(host=cfg.databricks_host, token=cfg.databricks_token)
    if cfg.databricks_profile:
        return WorkspaceClient(profile=cfg.databricks_profile)
    return WorkspaceClient()


def _reset_auth_cache() -> None:
    """Reset process-level auth state. Call in test teardown only."""
    global _AUTH_RESOLVED
    _AUTH_RESOLVED = False
    get_workspace_client.cache_clear()
    # Also clear the connection-layer cache to keep caches in sync.
    try:
        from agent_memory.memory.connection import clear_connection_caches
        clear_connection_caches()
    except ImportError:
        pass


@dataclass(frozen=True)
class Settings:
    """Load-bearing config from environment (see `.env.example`)."""

    databricks_host: str | None
    databricks_token: str | None
    databricks_client_id: str | None
    databricks_client_secret: str | None
    databricks_profile: str | None
    fm_api_endpoint: str
    fm_api_embedding_endpoint: str
    mlflow_experiment_name: str
    uc_catalog: str
    uc_schema: str
    lakebase_database: str | None
    lakebase_conninfo: str | None
    volume_name: str = "dossier_raw"
    max_upload_bytes: int = 25 * 1024 * 1024
    chunk_tokens: int = 512
    chunk_overlap_tokens: int = 50

    @classmethod
    def from_env(cls) -> Settings:
        load_local_env()
        return cls(
            databricks_host=_normalize_host(os.getenv("DATABRICKS_HOST")),
            databricks_token=_normalize_token(os.getenv("DATABRICKS_TOKEN")),
            databricks_client_id=os.getenv("DATABRICKS_CLIENT_ID") or None,
            databricks_client_secret=os.getenv("DATABRICKS_CLIENT_SECRET") or None,
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
            volume_name=os.getenv("VOLUME_NAME", "dossier_raw"),
            max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))),
            chunk_tokens=int(os.getenv("CHUNK_TOKENS", "512")),
            chunk_overlap_tokens=int(os.getenv("CHUNK_OVERLAP_TOKENS", "50")),
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
        # Prefer the frozen settings, but fall back to the live env: inside a notebook/
        # job, ensure_databricks_auth() resolves ambient credentials and sets
        # DATABRICKS_HOST/TOKEN *after* this Settings was frozen (with host=None), so the
        # instance fields lag reality. Re-reading the env keeps this gate truthful.
        host = self.databricks_host or _normalize_host(os.getenv("DATABRICKS_HOST"))
        if not host:
            return False
        if self.databricks_client_id and self.databricks_client_secret:
            return True
        if self.databricks_token or os.getenv("DATABRICKS_TOKEN"):
            return True
        return bool(self.databricks_profile or _infer_profile_from_host(host))

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

