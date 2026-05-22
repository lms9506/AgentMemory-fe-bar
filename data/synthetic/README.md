# Synthetic data

Generators for dummy clients, portfolios, and conversation seeds. **Generator code is checked in; output is gitignored.**

No real client data ever enters this directory.

## Generate fixtures

```bash
uv sync
uv run agent-memory-synthetic
# or: uv run python data/synthetic/generate.pygi
```

Writes JSON under `data/synthetic/output/` (`clients.json`, `portfolios.json`, `conversations.json`).

Implementation lives in `src/agent_memory/synthetic/` (importable from tests and notebooks).
