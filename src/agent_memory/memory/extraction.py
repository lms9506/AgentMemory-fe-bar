"""Document extraction and chunking — ai_parse_document VARIANT post-processing (D3).

ADR-0012: whitespace-approximation chunker (512 words / 50-word overlap, no new dep).
ADR-0005: ai_parse_document (invoked via sql_warehouse.fetch_sql) is the sole extractor
          for every non-text kind. Live validation (2026-06-09, T22) confirmed it handles
          printed text and handwriting — including connected cursive — well enough on its
          own (mean element confidence ≥0.92, ≥94% word recall), so there is no
          multimodal fallback path.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass

from agent_memory.config import Settings
from agent_memory.memory.models import ArtifactKind
from agent_memory.memory.sql_warehouse import _sql_string, fetch_sql


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    method: str            # 'text' | 'ai_parse_document'
    page_count: int | None = None
    mean_confidence: float | None = None


def extract_text(
    *,
    volume_path: str,
    kind: ArtifactKind,
    raw_bytes: bytes | None = None,   # required for kind='text'
    settings: Settings | None = None,
) -> ExtractionResult:
    """Extract text from a dossier artifact.

    kind='text' decodes raw_bytes utf-8 (errors='replace'); skips ai_parse_document.
    All other kinds (incl. images / scans of handwriting) run ai_parse_document via
    sql_warehouse.fetch_sql, then extract_text_from_variant().
    """
    cfg = settings or Settings.from_env()

    if kind == "text":
        if raw_bytes is None:
            raise ValueError("raw_bytes required when kind='text'")
        text = raw_bytes.decode("utf-8", errors="replace")
        return ExtractionResult(text=text, method="text")

    # All other kinds: invoke ai_parse_document via Statement Execution API.
    # volume_path is escaped via _sql_string (single-quote doubling) to prevent
    # SQL injection — client_id and upload filename derive from user input.
    # READ_FILES(..., 'binaryFile') exposes the binary column as `content`
    # (alongside path/length/modificationTime) — pass it straight to ai_parse_document.
    sql = (
        "SELECT to_json(ai_parse_document(content)) "
        f"FROM READ_FILES({_sql_string(volume_path)}, format => 'binaryFile')"
    )
    rows = fetch_sql(sql, settings=cfg)
    variant_json: str | None = None
    if rows and rows[0] and rows[0][0] is not None:
        variant_json = str(rows[0][0])

    if not variant_json:
        # Empty result — degrade gracefully.
        return ExtractionResult(text="", method="ai_parse_document")

    return extract_text_from_variant(variant_json)


def extract_text_from_variant(variant_json: str) -> ExtractionResult:
    """Parse to_json(ai_parse_document(...)) output.

    Concatenates document.elements[].content where element.type == 'text',
    joined by '\\n'. Computes mean_confidence if confidence values are present.
    Returns an ExtractionResult with method='ai_parse_document'.
    """
    try:
        data = json.loads(variant_json)
    except json.JSONDecodeError:
        return ExtractionResult(text="", method="ai_parse_document")

    # ai_parse_document returns {"document": {"elements": [...]}} or similar.
    # Navigate to the elements list.
    document = data.get("document") if isinstance(data, dict) else data
    if isinstance(document, dict):
        elements = document.get("elements", [])
    elif isinstance(document, list):
        elements = document
    else:
        elements = []

    text_parts: list[str] = []
    confidence_values: list[float] = []
    page_set: set[int] = set()

    for element in elements:
        if not isinstance(element, dict):
            continue
        elem_type = element.get("type", "")
        if elem_type == "text":
            content = element.get("content", "")
            if content:
                text_parts.append(str(content))
        # `confidence` is a per-element float in ai_parse_document v2.0 output
        # (validated live 2026-06-09, T22).
        confidence = element.get("confidence")
        if confidence is not None:
            with contextlib.suppress(TypeError, ValueError):
                confidence_values.append(float(confidence))
        # The page index lives in element.bbox[].page_id (0-based) — there is no
        # top-level `page` field on an element (validated live 2026-06-09, T22).
        for box in element.get("bbox") or []:
            if isinstance(box, dict) and box.get("page_id") is not None:
                with contextlib.suppress(TypeError, ValueError):
                    page_set.add(int(box["page_id"]))

    extracted = "\n".join(text_parts)
    mean_conf = (sum(confidence_values) / len(confidence_values)) if confidence_values else None

    # Prefer the authoritative document.pages count; fall back to the max bbox
    # page_id (0-based, so +1) when pages is absent.
    pages = document.get("pages") if isinstance(document, dict) else None
    if isinstance(pages, list) and pages:
        page_count = len(pages)
    elif page_set:
        page_count = max(page_set) + 1
    else:
        page_count = None

    return ExtractionResult(
        text=extracted,
        method="ai_parse_document",
        page_count=page_count,
        mean_confidence=mean_conf,
    )


def chunk_text(
    text: str,
    *,
    chunk_tokens: int = 512,
    overlap_tokens: int = 50,
) -> list[str]:
    """Whitespace-approximation chunker (ADR-0012).

    Splits text on whitespace (words ~ tokens). Windows chunk_tokens words with
    overlap_tokens stride overlap. Returns ordered, dense chunks (chunk_index 0..n-1).
    No tokenizer dependency — word count is a safe approximation for bge-large-en.
    """
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = max(1, chunk_tokens - overlap_tokens)
    start = 0
    while start < len(words):
        end = min(start + chunk_tokens, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += step

    return chunks
