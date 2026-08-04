#!/usr/bin/env bash
# Build UI + wheel, then deploy DAB (App + distillation job) to the target workspace.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-dev}"

cd "$ROOT"
./scripts/build_frontend.sh

echo "Building Python wheel..."
uv build

echo "Deploying bundle (target=${TARGET})..."
# Auth: ensure `databricks auth login --profile fevm-serverless-stable-2eacei` (see databricks.yml).
# Host/profile are literals in databricks.yml — edit there if your workspace differs from .env.shared.
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
export DATABRICKS_CONFIG_PROFILE="${DATABRICKS_PROFILE:-adb-984752964297111}"

if ! databricks auth describe -p "${DATABRICKS_CONFIG_PROFILE}" >/dev/null 2>&1; then
  echo "ERROR: Databricks auth failed for profile ${DATABRICKS_CONFIG_PROFILE}." >&2
  echo "  Run: databricks auth login --profile ${DATABRICKS_CONFIG_PROFILE}" >&2
  echo "  After CLI 1.0 upgrade, old token cache may need a fresh login (exit status 45)." >&2
  exit 1
fi

# Hashicorp rotated PGP keys Apr 2026; CLI <0.295.1 fails Terraform download (databricks/cli#5022).
CLI_VER="$(databricks --version 2>/dev/null | awk '{print $3}' || true)"
if [[ -n "${CLI_VER}" ]] && [[ "${CLI_VER}" < "0.295.1" ]]; then
  echo "WARNING: Databricks CLI ${CLI_VER} may fail bundle deploy (expired Terraform GPG key)." >&2
  echo "  Upgrade: brew upgrade databricks   (need >=0.295.1, or use workaround below)" >&2
  if command -v terraform >/dev/null 2>&1; then
    export DATABRICKS_TF_EXEC_PATH="$(command -v terraform)"
    export DATABRICKS_TF_VERSION="${DATABRICKS_TF_VERSION:-1.5.5}"
    echo "  Using system terraform: ${DATABRICKS_TF_EXEC_PATH} (version ${DATABRICKS_TF_VERSION})" >&2
  fi
fi

databricks bundle deploy --target "$TARGET"

# bundle deploy syncs files + job configs but does NOT restart the App.
# A separate apps deploy is required to pick up the new wheel.
echo "Deploying App (smart-advise-${TARGET})..."
databricks apps deploy "smart-advise-${TARGET}" -p "${DATABRICKS_CONFIG_PROFILE}"
echo "  App deployment triggered."

# ── Post-deploy permission grants ─────────────────────────────────────────────
# These run as the deploying user (you), which is required because:
#   - UC grants need a user who has MANAGE/ALL PRIVILEGES on the catalog/schema
#   - Warehouse set-permissions needs CAN_MANAGE on the warehouse
#   - Lakebase GRANT statements need the table owner
#
# The app service principal (SP) is created by the bundle on first deploy;
# its client_id is read here from the deployed app resource.

echo "Reading app service principal client ID..."
SP_CLIENT_ID=$(databricks apps get "smart-advise-${TARGET}" \
  -p "${DATABRICKS_CONFIG_PROFILE}" -o json 2>/dev/null \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['service_principal_client_id'])" \
  || true)

if [[ -z "${SP_CLIENT_ID}" ]]; then
  echo "WARNING: Could not read app SP client ID — skipping permission grants." >&2
  echo "  The app may show permission errors until grants are applied manually." >&2
