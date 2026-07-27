#!/usr/bin/env bash
# Build the advisor React UI. Clears Cursor/sandbox npm env that can hang installs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/src/agent_memory/ui/frontend"

# This accelerator ships a pre-built UI in frontend/dist/. If it's present and you
# don't have Node/npm (or you set SKIP_FRONTEND_BUILD=1), use the shipped assets as-is
# — no Node toolchain required to deploy. Devs with npm get a fresh build by default.
if [[ -f "$FRONTEND/dist/index.html" ]]; then
  if [[ "${SKIP_FRONTEND_BUILD:-}" == "1" ]] || ! command -v npm >/dev/null 2>&1; then
    echo "Using pre-built UI in frontend/dist/ (skipping npm build)."
    exit 0
  fi
fi

# Cursor IDE terminals often set this; npm warns and may hang fetching packages.
unset npm_config_devdir NPM_CONFIG_DEVDIR 2>/dev/null || true

cd "$FRONTEND"

REGISTRY="${NPM_CONFIG_REGISTRY:-$(npm config get registry 2>/dev/null || true)}"
REGISTRY="${REGISTRY:-https://npm-proxy.cloud.databricks.com/}"
export NPM_CONFIG_REGISTRY="$REGISTRY"

if ! curl -fsS --max-time 15 "${REGISTRY}vite" >/dev/null 2>&1; then
  # Registry unreachable (e.g. off the Databricks network). If a pre-built UI is
  # shipped, use it rather than failing the whole deploy — the accelerator is
  # designed to deploy with the shipped dist/ and no Node toolchain.
  if [[ -f "$FRONTEND/dist/index.html" ]]; then
    echo "WARNING: Cannot reach npm registry at ${REGISTRY} — using pre-built UI in frontend/dist/." >&2
    echo "  (To rebuild the UI, connect to the Databricks network or set NPM_CONFIG_REGISTRY.)" >&2
    exit 0
  fi
  echo "ERROR: Cannot reach npm registry at ${REGISTRY} and no pre-built UI in frontend/dist/." >&2
  echo "  For Databricks: npm config set registry https://npm-proxy.cloud.databricks.com/" >&2
  exit 1
fi
echo "Using npm registry: ${REGISTRY}"

echo "Installing frontend dependencies..."
npm install --no-audit --no-fund

echo "Building static assets -> frontend/dist/"
npm run build

echo "Done. Run: uv run agent-memory-app"
