-- Unity Catalog Delta: distilled long-term client profiles (FR-3).
-- Apply via `uv run python scripts/apply_delta_schema.py` or SQL warehouse.
-- Replace ${catalog} and ${schema} before running in a notebook.

CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.client_profile (
    client_id           STRING    NOT NULL COMMENT 'Primary key — one row per client',
    risk_tolerance      STRING    COMMENT 'conservative | moderate | aggressive',
    investment_goals    ARRAY<STRING>,
    family_context      STRING,
    stated_preferences  STRING,
    summary             STRING    COMMENT 'Advisor-facing narrative summary',
    source_artifact_ids ARRAY<BIGINT> COMMENT 'Artifact ids used in this distillation',
    distilled_at        TIMESTAMP NOT NULL,
    updated_at          TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Distilled long-term memory; prior versions via Delta time travel (ADR-0008)';