else
  echo "App SP: ${SP_CLIENT_ID}"

  # Read target-specific catalog/schema/warehouse from databricks.yml via bundle summary.
  BUNDLE_SUMMARY=$(databricks bundle summary --target "$TARGET" -o json 2>/dev/null || echo "{}")
  CATALOG=$(echo "$BUNDLE_SUMMARY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('variables',{}).get('catalog',{}).get('value',''))" 2>/dev/null || true)
  SCHEMA=$(echo "$BUNDLE_SUMMARY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('variables',{}).get('schema',{}).get('value','wealth_advisor'))" 2>/dev/null || echo "wealth_advisor")
  SCHEMA="${SCHEMA:-wealth_advisor}"
  WAREHOUSE_ID=$(echo "$BUNDLE_SUMMARY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('variables',{}).get('sql_warehouse_id',{}).get('value',''))" 2>/dev/null || true)
  LAKEBASE_BRANCH=$(echo "$BUNDLE_SUMMARY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('variables',{}).get('lakebase_branch',{}).get('value',''))" 2>/dev/null || true)

  # 1. Unity Catalog grants
  if [[ -n "${CATALOG}" ]]; then
    echo "Granting UC permissions on ${CATALOG}.${SCHEMA}..."
    databricks grants update catalog "${CATALOG}" \
      -p "${DATABRICKS_CONFIG_PROFILE}" \
      --json "{\"changes\":[{\"principal\":\"${SP_CLIENT_ID}\",\"add\":[\"USE CATALOG\"]}]}" \
      > /dev/null
    databricks grants update schema "${CATALOG}.${SCHEMA}" \
      -p "${DATABRICKS_CONFIG_PROFILE}" \
      --json "{\"changes\":[{\"principal\":\"${SP_CLIENT_ID}\",\"add\":[\"USE SCHEMA\",\"SELECT\",\"MODIFY\",\"CREATE TABLE\"]}]}" \
      > /dev/null
    echo "  UC grants applied."
  fi

  # 2. SQL warehouse CAN_USE
  if [[ -n "${WAREHOUSE_ID}" ]]; then
    echo "Granting CAN_USE on warehouse ${WAREHOUSE_ID}..."
    databricks warehouses set-permissions "${WAREHOUSE_ID}" \
      -p "${DATABRICKS_CONFIG_PROFILE}" \
      --json "{\"access_control_list\":[{\"service_principal_name\":\"${SP_CLIENT_ID}\",\"permission_level\":\"CAN_USE\"}]}" \
      > /dev/null
    echo "  Warehouse grant applied."
  fi

  # 2b. HITL distillation job — the app's "Propose update" button triggers it as the
  # app SP, which can neither see nor run the job without an explicit grant. The job
  # ACL otherwise lists only the deploying user (IS_OWNER) + admins. Match the bare
  # suffix so this works under the dev-mode "[dev <user>] " name prefix and in prod.
  HITL_JOB_ID=$(databricks jobs list -p "${DATABRICKS_CONFIG_PROFILE}" -o json 2>/dev/null \
    | python3 -c "import sys,json; print(next((str(j['job_id']) for j in json.load(sys.stdin) if (j.get('settings',{}).get('name') or '').endswith('agent-memory-distillation-hitl-${TARGET}')), ''))" \
    || true)
  if [[ -n "${HITL_JOB_ID}" ]]; then
    echo "Granting CAN_MANAGE_RUN on HITL job ${HITL_JOB_ID} to app SP..."
    databricks permissions update jobs "${HITL_JOB_ID}" \
      -p "${DATABRICKS_CONFIG_PROFILE}" \
      --json "{\"access_control_list\":[{\"service_principal_name\":\"${SP_CLIENT_ID}\",\"permission_level\":\"CAN_MANAGE_RUN\"}]}" \
      > /dev/null
    echo "  HITL job grant applied."
  fi

  # 3. Lakebase Postgres table grants
  if [[ -n "${LAKEBASE_BRANCH}" ]]; then
    echo "Granting Lakebase table access to SP ${SP_CLIENT_ID}..."
    LB_HOST=$(databricks postgres list-endpoints "${LAKEBASE_BRANCH}" \
      -p "${DATABRICKS_CONFIG_PROFILE}" -o json \
      | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['status']['hosts']['host'])" 2>/dev/null || true)
    LB_TOKEN=$(databricks postgres generate-database-credential \
      "${LAKEBASE_BRANCH}/endpoints/primary" \
      -p "${DATABRICKS_CONFIG_PROFILE}" -o json \
      | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null || true)
    LB_USER=$(databricks current-user me -p "${DATABRICKS_CONFIG_PROFILE}" -o json \
      | python3 -c "import sys,json; print(json.load(sys.stdin)['userName'])" 2>/dev/null || true)

    if [[ -n "${LB_HOST}" && -n "${LB_TOKEN}" && -n "${LB_USER}" ]]; then
      PGPASSWORD="${LB_TOKEN}" psql \
        "host=${LB_HOST} port=5432 dbname=databricks_postgres user=${LB_USER} sslmode=require" \
        -v sp="${SP_CLIENT_ID}" <<'SQL'
-- Dossier-model tables (artifacts, artifact_chunks, audit_log, profile_proposals,
-- clients). GRANT on ALL TABLES rather than naming each, so this stays correct
-- across schema migrations; ALTER DEFAULT PRIVILEGES covers tables created later.
GRANT USAGE ON SCHEMA public                                        TO :"sp";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"sp";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public               TO :"sp";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES    TO :"sp";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES                  TO :"sp";
SQL
      echo "  Lakebase grants applied."
    else
      echo "WARNING: Could not connect to Lakebase — skipping table grants." >&2
      echo "  Run manually: PGPASSWORD=<token> psql ... -c 'GRANT ...'" >&2
    fi
  fi
fi

echo ""
echo "Done. Open the app:"
echo "  https://smart-advise-${TARGET}-$(databricks current-user me \
  -p "${DATABRICKS_CONFIG_PROFILE}" -o json 2>/dev/null \
  | python3 -c "import sys,json; \
    me=json.load(sys.stdin); \
    print(str(me.get('id','')))" \
  2>/dev/null || echo '<workspace-id>').aws.databricksapps.com"
echo "Or run a job:"
echo "  databricks bundle run smart_advise --target ${TARGET}"
