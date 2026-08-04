# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Setup: provision the AgentMemory dossier infrastructure
# MAGIC
# MAGIC Run order: **00_setup → 01_seed → 02_demo**. Attach **Serverless** (or any
# MAGIC UC-enabled cluster) and **Run all**. No SQL warehouse needed — the synthetic
# MAGIC artifacts are plain text, so `ai_parse_document` never fires during setup/seed.
# MAGIC
# MAGIC This notebook:
# MAGIC 1. creates the UC Volume for raw artifact bytes,
# MAGIC 2. grants the app service principal `READ/WRITE VOLUME`,
# MAGIC 3. applies the Lakebase schema, and
# MAGIC 4. applies the Delta `client_profile` table.
# MAGIC
# MAGIC > ⚠️ **Destructive:** the Lakebase schema drops the v1 `conversation_turns` /
# MAGIC > `turn_embeddings` tables and creates `artifacts` / `artifact_chunks`. The data
# MAGIC > is synthetic/reference (ADR-0004), but this is the point of no return.
# MAGIC
# MAGIC Config is read from the bundle-synced `.env.shared` (`UC_CATALOG`, `UC_SCHEMA`,
# MAGIC `LAKEBASE_*`) — no workspace values are hardcoded. The only thing you may need to
# MAGIC edit is the bundle sync path (in the `%pip install` cell **and** the `REPO_ROOT`
# MAGIC constant) if your user/target differ from `linus.meister@databricks.com` / `dev`:
# MAGIC `/Workspace/Users/<you>/.bundle/agent-memory/<target>/files`.

# COMMAND ----------

# MAGIC %pip install /Workspace/Users/linus.meister@databricks.com/.bundle/agent-memory/dev/files

# COMMAND ----------

# Databricks Serverless %pip auto-restarts Python; guard the explicit restart so a
# second (redundant) restart can't error the cell.
try:
    dbutils.library.restartPython()
except Exception:
    pass  # already restarted by %pip install

# COMMAND ----------

# Bundle-synced repo root (same path as the %pip install above). Used to read
# .env.shared and the .sql schema files.
REPO_ROOT = "/Workspace/Users/linus.meister@databricks.com/.bundle/agent-memory/dev/files"
APP_NAME = "smart-advise-dev"  # bundle app resource; edit if your target differs

# Load team config (UC_CATALOG / UC_SCHEMA / LAKEBASE_*) from the synced .env.shared.
from dotenv import load_dotenv

load_dotenv(f"{REPO_ROOT}/.env.shared", override=False)

from agent_memory.config import Settings, ensure_databricks_auth

settings = Settings.from_env()
assert ensure_databricks_auth(settings), "Databricks auth failed — check the notebook's workspace credentials."

CATALOG = settings.uc_catalog
SCHEMA = settings.uc_schema
VOLUME_NAME = settings.volume_name
print(f"catalog={CATALOG}  schema={SCHEMA}  volume={VOLUME_NAME}")

# COMMAND ----------

# 1. UC Volume for raw artifact bytes (idempotent — the bundle may have created it already).
spark.sql(f"CREATE VOLUME IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`.`{VOLUME_NAME}`")
print(f"Volume ready: /Volumes/{CATALOG}/{SCHEMA}/{VOLUME_NAME}")

# COMMAND ----------

# 2. Grant READ+WRITE VOLUME to the app service principal (the app needs this to
#    save raw uploads and serve raw-byte downloads). The SP is looked up from the
#    deployed app — no need to paste an id.
from databricks.sdk import WorkspaceClient

try:
    app_sp = WorkspaceClient().apps.get(APP_NAME).service_principal_client_id
    spark.sql(
        f"GRANT READ VOLUME, WRITE VOLUME "
        f"ON VOLUME `{CATALOG}`.`{SCHEMA}`.`{VOLUME_NAME}` "
        f"TO `{app_sp}`"
    )
    print(f"Granted READ+WRITE VOLUME to app SP {app_sp}.")
except Exception as exc:  # noqa: BLE001 — surface the cause; grant is recoverable manually
    print(f"Auto-grant skipped ({exc!r}). Grant READ/WRITE VOLUME to the app SP manually.")

# COMMAND ----------

# 3. Apply the Lakebase schema (artifacts, artifact_chunks, audit_log, profile_proposals,
#    clients; drops the v1 turn tables). Uses the repo's OAuth Lakebase connection and the
#    same statement splitter the apply-schema script uses.
from agent_memory.memory.connection import lakebase_connection
from agent_memory.memory.lakebase_ddl import split_sql_statements

lakebase_sql = open(f"{REPO_ROOT}/databricks/lakebase_schema.sql").read()
statements = split_sql_statements(lakebase_sql)
with lakebase_connection(settings, register_pgvector=False) as conn, conn.cursor() as cur:
    for statement in statements:
        cur.execute(statement)
    conn.commit()
print(f"Applied {len(statements)} Lakebase statements (artifacts, artifact_chunks, audit_log, profile_proposals, clients).")

# COMMAND ----------

# 4. Apply the Delta client_profile table via Spark (no SQL warehouse required).
delta_sql = open(f"{REPO_ROOT}/databricks/delta_schema.sql").read()
for statement in split_sql_statements(delta_sql):
    spark.sql(statement.replace("${catalog}", CATALOG).replace("${schema}", SCHEMA))
print(f"Delta table ready: `{CATALOG}`.`{SCHEMA}`.client_profile")

# COMMAND ----------

# 5. Verify.
display(spark.sql(f"SHOW TABLES IN `{CATALOG}`.`{SCHEMA}`"))
print(dbutils.fs.ls(f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME_NAME}"))
print("Setup complete. Run 01_seed.py next.")