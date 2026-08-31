"""Landing-zone path convention for the batch bulk-onboarding path (ADR-0019).

The batch ingest lands raw files under a `_landing/` subfolder of the same UC
Volume that holds the immutable raw bytes:

    /Volumes/{catalog}/{schema}/{volume}/_landing/{client_id}/<filename>

`client_id` is the immediate parent folder; kind is derived from the extension.
`scripts/seed_landing.py` writes files here via `landing_root`; the Lakeflow
pipeline (`databricks/pipelines/dossier_ingest.py`) reads them and derives
client_id/kind in Spark. The pipeline re-implements that derivation inline
(rather than importing this module) because pipeline compute has no `agent_memory`
wheel installed — see the same rationale for the inlined `variant_to_text` there.
"""

from __future__ import annotations

# Subfolder within the dossier_raw Volume where raw batch files land before the
# pipeline picks them up. Kept distinct from the interactive path's
# `{client_id}/{artifact_id}.{ext}` layout so the two never collide.
LANDING_SUBDIR = "_landing"


def landing_root(*, catalog: str, schema: str, volume_name: str) -> str:
    """Absolute Volume path of the batch landing zone."""
    return f"/Volumes/{catalog}/{schema}/{volume_name}/{LANDING_SUBDIR}"
