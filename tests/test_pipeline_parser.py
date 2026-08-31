"""Parity guard: the Lakeflow pipeline's inlined variant parser must match the
canonical `extract_text_from_variant` (ADR-0019). The pipeline inlines a copy so
it deploys without the wheel; this test ensures the copy never diverges.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from agent_memory.memory.extraction import extract_text_from_variant

# Load databricks/pipelines/dossier_ingest.py by path (it's not under src/).
# `import dlt` is guarded in the module, so the import succeeds offline and the
# pure `variant_to_text` helper is available.
_PIPELINE_PATH = (
    Path(__file__).resolve().parents[1] / "databricks" / "pipelines" / "dossier_ingest.py"
)
_spec = importlib.util.spec_from_file_location("dossier_ingest", _PIPELINE_PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
variant_to_text = _mod.variant_to_text


def _variant(elements: list[dict], **doc_extra) -> str:
    return json.dumps({"document": {"elements": elements, **doc_extra}})


_CASES = [
    _variant([{"type": "text", "content": "Hello"}, {"type": "text", "content": "World"}]),
    _variant([{"type": "text", "content": "A", "confidence": 0.8}, {"type": "text", "content": "B", "confidence": 0.6}]),
    _variant([{"type": "table", "content": "ignored"}, {"type": "text", "content": "kept"}]),
    _variant([{"type": "text", "content": "P", "bbox": [{"page_id": 0}]}, {"type": "text", "content": "Q", "bbox": [{"page_id": 2}]}]),
    _variant([], pages=[{}, {}, {}]),
    _variant([]),
    "",
    None,
    "not valid json{{{",
    json.dumps([{"type": "text", "content": "top-level-list"}]),  # document is a list
]


@pytest.mark.parametrize("variant_json", _CASES)
def test_parity_with_canonical_parser(variant_json):
    canonical = extract_text_from_variant(variant_json or "")
    text, pages, conf = variant_to_text(variant_json)
    assert text == canonical.text
    assert pages == canonical.page_count
    assert conf == canonical.mean_confidence


def test_none_and_empty_return_empty():
    assert variant_to_text(None) == ("", None, None)
    assert variant_to_text("") == ("", None, None)
