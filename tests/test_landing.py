"""Tests for the shared batch bulk-onboarding landing-path helper (ADR-0019)."""

from __future__ import annotations

from agent_memory.memory.landing import LANDING_SUBDIR, landing_root


def test_landing_root():
    root = landing_root(catalog="cat", schema="sch", volume_name="dossier_raw")
    assert root == f"/Volumes/cat/sch/dossier_raw/{LANDING_SUBDIR}"


def test_landing_root_uses_configured_volume():
    root = landing_root(catalog="c", schema="s", volume_name="myvol")
    assert root.endswith(f"/myvol/{LANDING_SUBDIR}")
    assert root.startswith("/Volumes/c/s/")
