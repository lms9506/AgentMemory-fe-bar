"""Seed the Lakeflow landing zone with synthetic raw dossier files (ADR-0019).

Writes the raw bytes the batch bulk-onboarding pipeline ingests into
`/Volumes/{catalog}/{schema}/{volume}/_landing/{client_id}/<file>`. Two sources,
both synthetic (CLAUDE.md rule 6 — no real client data, ever):

  1. The 3 hand-authored personas (ADR-0015): mixed-format fixtures (PDF/PNG/JPG)
     + inline text notes. These exercise `ai_parse_document` OCR through the
     pipeline (handwriting, scans, printed statements).
  2. Procedurally generated text clients (`synthetic.generator`): plain-text
     artifacts that give the batch job realistic volume/variety.

This script only touches the UC Volume (the raw tier). It does NOT write Lakebase
or Delta — the pipeline produces the Delta tables and the `hydrate` job loads
Lakebase. Idempotent: existing files are skipped so Auto Loader stays stable.

Usage:
    uv run python scripts/seed_landing.py --extra-clients 10 --seed 7
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from agent_memory.config import Settings, ensure_databricks_auth, get_workspace_client
from agent_memory.memory.landing import landing_root
from agent_memory.synthetic.generator import generate_dataset
from agent_memory.synthetic.personas import PERSONAS

# Repo-relative fixtures dir (this file lives in scripts/).
_FIXTURES = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "fixtures"


def _exists(wc, path: str) -> bool:
    try:
        wc.files.get_metadata(path)
        return True
    except Exception:
        return False


def _upload(wc, path: str, data: bytes, *, force: bool) -> bool:
    """Upload bytes to a Volume path. Returns True if written, False if skipped."""
    if not force and _exists(wc, path):
        return False
    wc.files.upload(path, io.BytesIO(data), overwrite=True)
    return True


def seed(*, extra_clients: int, artifacts_per_client: int, seed: int, force: bool) -> dict[str, int]:
    cfg = Settings.from_env()
    if not ensure_databricks_auth(cfg):
        raise SystemExit(f"Databricks auth failed. {cfg.auth_diagnostics()}")
    wc = get_workspace_client(cfg)
    root = landing_root(catalog=cfg.uc_catalog, schema=cfg.uc_schema, volume_name=cfg.volume_name)
    print(f"Landing zone: {root}")

    written = skipped = 0

    # 1) Personas — mixed-format fixtures + inline text.
    for persona in PERSONAS:
        for art in persona.artifacts:
            filename = art.filename(persona.client_id)
            if art.fmt == "text":
                data = art.content.encode("utf-8")
            else:
                data = (_FIXTURES / persona.client_id / filename).read_bytes()
            dest = f"{root}/{persona.client_id}/{filename}"
            if _upload(wc, dest, data, force=force):
                written += 1
            else:
                skipped += 1
        print(f"  persona {persona.client_id} ({persona.display_name}): {len(persona.artifacts)} artifacts")

    # 2) Procedurally generated text clients (offset ids so they never collide
    #    with the personas' client_000x).
    if extra_clients > 0:
        # start_index=1000 keeps generated ids (client_1000+) clear of the
        # personas' client_0000-0002.
        dataset = generate_dataset(
            client_count=extra_clients,
            artifacts_per_client=artifacts_per_client,
            seed=seed,
            start_index=1000,
        )
        for art in dataset.artifacts:
            dest = f"{root}/{art.client_id}/{art.original_filename}"
            if _upload(wc, dest, art.content.encode("utf-8"), force=force):
                written += 1
            else:
                skipped += 1
        print(f"  generated: {len(dataset.clients)} clients, {len(dataset.artifacts)} text artifacts")

    counts = {"written": written, "skipped": skipped}
    print(f"Seed landing complete: {counts}")
    return counts


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Seed the Lakeflow landing zone with synthetic raw files.")
    parser.add_argument("--extra-clients", type=int, default=10, help="Procedurally generated text clients")
    parser.add_argument("--artifacts-per-client", type=int, default=4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--force", action="store_true", help="Overwrite existing landing files")
    args = parser.parse_args(argv)
    seed(
        extra_clients=args.extra_clients,
        artifacts_per_client=args.artifacts_per_client,
        seed=args.seed,
        force=args.force,
    )


if __name__ == "__main__":
    sys.exit(main())
