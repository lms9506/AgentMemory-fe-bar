# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Bulk onboarding via Lakeflow (batch dossier ingest)
# MAGIC
# MAGIC Run order: 00_setup → 01_seed (interactive personas) → **03_bulk_onboard** → 02_demo.
# MAGIC
# MAGIC This is the **batch** ingest surface (ADR-0019), complementary to the interactive
# MAGIC drag-drop path. It mirrors an advisor **inheriting a book of clients**: a pile of
# MAGIC historical documents onboarded at once. The end-to-end journey, all in one run:
# MAGIC
# MAGIC | Stage | Tool | Output |
# MAGIC |---|---|---|
# MAGIC | Land raw files | UC Volume `_landing/` | synthetic PDFs/scans/notes |
# MAGIC | Ingest + govern | **Lakeflow** pipeline | `bronze_raw_artifacts`, `silver_parsed_artifacts` (Unity Catalog) |
# MAGIC | Make intelligent | `ai_parse_document` + `ai_query` | extracted text + per-artifact summary |
# MAGIC | Operational serving | **Lakebase** pgvector | `artifacts` + `artifact_chunks` (hydrate job) |
# MAGIC | Distill | Delta `client_profile` | governed long-term memory |
# MAGIC | Query in NL | **Genie** | `scripts/setup_genie.py` |
# MAGIC | Surface | **Databricks App** | the advisor UI (00_setup deploys it) |

# COMMAND ----------

# Derive the bundle files root from the CURRENT user (portable — no hardcoded home).
# %pip can't read a Python var but does expand shell env vars ($VAR), so publish it.
import os

_user = spark.sql("SELECT current_user()").first()[0]
os.environ["BUNDLE_ROOT"] = f"/Workspace/Users/{_user}/.bundle/agent-memory/dev/files"
print(os.environ["BUNDLE_ROOT"])

# COMMAND ----------

# MAGIC %pip install $BUNDLE_ROOT

# COMMAND ----------

try:
    dbutils.library.restartPython()
except Exception:
    pass

# COMMAND ----------

# restartPython clears in-process env, so re-derive REPO_ROOT from the (persistent)
# Spark session rather than hardcoding a user.
_user = spark.sql("SELECT current_user()").first()[0]
REPO_ROOT = f"/Workspace/Users/{_user}/.bundle/agent-memory/dev/files"
from dotenv import load_dotenv

load_dotenv(f"{REPO_ROOT}/.env.shared", override=False)

from agent_memory.config import Settings, ensure_databricks_auth

settings = Settings.from_env()
assert ensure_databricks_auth(settings), "Databricks auth failed."
print(f"catalog={settings.uc_catalog}  schema={settings.uc_schema}  volume={settings.volume_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Land synthetic raw files in the UC Volume
# MAGIC The 3 mixed-format personas (PDF/scan/handwriting — exercises `ai_parse_document`)
# MAGIC plus 10 procedurally generated text clients (`client_1000+`).

# COMMAND ----------

import sys

sys.path.insert(0, REPO_ROOT)  # import scripts/seed_landing
from scripts.seed_landing import seed as seed_landing

seed_landing(extra_clients=10, artifacts_per_client=4, seed=7, force=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Run the Lakeflow bulk-onboarding job
# MAGIC Triggers `agent-memory-dossier-ingest` (pipeline → hydrate → distill) and waits.
# MAGIC The job is deployed by `databricks bundle deploy`. You can also click **Run now**
# MAGIC in the Jobs UI.

# COMMAND ----------

from agent_memory.config import get_workspace_client

wc = get_workspace_client(settings)
BUNDLE_TARGET = "dev"
job_name = f"agent-memory-dossier-ingest-{BUNDLE_TARGET}"

jobs = [j for j in wc.jobs.list(name=job_name)]
assert jobs, f"Job {job_name!r} not found — run `databricks bundle deploy` first."
job_id = jobs[0].job_id
print(f"Triggering {job_name} (job_id={job_id}) ...")
run = wc.jobs.run_now(job_id=job_id).result()  # blocks until all 3 tasks finish
print(f"Run finished: {run.state.result_state}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Verify the governed Delta tables (Lakeflow output)

# COMMAND ----------

cat, sch = settings.uc_catalog, settings.uc_schema
display(spark.sql(f"""
  SELECT 'bronze' AS layer, count(*) AS rows FROM {cat}.{sch}.bronze_raw_artifacts
  UNION ALL SELECT 'silver', count(*) FROM {cat}.{sch}.silver_parsed_artifacts
  UNION ALL SELECT 'client_profile', count(*) FROM {cat}.{sch}.client_profile
"""))

# COMMAND ----------

# A parsed scan/handwriting sample — shows ai_parse_document extracted text + summary.
display(spark.sql(f"""
  SELECT client_id, original_filename, kind, extract_method,
         round(mean_confidence, 3) AS ocr_conf,
         left(extracted_text, 300) AS extracted_text_preview,
         summary
  FROM {cat}.{sch}.silver_parsed_artifacts
  WHERE extract_method = 'ai_parse_document'
  ORDER BY mean_confidence DESC
  LIMIT 5
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Verify Lakebase (operational serving) + set up Genie
# MAGIC Lakebase row counts confirm the hydrate task loaded pgvector. Then create the
# MAGIC Genie space over the governed Delta tables.

# COMMAND ----------

from agent_memory.memory.store import LakebaseArtifactStore

store = LakebaseArtifactStore()
clients = store.list_clients()
print(f"Lakebase clients: {len(clients)}")
for cid, name in clients[:15]:
    print(f"  {cid}: {name} — {len(store.list_artifacts(client_id=cid))} artifacts")

# COMMAND ----------

from scripts.setup_genie import main as setup_genie

setup_genie([])  # creates/updates the dossier Genie space; prints the space URL
print("\n03 complete. Open the Genie space above, then walk 02_demo.py for the app.")
