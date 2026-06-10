"""CLI to write synthetic JSON fixtures under `data/synthetic/output/`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_memory.synthetic.generator import generate_dataset

_DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "output"


def main(argv: list[str] | None = None) -> None:
    """Generate synthetic wealth-advisor demo data.

    Args:
        argv: Argument list to parse.  Defaults to ``sys.argv[1:]`` when ``None``.
    """
    parser = argparse.ArgumentParser(description="Generate synthetic wealth-advisor demo data.")
    parser.add_argument("--client-count", "--clients", dest="client_count", type=int, default=5, help="Number of synthetic clients")
    parser.add_argument(
        "--artifacts-per-client",
        type=int,
        default=3,
        help="Dossier artifacts per client",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility")
    parser.add_argument(
        "--output",
        "--output-dir",
        dest="output_dir",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="Directory for JSON output (gitignored)",
    )
    args = parser.parse_args(argv)

    dataset = generate_dataset(
        client_count=args.client_count,
        artifacts_per_client=args.artifacts_per_client,
        seed=args.seed,
    )
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    # Write the full dataset bundle as a single artifacts.json (dossier model — D7).
    bundle = dataset.model_dump(mode="json")
    (out / "artifacts.json").write_text(
        json.dumps(bundle, indent=2),
        encoding="utf-8",
    )
    # Also write per-entity files for convenience.
    (out / "clients.json").write_text(
        json.dumps([c.model_dump(mode="json") for c in dataset.clients], indent=2),
        encoding="utf-8",
    )
    (out / "portfolios.json").write_text(
        json.dumps([p.model_dump(mode="json") for p in dataset.portfolios], indent=2),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(dataset.clients)} clients, {len(dataset.portfolios)} portfolios, "
        f"{len(dataset.artifacts)} artifacts to {out}"
    )


if __name__ == "__main__":
    main()
