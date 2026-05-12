"""Smoke tests — replace once real modules land."""

import agent_memory


def test_package_imports():
    assert agent_memory.__version__ == "0.1.0"
