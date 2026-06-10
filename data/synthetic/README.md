# Synthetic data

No real client data ever enters this directory.

There are two synthetic data paths — the **demo personas** (what the seed notebook
ingests) and the **procedural generator** (parameterized data for tests/eval).

## Demo personas (the seed source)

`src/agent_memory/synthetic/personas.py` hand-authors **3 refined clients**, each with
a continuous storyline across 6 mixed-format artifacts — handwritten notes (PNG),
printed statements (PDF), scanned forms (JPG), and typed text — backdated over ~8
months. `notebooks/01_seed.py` ingests these and backdates each artifact (ADR-0015).

Binary artifacts are committed as **fixtures** under `data/synthetic/fixtures/<client_id>/`.
Regenerate them after editing persona content:

```bash
uv sync --extra synthetic
uv run python scripts/render_fixtures.py
```

Rendering lives in `src/agent_memory/synthetic/render.py` (Pillow; dev/`synthetic`
extra only — never imported by the app or the ingest runtime).

## Procedural generator (tests / eval)

`src/agent_memory/synthetic/generator.py` produces parameterized random clients +
plain-text artifacts. **Generator code is checked in; JSON output is gitignored.**

```bash
uv sync
uv run agent-memory-synthetic            # writes JSON under data/synthetic/output/
```
