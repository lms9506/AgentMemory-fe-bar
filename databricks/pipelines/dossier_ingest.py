"""Lakeflow Declarative Pipeline — batch bulk-onboarding of dossier artifacts (ADR-0019).

This is the BATCH ingest surface, complementary to the interactive one-file
drag-drop path (`agents/ingest_graph.py`). When an advisor inherits a book of
clients or migrates off a legacy system, they have a pile of historical
documents to load at once — that is a data-engineering job, and Lakeflow is the
right tool for it.

Data journey (each layer is a UC-governed table under ${catalog}.${schema}):

    UC Volume  _landing/{client_id}/*   (raw bytes — the books-and-records copy)
        │  Auto Loader (cloudFiles, binaryFile)
        ▼
    bronze_raw_artifacts   one row per raw file: bytes, hash, kind, client_id
        │  ai_parse_document(content)  +  ai_query(<llm>, summary)
        ▼
    silver_parsed_artifacts   extracted text, per-artifact summary, OCR confidence

Downstream, the `hydrate` job task (a python wheel task, see databricks.yml)
reads silver, chunks + embeds the text, and loads Lakebase pgvector for
operational recall — keeping the three tiers distinct (UC Volume = raw bytes,
Delta = governed batch tables, Lakebase = live serving).

Reuse note: text extraction from the ai_parse_document VARIANT delegates to the
SAME parser the interactive path uses (`memory.extraction.extract_text_from_variant`),
so batch- and interactive-ingested artifacts get byte-identical text. The
`agent_memory` wheel is installed on the pipeline (see the pipeline's
`environment` in databricks.yml).

Configuration (set via the DAB pipeline `configuration` block):
    dossier.landing_path   absolute Volume path of the _landing zone
    dossier.fm_endpoint    Foundation Model chat endpoint for the summary
"""

from __future__ import annotations

# Spark / DLT are only present on pipeline compute. Guard the imports so this
# module stays importable in the offline test suite (which exercises the pure
# helpers below). The @dlt tables are only defined when running on a pipeline.
try:
    import dlt  # type: ignore
    from pyspark.sql import DataFrame  # type: ignore
    from pyspark.sql import functions as F  # type: ignore
    from pyspark.sql import types as T  # type: ignore

    _PIPELINE_RUNTIME = True
except ImportError:  # pragma: no cover - offline import path
    _PIPELINE_RUNTIME = False


def variant_to_text(variant_json: str | None) -> tuple[str, int | None, float | None]:
    """Extract (text, page_count, mean_confidence) from to_json(ai_parse_document(...)).

    A faithful, dependency-free copy of `memory.extraction.extract_text_from_variant`
    so the pipeline deploys as a single .py file (no wheel install on pipeline
    compute). `tests/test_pipeline_parser.py` asserts byte-for-byte parity with the
    canonical parser, so the two can never silently diverge (ADR-0019).
    """
    import contextlib
    import json

    if not variant_json:
        return ("", None, None)
    try:
        data = json.loads(variant_json)
    except json.JSONDecodeError:
        return ("", None, None)

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
        if element.get("type", "") == "text":
            content = element.get("content", "")
            if content:
                text_parts.append(str(content))
        confidence = element.get("confidence")
        if confidence is not None:
            with contextlib.suppress(TypeError, ValueError):
                confidence_values.append(float(confidence))
        for box in element.get("bbox") or []:
            if isinstance(box, dict) and box.get("page_id") is not None:
                with contextlib.suppress(TypeError, ValueError):
                    page_set.add(int(box["page_id"]))

    text = "\n".join(text_parts)
    mean_conf = (sum(confidence_values) / len(confidence_values)) if confidence_values else None
    pages = document.get("pages") if isinstance(document, dict) else None
    if isinstance(pages, list) and pages:
        page_count: int | None = len(pages)
    elif page_set:
        page_count = max(page_set) + 1
    else:
        page_count = None
    return (text, page_count, mean_conf)


# The per-artifact summary prompt mirrors the interactive summarize node
# (agents/ingest_graph._make_summarize_node) so both paths produce the same
# kind of dossier-timeline entry. No financial advice; plain text only.
_SUMMARY_PROMPT = (
    "You are an assistant that writes concise dossier summaries for a wealth "
    "advisor. Summarize the key facts from the document in 2-4 sentences. Do not "
    "recommend any financial action. Output plain text only.\n\nDocument:\n"
)

# ai_parse_document only runs on non-text kinds; plain text is decoded directly
# (matches memory.extraction.extract_text — text skips the parser).
_TEXT_EXTS = ("txt", "md", "text")


