"""Tests for synthetic/render.py — Pillow fixture rendering (ADR-0015).

Asserts each renderer emits the right binary format (magic bytes). Requires Pillow
(the `dev`/`synthetic` extra).
"""

from __future__ import annotations

from agent_memory.synthetic.render import render_handwritten, render_pdf, render_scan

SAMPLE = "Meeting note - Test Client\nRisk tolerance moderate.\nMove 150k from equities to bonds."


def test_render_handwritten_is_png():
    data = render_handwritten(SAMPLE)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 1000


def test_render_pdf_is_pdf():
    data = render_pdf(SAMPLE)
    assert data[:5] == b"%PDF-"
    assert len(data) > 1000


def test_render_scan_is_jpeg():
    data = render_scan(SAMPLE)
    assert data[:3] == b"\xff\xd8\xff"
    assert len(data) > 1000


def test_render_handwritten_deterministic():
    # No randomness in the handwriting/print path → byte-identical re-renders.
    assert render_handwritten(SAMPLE) == render_handwritten(SAMPLE)


def test_render_empty_text_does_not_raise():
    assert render_pdf("")[:5] == b"%PDF-"
    assert render_handwritten("")[:8] == b"\x89PNG\r\n\x1a\n"
