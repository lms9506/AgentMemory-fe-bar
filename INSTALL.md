# Install — AI Wealth Advisor (Agent Memory accelerator)

A Databricks Solution Accelerator: an **advisor-facing** app that turns a client's
documents (meeting notes, statements, scanned forms, handwritten notes) into a
governed, longitudinal **client memory** on Lakebase + Unity Catalog. This guide
deploys it to your **own Databricks workspace** from scratch.

Deploying takes ~15 minutes, most of it waiting for the Lakebase instance to start.

---

## 1. What your workspace needs

- **Unity Catalog** enabled, and a **catalog you can create a schema in** (e.g. `main`,
  or one your admin gave you `CREATE SCHEMA` on).
- **Lakebase** (Postgres) available — Databricks → *Compute* → *Database instances*.
- **Serverless SQL** available.
- **Foundation Model APIs** — the endpoints `databricks-meta-llama-3-3-70b-instruct`
  and `databricks-gte-large-en` (pay-per-token; available by default in most regions).

You don't create the Lakebase instance or the SQL warehouse yourself — **the deploy
provisions them.**

## 2. Tools on your laptop

- **Databricks CLI** ≥ 0.295.1 — `brew install databricks` (or see Databricks docs).
- **uv** — `curl -LsSf https://astral.sh/uv/install.sh | sh` (https://docs.astral.sh/uv/).
- **Node/npm is NOT required** — the web UI is pre-built and shipped in this package.

## 3. Deploy

```bash
# a) Log in to your workspace (opens a browser)
databricks auth login --profile my-workspace

# b) Configure — copy the template and set two values
cp .env.example .env
#    edit .env:  DATABRICKS_PROFILE=my-workspace
#                UC_CATALOG=<a catalog you can write to>

# c) Deploy (builds the wheel, provisions Lakebase + SQL warehouse + the App + jobs,
#    and applies the permission grants). Run from this folder:
./scripts/deploy_bundle.sh dev
```

`.env` is the only file you edit. The script feeds it to the deploy and writes the
provisioned Lakebase + warehouse ids back into `.env` when it finishes.

> If `databricks bundle deploy` fails downloading Terraform with `openpgp: key expired`,
> upgrade the CLI (`brew upgrade databricks`), or run with a local Terraform:
> `export DATABRICKS_TF_EXEC_PATH="$(which terraform)" DATABRICKS_TF_VERSION=1.5.5`.

## 4. Set up + seed (in the workspace)

The deploy syncs three notebooks to your workspace under
`/Workspace/Users/<you>/.bundle/agent-memory/dev/files/notebooks/`. Open each in order,
attach **Serverless**, and click **Run all**:

1. **`00_setup`** — creates the Lakebase schema, the UC Volume, the Delta profile table,
   and grants the app's service principal access.
2. **`01_seed`** — loads three demo client dossiers (mixed formats — handwritten, PDF,
   scanned, typed — backdated over ~8 months).
3. **`02_demo`** — walks the four UI panels end-to-end.

The notebooks figure out everything from their own location — nothing to edit.

## 5. Open the app

The deploy prints the App URL at the end (or: Databricks → *Compute* → *Apps* →
`wealth-advisor-dev`). It's workspace-authenticated (advisor-internal, not public).

---

## What gets created

In your workspace, under target `dev`: a Lakebase instance `agent-memory-dev`, a
serverless SQL warehouse `agent-memory-dev`, the `wealth-advisor-dev` App, three nightly
jobs (distillation + eval), a UC Volume `dossier_raw`, and the Lakebase/Delta tables
(created by `00_setup`). Everything is named with the `dev` target so it's easy to find
and tear down.

## Cost

The Lakebase instance is the smallest unit (`CU_1`); the SQL warehouse is `2X-Small`
serverless with a 10-minute auto-stop. Tear everything down with:

```bash
databricks bundle destroy --target dev
```

## Troubleshooting

- **`Refresh token is invalid` / auth errors** — re-run `databricks auth login --profile <p>`.
- **FM endpoint not found** — your region may name them differently; set `FM_API_ENDPOINT`
  / `FM_API_EMBEDDING_ENDPOINT` in `.env` to endpoints that exist in your workspace
  (Databricks → *Serving*).
- **Lakebase not available** — confirm Database Instances are enabled for your workspace.
- **Want to rebuild the UI yourself** — install Node, then `./scripts/build_frontend.sh`
  (it rebuilds when npm is present; otherwise it uses the shipped `dist/`).

See `README.md` for the architecture and `docs/` for the full design.
