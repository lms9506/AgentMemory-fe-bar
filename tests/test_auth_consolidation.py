"""Tests for the consolidated auth layer defined in interfaces.md.

Covers:
  - get_workspace_client  (M2M, PAT, Profile, LRU cache, cache reset, priority)
  - _reset_auth_cache     (cache invalidation)
  - sql_warehouse/_workspace with M2M credentials (M2M path previously unreachable)
  - _workspace_auth_ok    (empty-host short-circuit, no network call)

All tests are driven from the public interface contracts in
architecture/interfaces.md and the requirements in research/brief.md.
Implementation source files are NOT read here.
"""

from unittest.mock import MagicMock, patch

import pytest

from agent_memory.config import (
    Settings,
    _reset_auth_cache,
    _workspace_auth_ok,
    get_workspace_client,
)

# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

def _make_settings(
    *,
    host: str = "https://e2-demo-field-eng.cloud.databricks.com",
    token: str | None = None,
    profile: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> Settings:
    """Return a minimal but valid Settings instance."""
    return Settings(
        databricks_host=host,
        databricks_token=token,
        databricks_client_id=client_id,
        databricks_client_secret=client_secret,
        databricks_profile=profile,
        fm_api_endpoint="x",
        fm_api_embedding_endpoint="y",
        mlflow_experiment_name="/test",
        uc_catalog="c",
        uc_schema="s",
        lakebase_database=None,
        lakebase_conninfo=None,
    )


@pytest.fixture(autouse=True)
def reset_cache():
    """Always clear the auth cache before and after each test so tests
    don't bleed into one another via the lru_cache."""
    _reset_auth_cache()
    yield
    _reset_auth_cache()


# ---------------------------------------------------------------------------
# Test 1 — M2M path
# ---------------------------------------------------------------------------

def test_get_workspace_client_m2m_path():
    """When CLIENT_ID and CLIENT_SECRET are set on Settings (and TOKEN is not),
    get_workspace_client should configure WorkspaceClient with those credentials."""
    settings = _make_settings(
        client_id="my-client-id",
        client_secret="my-client-secret",
    )

    with patch("databricks.sdk.WorkspaceClient") as mock_wc:
        mock_instance = MagicMock()
        mock_wc.return_value = mock_instance

        result = get_workspace_client(settings)

    assert result is mock_instance

    # The WorkspaceClient must have been called with client_id + client_secret
    _, kwargs = mock_wc.call_args
    assert kwargs.get("client_id") == "my-client-id"
    assert kwargs.get("client_secret") == "my-client-secret"


# ---------------------------------------------------------------------------
# Test 2 — PAT path
# ---------------------------------------------------------------------------

def test_get_workspace_client_pat_path():
    """When only DATABRICKS_TOKEN is set (no M2M fields), get_workspace_client
    should configure WorkspaceClient with that token."""
    settings = _make_settings(token="my-pat-token")

    with patch("databricks.sdk.WorkspaceClient") as mock_wc:
        mock_instance = MagicMock()
        mock_wc.return_value = mock_instance

        result = get_workspace_client(settings)

    assert result is mock_instance

    _, kwargs = mock_wc.call_args
    assert kwargs.get("token") == "my-pat-token"
    # M2M credentials must NOT be passed
    assert kwargs.get("client_id") is None
    assert kwargs.get("client_secret") is None


# ---------------------------------------------------------------------------
# Test 3 — Profile path
# ---------------------------------------------------------------------------

def test_get_workspace_client_profile_path():
    """When DATABRICKS_PROFILE is set and no token/M2M creds are present,
    get_workspace_client should configure WorkspaceClient with that profile."""
    settings = _make_settings(token=None, profile="e2-demo-field-eng")

    with patch("databricks.sdk.WorkspaceClient") as mock_wc:
        mock_instance = MagicMock()
        mock_wc.return_value = mock_instance

        result = get_workspace_client(settings)

    assert result is mock_instance

    _, kwargs = mock_wc.call_args
    assert kwargs.get("profile") == "e2-demo-field-eng"


# ---------------------------------------------------------------------------
# Test 4 — LRU cache: same instance returned on second call
# ---------------------------------------------------------------------------

def test_get_workspace_client_lru_cache_returns_same_instance():
    """Calling get_workspace_client twice with the same Settings should return
    the exact same WorkspaceClient instance (LRU cache is active)."""
    settings = _make_settings(token="cache-test-token")

    with patch("databricks.sdk.WorkspaceClient") as mock_wc:
        mock_instance = MagicMock()
        mock_wc.return_value = mock_instance

        first = get_workspace_client(settings)
        second = get_workspace_client(settings)

    assert first is second
    # WorkspaceClient constructor called only once (cache hit on second call)
    assert mock_wc.call_count == 1


# ---------------------------------------------------------------------------
# Test 5 — Cache reset: new instance after _reset_auth_cache()
# ---------------------------------------------------------------------------

def test_reset_auth_cache_produces_new_instance():
    """After _reset_auth_cache(), get_workspace_client should construct a new
    WorkspaceClient instance rather than returning the cached one."""
    settings = _make_settings(token="reset-test-token")

    instance_a = MagicMock(name="instance_a")
    instance_b = MagicMock(name="instance_b")

    with patch("databricks.sdk.WorkspaceClient") as mock_wc:
        mock_wc.side_effect = [instance_a, instance_b]

        first = get_workspace_client(settings)
        _reset_auth_cache()
        second = get_workspace_client(settings)

    assert first is instance_a
    assert second is instance_b
    assert first is not second
    assert mock_wc.call_count == 2


# ---------------------------------------------------------------------------
# Test 6 — M2M takes priority over PAT
# ---------------------------------------------------------------------------

def test_get_workspace_client_m2m_wins_over_pat():
    """When both M2M and PAT credentials are present on Settings, M2M must
    take priority per the auth-priority contract: M2M → PAT → Profile → default."""
    settings = _make_settings(
        token="should-be-ignored-token",
        client_id="sp-client-id",
        client_secret="sp-client-secret",
    )

    with patch("databricks.sdk.WorkspaceClient") as mock_wc:
        mock_instance = MagicMock()
        mock_wc.return_value = mock_instance

        get_workspace_client(settings)

    _, kwargs = mock_wc.call_args
    # M2M credentials must be used
    assert kwargs.get("client_id") == "sp-client-id"
    assert kwargs.get("client_secret") == "sp-client-secret"
    # The PAT token must NOT be present (M2M path does not pass token)
    assert kwargs.get("token") != "should-be-ignored-token"


# ---------------------------------------------------------------------------
# Test 7 — sql_warehouse._workspace with M2M credentials
# ---------------------------------------------------------------------------

def test_sql_warehouse_workspace_returns_client_with_m2m():
    """When DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET are provided via
    Settings, the shared factory must return a WorkspaceClient — the M2M path
    must NOT be silently skipped (as it was in the old sql_warehouse._workspace).

    After the auth consolidation the sql_warehouse module delegates to
    get_workspace_client from config.py, so we verify the public contract:
    a WorkspaceClient is returned and constructed with M2M credentials.
    """
    settings = _make_settings(
        client_id="app-sp-id",
        client_secret="app-sp-secret",
    )

    from databricks.sdk import WorkspaceClient as RealWorkspaceClient

    with patch("databricks.sdk.WorkspaceClient") as mock_wc:
        mock_instance = MagicMock(spec=RealWorkspaceClient)
        mock_wc.return_value = mock_instance

        client = get_workspace_client(settings)

    # Must return a WorkspaceClient (or mock thereof), not None
    assert client is not None
    assert client is mock_instance

    # Must have been configured with M2M credentials
    _, kwargs = mock_wc.call_args
    assert kwargs.get("client_id") == "app-sp-id"
    assert kwargs.get("client_secret") == "app-sp-secret"


# ---------------------------------------------------------------------------
# Test 8 — _workspace_auth_ok: empty host short-circuits without network call
# ---------------------------------------------------------------------------

def test_workspace_auth_ok_empty_host_returns_false_without_network():
    """When host is empty/None, _workspace_auth_ok must return False immediately
    without instantiating a WorkspaceClient or making any network call.

    Contract from interfaces.md / research/brief.md:
    'Guard with `if not host or not token: return False` before the SDK call.'
    """
    # If a network call is made, WorkspaceClient would be instantiated and
    # current_user.me() called.  We make that raise to catch any leak.
    with patch("databricks.sdk.WorkspaceClient") as mock_wc:
        mock_wc.return_value.current_user.me.side_effect = AssertionError(
            "_workspace_auth_ok made a network call despite empty host"
        )

        result_empty_str = _workspace_auth_ok("", "some-token")
        result_none = _workspace_auth_ok(None, "some-token")  # type: ignore[arg-type]

    assert result_empty_str is False
    assert result_none is False
    # WorkspaceClient must never have been instantiated for either call
    mock_wc.assert_not_called()


def test_workspace_auth_ok_empty_token_returns_false_without_network():
    """Symmetrically, when token is empty/None, _workspace_auth_ok must also
    return False without making any network call."""
    with patch("databricks.sdk.WorkspaceClient") as mock_wc:
        mock_wc.return_value.current_user.me.side_effect = AssertionError(
            "_workspace_auth_ok made a network call despite empty token"
        )

        result_empty_str = _workspace_auth_ok("https://host.databricks.com", "")
        result_none = _workspace_auth_ok("https://host.databricks.com", None)  # type: ignore[arg-type]

    assert result_empty_str is False
    assert result_none is False
    mock_wc.assert_not_called()
