# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Demo: walk the four advisor UI panels end-to-end
# MAGIC
# MAGIC Run order: 00_setup → 01_seed → **02_demo**. Narrates the four panels of the
# MAGIC advisor app via the Python API directly; the matching app URL is printed for
# MAGIC each action so you can follow along in the UI. Attach Serverless and **Run all**.

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

# Repo root + target derived from this notebook's own workspace path (no hardcoded
# user/target); the live app URL is looked up from the deployed app via the SDK.
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
REPO_ROOT = "/Workspace" + os.path.dirname(os.path.dirname(_nb_path))
TARGET = os.path.basename(os.path.dirname(REPO_ROOT))

# The client/advisor to demo (client_0000 is the first synthetic client from 01_seed).
CLIENT_ID = "client_0000"
ADVISOR_ID = "advisor_demo_01"

from databricks.sdk import WorkspaceClient

try:
    APP_URL = WorkspaceClient().apps.get(f"wealth-advisor-{TARGET}").url.rstrip("/") + "/api"
except Exception as exc:  # noqa: BLE001 — URL is for display only; fall back to a placeholder
    APP_URL = "<your-app-url>/api"
    print(f"App URL lookup skipped ({exc!r}); printed API paths show a placeholder.")

from dotenv import load_dotenv

load_dotenv(f"{REPO_ROOT}/.env.shared", override=False)

# Point at the bundle-provisioned Lakebase instance (agent-memory-<target>); look up
# its Postgres endpoint via the SDK (matches 00_setup/01_seed — no host hardcoded).
LAKEBASE_INSTANCE = f"agent-memory-{TARGET}"
_instance = WorkspaceClient().database.get_database_instance(name=LAKEBASE_INSTANCE)
os.environ["LAKEBASE_INSTANCE_NAME"] = LAKEBASE_INSTANCE
os.environ["LAKEBASE_URL"] = f"postgresql://{_instance.read_write_dns}/databricks_postgres?sslmode=require"
os.environ["LAKEBASE_DATABASE"] = "databricks_postgres"

from agent_memory.config import Settings, ensure_databricks_auth

settings = Settings.from_env()
assert ensure_databricks_auth(settings), "Databricks auth failed."

# COMMAND ----------

# PANEL 1: Dossier Timeline — every artifact ingested for this client.
# UI: GET /api/clients/{client_id}/artifacts
print(f"=== Panel 1: Dossier Timeline for {CLIENT_ID} ===")
print(f"  API: GET {APP_URL}/clients/{CLIENT_ID}/artifacts\n")

from agent_memory.memory.store import LakebaseArtifactStore

store = LakebaseArtifactStore()
artifacts = store.list_artifacts(client_id=CLIENT_ID)
for a in artifacts:
    print(f"  [{a.ingested_at.date()}] {a.kind.upper():6} {a.original_filename}")
    if a.summary:
        print(f"    Summary: {a.summary[:120]}...")

# COMMAND ----------

# PANEL 2: Semantic Query — recall relevant chunks and ask the advisor agent.
# UI: POST /api/chat  (or /api/chat/stream for SSE). The agent surfaces considerations,
# never advice (FR-10).
print("\n=== Panel 2: Advisor Query (semantic recall) ===")
print(f"  API: POST {APP_URL}/chat\n")

from agent_memory.agents.run import run_turn_with_state

query = "What has the client said about retirement income and risk tolerance?"
print(f"Query: {query!r}\n")

final_state = run_turn_with_state(
    client_id=CLIENT_ID,
    advisor_id=ADVISOR_ID,
    user_message=query,
    settings=settings,
)
print(f"Retrieved {len(final_state['retrieved_chunks'])} chunks:")
for c in final_state["retrieved_chunks"]:
    print(f"  [artifact={c['artifact_id']}, score={c['score']:.2f}] {c['content'][:80]}...")

print(f"\nAdvisor response:\n{final_state['response']}")

# COMMAND ----------

# PANEL 3: Distillation → Profile Proposal (HITL). Triggers distillation inline; the
# advisor accepts/edits/rejects the proposal in the UI.
print("\n=== Panel 3: Distillation & Profile Proposal ===")
print(f"  API: POST {APP_URL}/distill\n")

from agent_memory.memory.distillation import LakebaseArtifactSource, run_distillation
from agent_memory.memory.proposal_store import LakebaseProposalStore

proposal_store = LakebaseProposalStore(settings)
results = run_distillation(
    client_id=CLIENT_ID,
    settings=settings,
    hitl=True,
    artifact_source=LakebaseArtifactSource(settings),
    proposal_store=proposal_store,
)
for r in results:
    print(f"  {r.client_id}: {r.status}" + (f" — proposal_id={r.proposal_id}" if r.proposal_id else ""))

proposals = proposal_store.list_proposals(status="pending", client_id=CLIENT_ID)
if proposals:
    p = proposals[0]
    print(f"\nPending proposal {p.proposal_id}:")
    print(f"  risk_tolerance: {p.proposed_profile.risk_tolerance}")
    print(f"  investment_goals: {p.proposed_profile.investment_goals}")
    print(f"  summary: {p.proposed_profile.summary[:120]}...")
    print(f"\n  Review in the UI: POST {APP_URL}/proposals/{p.proposal_id}/accept")

# COMMAND ----------

# PANEL 4: Provenance — inspect an artifact and its raw-byte source.
# UI: GET /api/artifacts/{id}  and  GET /api/artifacts/{id}/raw
print("\n=== Panel 4: Provenance ===")
if artifacts:
    a = artifacts[0]
    print(f"  API: GET {APP_URL}/artifacts/{a.artifact_id}")
    detail = store.get_artifact(a.artifact_id)
    print(f"  artifact_id:      {detail.artifact_id}")
    print(f"  original_filename:{detail.original_filename}")
    print(f"  volume_path:      {detail.volume_path}")
    print(f"  content_hash:     {detail.content_hash}")
    print(f"  extracted_text:   {(detail.extracted_text or '')[:200]}")
    print(f"\n  Raw bytes: GET {APP_URL}/artifacts/{a.artifact_id}/raw")

print("\nDemo complete.")
