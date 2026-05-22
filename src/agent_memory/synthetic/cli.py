"""CLI to write synthetic JSON fixtures under `data/synthetic/output/`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_memory.synthetic.generator import generate_dataset

_DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "output"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic wealth-advisor demo data.")
    parser.add_argument("--clients", type=int, default=5, help="Number of synthetic clients")
    parser.add_argument(
        "--sessions-per-client",
        type=int,
        default=2,
        help="Conversation seeds per client",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="Directory for JSON output (gitignored)",
    )
    args = parser.parse_args()

    dataset = generate_dataset(
        client_count=args.clients,
        sessions_per_client=args.sessions_per_client,
        seed=args.seed,
    )
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    (out / "clients.json").write_text(
        json.dumps([c.model_dump(mode="json") for c in dataset.clients], indent=2),
        encoding="utf-8",
    )
    (out / "portfolios.json").write_text(
        json.dumps([p.model_dump(mode="json") for p in dataset.portfolios], indent=2),
        encoding="utf-8",
    )
    (out / "conversations.json").write_text(
        json.dumps([c.model_dump(mode="json") for c in dataset.conversations], indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(dataset.clients)} clients, {len(dataset.portfolios)} portfolios, "
          f"{len(dataset.conversations)} conversations to {out}")


if __name__ == "__main__":
    main()