if _PIPELINE_RUNTIME:

    def _conf(key: str, default: str = "") -> str:
        return spark.conf.get(key, default)  # type: ignore[name-defined]  # noqa: F821

    _LANDING_PATH = _conf("dossier.landing_path")
    _FM_ENDPOINT = _conf("dossier.fm_endpoint", "databricks-meta-llama-3-3-70b-instruct")

    # ---- Pandas UDF: VARIANT JSON -> plain text --------------------------------
    # Delegates to the canonical parser so batch text == interactive text.
    _parsed_schema = T.StructType(
        [
            T.StructField("text", T.StringType()),
            T.StructField("page_count", T.IntegerType()),
            T.StructField("mean_confidence", T.DoubleType()),
        ]
    )

    @F.pandas_udf(_parsed_schema)  # type: ignore[misc]
    def _parse_variant(json_col):
        import pandas as pd

        rows = [variant_to_text(None if raw is None else str(raw)) for raw in json_col]
        return pd.DataFrame(rows, columns=["text", "page_count", "mean_confidence"])

    @dlt.table(
        name="bronze_raw_artifacts",
        comment="Raw dossier files landed in the UC Volume, one row per file "
        "(binary bytes + SHA-256 hash + derived client_id/kind). Ingest boundary.",
        table_properties={"quality": "bronze"},
    )
    def bronze_raw_artifacts() -> DataFrame:
        raw = (
            spark.readStream.format("cloudFiles")  # type: ignore[name-defined]  # noqa: F821
            .option("cloudFiles.format", "binaryFile")
            .option("pathGlobFilter", "*.*")
            .option("recursiveFileLookup", "true")
            .load(_LANDING_PATH)
        )
        # path is .../_landing/<client_id>/<filename>
        client_id = F.regexp_extract(F.col("path"), r"/_landing/([^/]+)/", 1)
        filename = F.element_at(F.split(F.col("path"), "/"), -1)
        ext = F.lower(F.regexp_extract(filename, r"\.([^.]+)$", 1))
        kind = (
            F.when(ext == F.lit("pdf"), "pdf")
            .when(ext.isin("png", "jpg", "jpeg", "gif", "webp", "tif", "tiff", "bmp"), "image")
            .when(ext == F.lit("docx"), "docx")
            .when(ext.isin("txt", "md", "text"), "text")
            .otherwise("other")
        )
        return (
            raw.withColumn("client_id", client_id)
            .withColumn("original_filename", filename)
            .withColumn("kind", kind)
            .withColumn("content_hash", F.sha2(F.col("content"), 256))
            .withColumnRenamed("length", "size_bytes")
            .select(
                "client_id",
                "original_filename",
                "kind",
                "content_hash",
                "size_bytes",
                "modificationTime",
                "path",
                "content",
            )
        )

    @dlt.table(
        name="silver_parsed_artifacts",
        comment="Bronze artifacts with text extracted via ai_parse_document and a "
        "per-artifact summary via ai_query. GenAI enrichment layer; feeds Genie + "
        "the Lakebase hydration job.",
        table_properties={"quality": "silver"},
    )
    @dlt.expect_or_drop("has_client_id", "client_id IS NOT NULL AND client_id != ''")
    def silver_parsed_artifacts() -> DataFrame:
        bronze = dlt.read_stream("bronze_raw_artifacts")

        is_text = F.col("kind") == F.lit("text")
        # Non-text kinds: to_json(ai_parse_document(content)) -> canonical parser.
        # Text kinds: decode the bytes directly (parser is skipped). ai_parse_document
        # is a billed AI/OCR function, so guard it behind ~is_text: a CASE WHEN only
        # evaluates its THEN branch for matching rows, so the parser never fires on the
        # plain-text notes (and can't error on non-document bytes). text rows get NULL,
        # which _parse_variant maps to ("", None, None).
        raw_variant = F.when(~is_text, F.expr("to_json(ai_parse_document(content))"))
        parsed = _parse_variant(raw_variant)
        decoded_text = F.col("content").cast("string")

        enriched = bronze.withColumn(
            "extracted_text",
            F.when(is_text, decoded_text).otherwise(parsed["text"]),
        ).withColumns(
            {
                "page_count": F.when(is_text, F.lit(None)).otherwise(parsed["page_count"]),
                "mean_confidence": F.when(is_text, F.lit(None)).otherwise(parsed["mean_confidence"]),
                "extract_method": F.when(is_text, F.lit("text")).otherwise(F.lit("ai_parse_document")),
            }
        )

        # Per-artifact summary via the Foundation Model API (native SQL, no Python).
        # Cap the input so a huge statement can't blow the context window.
        _prompt_sql = _SUMMARY_PROMPT.replace("'", "''")
        summary = F.expr(
            f"ai_query('{_FM_ENDPOINT}', concat('{_prompt_sql}', substring(extracted_text, 1, 8000)))"
        )
        return (
            enriched.withColumn(
                "summary",
                F.when(F.length(F.coalesce(F.col("extracted_text"), F.lit(""))) > 0, summary),
            )
            .withColumn("parsed_at", F.current_timestamp())
            .drop("content")  # bytes stay in the Volume + bronze; silver is text-only
        )
