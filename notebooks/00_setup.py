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
# MAGIC `LAKEBASE_*`) — no workspace values are hardcoded. The bundle sync path is derived
# MAGIC automatically from this notebook's own location, so there is **nothing to edit**:
# MAGIC clone, `databricks bundle deploy --target <target>`, then **Run all**. (The
# MAGIC `%pip install ..` below installs the package from the repo root — a bundle-synced
# MAGIC notebook's working directory is its own folder, so `..` is the repo root.)

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

# Bundle-synced repo root + app name, derived from this notebook's own workspace path
# (no hardcoded user/target). The notebook lives at <REPO_ROOT>/notebooks/<name> under
# /Workspace/Users/<user>/.bundle/agent-memory/<target>/files, so REPO_ROOT is two
# levels up and <target> is the directory above it. Used to read .env.shared + the .sql.
import os

_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
REPO_ROOT = "/Workspace" + os.path.dirname(os.path.dirname(_nb_path))
TARGET = os.path.basename(os.path.dirname(REPO_ROOT))  # .../agent-memory/<target>/files
APP_NAME = f"wealth-advisor-{TARGET}"  # bundle app resource (wealth-advisor-${bundle.target})
print(f"REPO_ROOT={REPO_ROOT}  TARGET={TARGET}  APP_NAME={APP_NAME}")

# Load catalog/schema (+ FM endpoints) from the synced .env.shared (generated from
# your .env by scripts/deploy_bundle.sh — single source of truth).
from dotenv import load_dotenv

load_dotenv(f"{REPO_ROOT}/.env.shared", override=False)

# The Lakebase instance is PROVISIONED by the bundle as `agent-memory-<target>`.
# Derive its name and look up the Postgres endpoint via the SDK, then expose them
# the way the connection layer expects (provisioned-instance OAuth path) — no host
# is hardcoded anywhere.
from databricks.sdk import WorkspaceClient

LAKEBASE_INSTANCE = f"agent-memory-{TARGET}"
_instance = WorkspaceClient().database.get_database_instance(name=LAKEBASE_INSTANCE)
os.environ["LAKEBASE_INSTANCE_NAME"] = LAKEBASE_INSTANCE
os.environ["LAKEBASE_URL"] = f"postgresql://{_instance.read_write_dns}/databricks_postgres?sslmode=require"
os.environ["LAKEBASE_DATABASE"] = "databricks_postgres"
print(f"Lakebase instance={LAKEBASE_INSTANCE}  host={_instance.read_write_dns}")

from agent_memory.config import Settings, ensure_databricks_auth

settings = Settings.from_env()
assert ensure_databricks_auth(settings), "Databricks auth failed — check the notebook's workspace credentials."

CATALOG = settings.uc_catalog
SCHEMA = settings.uc_schema
VOLUME_NAME = settings.volume_name
print(f"catalog={CATALOG}  schema={SCHEMA}  volume={VOLUME_NAME}")

# COMMAND ----------

# 1. UC schema + Volume for raw artifact bytes (idempotent). The schema is created
#    here (not as a bundle resource) so its name stays the literal UC_SCHEMA that the
#    app, jobs, and this notebook all share — dev-mode name prefixing would otherwise
#    rename a bundle-managed schema to dev_<user>_<schema>. Needs CREATE SCHEMA on the
#    catalog (the deploying user has it; the catalog itself must already exist).
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`")
spark.sql(f"CREATE VOLUME IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`.`{VOLUME_NAME}`")
print(f"Schema + Volume ready: /Volumes/{CATALOG}/{SCHEMA}/{VOLUME_NAME}")

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

# 3b. Grant the app service principal access to the Lakebase tables. The app binding
#     gives the SP a Postgres role + CONNECT/CREATE, but the tables above are owned by
#     you (this notebook), so the SP needs explicit table grants. ALL TABLES + ALTER
#     DEFAULT PRIVILEGES keeps this correct across future schema migrations.
import re

if "app_sp" in dir() and app_sp and re.fullmatch(r"[0-9a-fA-F-]{36}", app_sp):
    role = f'"{app_sp}"'  # the SP's Postgres role is its client id (UUID)
    grant_sql = [
        f"GRANT USAGE ON SCHEMA public TO {role}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {role}",
    ]
    try:
        with lakebase_connection(settings, register_pgvector=False) as conn, conn.cursor() as cur:
            for stmt in grant_sql:
                cur.execute(stmt)
            conn.commit()
        print(f"Granted Lakebase table access to app SP {app_sp}.")
    except Exception as exc:  # noqa: BLE001 — SP role may not exist yet; surface + continue
        print(f"Lakebase SP grant skipped ({exc!r}). Re-run after the app's first deploy.")
else:
    print("App SP id unavailable — skipping Lakebase SP grant (re-run cell 2 first).")

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
