# Notebooks

For humans, not imports. Use these to demo, explore, and walk a customer through the accelerator.

Anything that becomes reusable code graduates to `src/agent_memory/`. Don't `import` from a notebook.

## Planned notebooks

- `00_setup_lakebase.ipynb` — provision Lakebase, run `databricks/lakebase_schema.sql`
- `01_generate_synthetic_data.ipynb` — populate Lakebase + Delta with synthetic clients
- `10_agent_no_memory.ipynb` — minimal LangGraph agent, proves stack wiring (M4)
- `20_agent_with_memory.ipynb` — same agent + episodic + pgvector retrieval (M5)
- `30_distillation.ipynb` — long-term profile job walkthrough (M6)
- `40_eval.ipynb` — MLflow eval over synthetic scenarios (M8)
- `99_demo_end_to_end.ipynb` — the customer-facing demo
