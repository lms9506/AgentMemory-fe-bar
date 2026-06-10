"""Shared pytest fixtures applied to all test files."""

from __future__ import annotations

import os

import pytest

from agent_memory.config import _reset_auth_cache

# Env vars that steer which branch lakebase_conninfo() takes. A test that calls
# load_local_env()/Settings.from_env() reads .env into the process env; without
# isolation those leak and push a *later* connection test down an unpatched
# branch (e.g. LAKEBASE_PROJECT making _lakebase_credential_endpoint() truthy).
# Neutralised per-test and restored after. Scoped to LAKEBASE_* only so
# MLFLOW_*/DATABRICKS_* and the shell env are left untouched.
_LAKEBASE_STEERING_ENV = (
    "LAKEBASE_CREDENTIAL_ENDPOINT",
    "LAKEBASE_INSTANCE_NAME",
    "LAKEBASE_PROJECT",
    "LAKEBASE_BRANCH",
    "LAKEBASE_COMPUTE",
    "LAKEBASE_HOST",
    "LAKEBASE_USER",
    "LAKEBASE_PASSWORD",
    "LAKEBASE_DATABASE",
    "LAKEBASE_PORT",
)


@pytest.fixture(autouse=True)
def reset_auth_cache_global():
    """Isolate process-level auth state and Lakebase env between tests.

    Clears _AUTH_RESOLVED / get_workspace_client's LRU cache, and removes the
    LAKEBASE_* steering vars so .env leakage from one test can't push a later
    connection test down a different (unpatched) branch. Restores them after.
    Runs for ALL tests (conftest-level autouse).
    """
    _reset_auth_cache()
    saved = {k: os.environ.pop(k) for k in _LAKEBASE_STEERING_ENV if k in os.environ}
    yield
    for k in _LAKEBASE_STEERING_ENV:
        os.environ.pop(k, None)
    os.environ.update(saved)
    _reset_auth_cache()
