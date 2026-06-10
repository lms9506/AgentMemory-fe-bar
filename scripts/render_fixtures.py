"""Render persona binary artifacts to committed demo fixtures (ADR-0015).

Run locally (needs the rendering deps: ``uv sync --extra synthetic``):

    uv run python scripts/render_fixtures.py

Writes ``data/synthetic/fixtures/<client_id>/<filename>`` for every non-text artifact
in ``agent_memory.synthetic.personas.PERSONAS``. Text artifacts carry no fixture — the
seed notebook ingests their content inline. Deterministic; safe to re-run and commit.
"""

from __future__ import annotations

from pathlib import Path

from agent_memory.synthetic.personas import PERSONAS
from agent_memory.synthetic.render import render_handwritten, render_pdf, render_scan

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = _REPO_ROOT / "data" / "synthetic" / "fixtures"
_RENDERERS = {
    "handwritten": render_handwritten,
    "pdf": render_pdf,
    "scan": render_scan,
}


def main() -> None:
    written = 0
    for persona in PERSONAS:
        out_dir = _FIXTURES / persona.client_id
        out_dir.mkdir(parents=True, exist_ok=True)
        for art in persona.artifacts:
            if art.fmt == "text":
                continue
            data = _RENDERERS[art.fmt](art.content)
            path = out_dir / art.filename(persona.client_id)
            path.write_bytes(data)
            print(f"  wrote {path.relative_to(_REPO_ROOT)} ({len(data):,} bytes)")
            written += 1
    print(f"Done. {written} fixtures under {_FIXTURES.relative_to(_REPO_ROOT)}")


if __name__ == "__main__":
    main()
