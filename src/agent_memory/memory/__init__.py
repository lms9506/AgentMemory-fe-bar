"""Memory subsystem.

- `lakebase.py` — connection + low-level read/write (live memory)
- `retrievers.py` — top-k semantic retrieval over pgvector
- `distillation.py` — episodic → long-term profile job logic
- `audit.py` — audit-log helpers (every long-term write goes through here)
"""
