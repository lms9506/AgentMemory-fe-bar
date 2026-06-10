# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Seed: ingest the hand-authored demo dossiers
# MAGIC
# MAGIC Run order: 00_setup → **01_seed** → 02_demo. Prereq: `00_setup` completed
# MAGIC (Lakebase + Volume + Delta schema applied). Attach Serverless and **Run all**.
# MAGIC
# MAGIC Seeds three refined client personas (`agent_memory.synthetic.personas`), each
# MAGIC with a continuous storyline across mixed-format artifacts — handwritten notes
# MAGIC (PNG), printed statements (PDF), scanned forms (JPG), and typed text — spread
# MAGIC over ~8 months. Binary artifacts are read from the committed fixtures in
# MAGIC `data/synthetic/fixtures/`; text artifacts are ingested inline. Each artifact is
# MAGIC pushed through the real ingest pipeline
# MAGIC (`raw_save → extract → chunk_embed → summarize → maybe_propose`) and then
# MAGIC **backdated** to its persona date so the dossier timeline reads as real history.

# COMMAND ----------

# MAGIC %pip install ..

# COMMAND ----------

# Databricks Serverless %pip auto-restarts Python; guard the explicit restart so a
# second (redundant) restart can't error the cell.
try:
    dbutils.library.restartPython()
except Exception:
    pass  # already restarted by %pip install

# COMMAND ----------

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Repo root derived from this notebook's own workspace path (no hardcoded user/target);
# the notebook lives at <REPO_ROOT>/notebooks/<name>, so REPO_ROOT is two levels up.
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
REPO_ROOT = "/Workspace" + os.path.dirname(os.path.dirname(_nb_path))
FIXTURES = Path(REPO_ROOT) / "data" / "synthetic" / "fixtures"

from dotenv import load_dotenv

load_dotenv(f"{REPO_ROOT}/.env.shared", override=False)

from agent_memory.config import Settings, ensure_databricks_auth

settings = Settings.from_env()
assert ensure_databricks_auth(settings), "Databricks auth failed."
print(f"catalog={settings.uc_catalog}  schema={settings.uc_schema}  volume={settings.volume_name}")

# COMMAND ----------

# The personas define everything: client identity + an ordered list of mixed-format,
# dated artifacts. Binary artifacts (handwritten/pdf/scan) read their bytes from the
# committed fixtures; text artifacts encode their content inline.
from agent_memory.synthetic.personas import PERSONAS

total_artifacts = sum(len(p.artifacts) for p in PERSONAS)
print(f"{len(PERSONAS)} personas, {total_artifacts} artifacts.")

# COMMAND ----------

# Register each client so list_clients() returns display names in the UI.
from agent_memory.memory.store import LakebaseArtifactStore

store = LakebaseArtifactStore()
for persona in PERSONAS:
    store.upsert_client(persona.client_id, persona.display_name)
    print(f"Registered: {persona.client_id} ({persona.display_name})")

# COMMAND ----------

# Ingest every artifact through the full pipeline, then backdate it to its persona
# date. run_ingest_graph yields SSE event dicts; we read the terminal event per
# artifact to recover the artifact_id, then call store.backdate_artifact.
from agent_memory.agents.ingest_graph import run_ingest_graph

now = datetime.now(tz=timezone.utc)

for persona in PERSONAS:
    print(f"\n{persona.display_name} ({persona.client_id}):")
    for art in persona.artifacts:
        filename = art.filename(persona.client_id)
        if art.fmt == "text":
            raw_bytes = art.content.encode("utf-8")
        else:
            raw_bytes = (FIXTURES / persona.client_id / filename).read_bytes()

        events = list(
            run_ingest_graph(
                client_id=persona.client_id,
                advisor_id="advisor_demo_01",
                original_filename=filename,
                kind=art.kind,
                raw_bytes=raw_bytes,
                settings=settings,
            )
        )
        final = events[-1] if events else {}
        if final.get("type") != "done":
            print(f"  {filename}: ERROR — {final.get('message', final)}")
            continue

        artifact_id = final["artifact_id"]
        ingested_at = now - timedelta(days=art.days_ago)
        store.backdate_artifact(artifact_id=artifact_id, ingested_at=ingested_at)
        print(
            f"  {filename:48s} kind={art.kind:5s} id={artifact_id} "
            f"dated -{art.days_ago}d deduped={final.get('deduped', False)}"
        )

print("\nSeed complete. Run 02_demo.py to walk the UI panels.")

# COMMAND ----------

# Verify: artifact counts per client.
for persona in PERSONAS:
    records = store.list_artifacts(client_id=persona.client_id)
    print(f"  {persona.client_id} ({persona.display_name}): {len(records)} artifacts")
