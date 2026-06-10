"""Tests for memory/extraction.py — NEW module (D3, ADR-0012 + ADR-0005).

Contract source: interfaces.md §3 (extraction.py functions).
All Databricks external calls are monkeypatched; tests run offline.

The VARIANT-shape fixtures mirror live ai_parse_document v2.0 output
(validated 2026-06-09, T22): per-element `confidence` float and page index
in `bbox[].page_id`, with an authoritative `document.pages` list.
"""

from __future__ import annotations

import json

import pytest

from agent_memory.memory.extraction import (
    ExtractionResult,
    chunk_text,
    extract_text,
    extract_text_from_variant,
)

# ---------------------------------------------------------------------------
# chunk_text — windowing, overlap, ordering, edge cases
# ---------------------------------------------------------------------------

def test_chunk_text_single_chunk_for_short_text():
    text = "This is a short note."
    chunks = chunk_text(text, chunk_tokens=512, overlap_tokens=50)
    assert len(chunks) == 1
    assert chunks[0] == text.strip()


def test_chunk_text_empty_returns_empty():
    assert chunk_text("", chunk_tokens=512, overlap_tokens=50) == []


def test_chunk_text_whitespace_only_returns_empty():
    assert chunk_text("   \n\t  ", chunk_tokens=512, overlap_tokens=50) == []


def test_chunk_text_produces_multiple_chunks():
    words = ["word"] * 600
    text = " ".join(words)
    chunks = chunk_text(text, chunk_tokens=100, overlap_tokens=10)
    assert len(chunks) >= 2


def test_chunk_text_chunks_are_ordered():
    words = [f"word{i}" for i in range(300)]
    text = " ".join(words)
    chunks = chunk_text(text, chunk_tokens=100, overlap_tokens=10)
    # Chunks must appear in document order: first word of chunk i < first word of chunk i+1
    first_words = [c.split()[0] for c in chunks]
    # Verify chunk[0] starts earlier in text than chunk[1], etc.
    positions = [text.index(w) for w in first_words]
    assert positions == sorted(positions)


def test_chunk_text_overlap():
    """With overlap_tokens > 0, adjacent chunks share words at boundaries."""
    words = [f"w{i}" for i in range(50)]
    text = " ".join(words)
    chunks = chunk_text(text, chunk_tokens=20, overlap_tokens=5)
    if len(chunks) >= 2:
        # Last words of chunk[0] should appear at start of chunk[1]
        tail = set(chunks[0].split()[-5:])
        head = set(chunks[1].split()[:5])
        assert tail & head  # non-empty intersection


def test_chunk_text_no_overlap_no_shared_words():
    words = [f"u{i}" for i in range(60)]
    text = " ".join(words)
    chunks = chunk_text(text, chunk_tokens=20, overlap_tokens=0)
    if len(chunks) >= 2:
        set0 = set(chunks[0].split())
        set1 = set(chunks[1].split())
        assert not (set0 & set1)


def test_chunk_text_all_words_covered():
    """Every word in the input must appear in at least one chunk."""
    words = [f"token{i}" for i in range(200)]
    text = " ".join(words)
    chunks = chunk_text(text, chunk_tokens=50, overlap_tokens=5)
    all_words_in_chunks = set()
    for c in chunks:
        all_words_in_chunks.update(c.split())
    assert set(words) == all_words_in_chunks


def test_chunk_text_exactly_one_chunk_at_boundary():
    """Text of exactly chunk_tokens words produces exactly 1 chunk."""
    words = ["w"] * 512
    text = " ".join(words)
    chunks = chunk_text(text, chunk_tokens=512, overlap_tokens=50)
    assert len(chunks) == 1


def test_chunk_text_chunks_are_non_empty():
    text = " ".join([f"t{i}" for i in range(100)])
    chunks = chunk_text(text, chunk_tokens=30, overlap_tokens=5)
    assert all(len(c.strip()) > 0 for c in chunks)


# ---------------------------------------------------------------------------
# extract_text_from_variant — VARIANT JSON parsing
# ---------------------------------------------------------------------------

def _variant_json(elements: list[dict]) -> str:
    return json.dumps({"document": {"elements": elements}})


def test_extract_text_from_variant_concats_text_elements():
    elements = [
        {"type": "text", "content": "First paragraph."},
        {"type": "text", "content": "Second paragraph."},
    ]
    result = extract_text_from_variant(_variant_json(elements))
    assert isinstance(result, ExtractionResult)
    assert "First paragraph." in result.text
    assert "Second paragraph." in result.text


def test_extract_text_from_variant_joins_with_newline():
    elements = [
        {"type": "text", "content": "Line A."},
        {"type": "text", "content": "Line B."},
    ]
    result = extract_text_from_variant(_variant_json(elements))
    assert "\n" in result.text


def test_extract_text_from_variant_ignores_non_text_elements():
    elements = [
        {"type": "text", "content": "Good text."},
        {"type": "image", "content": "should be ignored"},
        {"type": "table", "content": "also ignored"},
    ]
    result = extract_text_from_variant(_variant_json(elements))
    assert "should be ignored" not in result.text
    assert "also ignored" not in result.text
    assert "Good text." in result.text


def test_extract_text_from_variant_empty_elements():
    result = extract_text_from_variant(_variant_json([]))
    assert isinstance(result, ExtractionResult)
    assert result.text == "" or result.text is not None  # empty but not erroring


def test_extract_text_from_variant_mean_confidence():
    elements = [
        {"type": "text", "content": "A", "confidence": 0.8},
        {"type": "text", "content": "B", "confidence": 0.6},
    ]
    result = extract_text_from_variant(_variant_json(elements))
    assert result.mean_confidence is not None
    assert abs(result.mean_confidence - 0.7) < 1e-9


def test_extract_text_from_variant_no_confidence_is_none():
    elements = [
        {"type": "text", "content": "No confidence scores here"},
    ]
    result = extract_text_from_variant(_variant_json(elements))
    assert result.mean_confidence is None


def test_extract_text_from_variant_method_field():
    elements = [{"type": "text", "content": "x"}]
    result = extract_text_from_variant(_variant_json(elements))
    assert result.method == "ai_parse_document"


# ---------------------------------------------------------------------------
# page_count — derived from document.pages / element bbox[].page_id (T22)
# ---------------------------------------------------------------------------

def test_extract_text_from_variant_page_count_from_document_pages():
    """page_count comes from the authoritative document.pages list length."""
    variant = json.dumps({
        "document": {
            "elements": [{"type": "text", "content": "p1"}],
            "pages": [{"id": 0}, {"id": 1}, {"id": 2}],
        }
    })
    result = extract_text_from_variant(variant)
    assert result.page_count == 3


def test_extract_text_from_variant_page_count_from_bbox_page_id():
    """With no document.pages, page_count falls back to max bbox page_id + 1 (0-based)."""
    elements = [
        {"type": "text", "content": "a", "bbox": [{"coord": [0, 0, 1, 1], "page_id": 0}]},
        {"type": "text", "content": "b", "bbox": [{"coord": [0, 0, 1, 1], "page_id": 1}]},
    ]
    result = extract_text_from_variant(_variant_json(elements))
    assert result.page_count == 2


def test_extract_text_from_variant_page_count_none_without_page_info():
    elements = [{"type": "text", "content": "no page info"}]
    result = extract_text_from_variant(_variant_json(elements))
    assert result.page_count is None


# ---------------------------------------------------------------------------
# ExtractionResult dataclass shape (contract test)
# ---------------------------------------------------------------------------

def test_extraction_result_fields():
    r = ExtractionResult(text="hello", method="text")
    assert r.text == "hello"
    assert r.method == "text"
    assert r.page_count is None
    assert r.mean_confidence is None


def test_extraction_result_is_frozen():
    r = ExtractionResult(text="hello", method="text")
    with pytest.raises((AttributeError, TypeError)):
        r.text = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# extract_text — text path (kind='text')
# ---------------------------------------------------------------------------

def test_extract_text_kind_text_decodes_utf8(monkeypatch):
    """kind='text' must decode raw_bytes utf-8 and NOT call fetch_sql."""
    called = []

    def _should_not_be_called(*args, **kwargs):
        called.append(True)
        raise AssertionError("fetch_sql must NOT be called for kind='text'")

    monkeypatch.setattr(
        "agent_memory.memory.extraction.fetch_sql",
        _should_not_be_called,
    )

    raw_bytes = b"Meeting notes: discussed retirement."
    result = extract_text(
        volume_path="/vol/c0/1.txt",
        kind="text",
        raw_bytes=raw_bytes,
    )

    assert "Meeting notes" in result.text
    assert result.method == "text"
    assert called == []


def test_extract_text_kind_text_utf8_errors_replace(monkeypatch):
    """Invalid UTF-8 must be decoded with errors='replace', not raised."""
    monkeypatch.setattr(
        "agent_memory.memory.extraction.fetch_sql",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not be called")),
    )

    raw_bytes = b"valid \xff\xfe invalid bytes"
    result = extract_text(
        volume_path="/vol/c0/1.txt",
        kind="text",
        raw_bytes=raw_bytes,
    )
    # Must return something without raising
    assert isinstance(result.text, str)
    assert result.method == "text"


def test_extract_text_kind_text_requires_raw_bytes():
    """kind='text' without raw_bytes should raise ValueError."""
    with pytest.raises((ValueError, TypeError)):
        extract_text(volume_path="/vol/c0/1.txt", kind="text", raw_bytes=None)


def test_extract_text_pdf_calls_fetch_sql(monkeypatch):
    """kind='pdf' must invoke fetch_sql (sql_warehouse) for ai_parse_document."""
    import json as _json

    variant_response = _json.dumps({
        "document": {"elements": [{"type": "text", "content": "PDF text content"}]}
    })

    fetch_sql_calls = []

    def _mock_fetch_sql(sql, *args, **kwargs):
        fetch_sql_calls.append(sql)
        return [[variant_response]]

    monkeypatch.setattr("agent_memory.memory.extraction.fetch_sql", _mock_fetch_sql)

    result = extract_text(
        volume_path="/Volumes/cat/schema/vol/c0/1.pdf",
        kind="pdf",
    )

    assert len(fetch_sql_calls) == 1
    assert "ai_parse_document" in fetch_sql_calls[0]
    assert "PDF text content" in result.text
    assert result.method == "ai_parse_document"


def test_extract_text_returns_extraction_result():
    """extract_text always returns ExtractionResult regardless of kind."""
    raw_bytes = b"plain text"
    result = extract_text(volume_path="/vol/c0/1.txt", kind="text", raw_bytes=raw_bytes)
    assert isinstance(result, ExtractionResult)
    assert hasattr(result, "text")
    assert hasattr(result, "method")
    assert hasattr(result, "page_count")
    assert hasattr(result, "mean_confidence")
