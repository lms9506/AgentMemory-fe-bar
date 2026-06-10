#!/usr/bin/env bash
# Build the advisor React UI. Clears Cursor/sandbox npm env that can hang installs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/src/agent_memory/ui/frontend"

# Cursor IDE terminals often set this; npm warns and may hang fetching packages.
unset npm_config_devdir NPM_CONFIG_DEVDIR 2>/dev/null || true

cd "$FRONTEND"

REGISTRY="${NPM_CONFIG_REGISTRY:-$(npm config get registry 2>/dev/null || true)}"
REGISTRY="${REGISTRY:-https://npm-proxy.cloud.databricks.com/}"
export NPM_CONFIG_REGISTRY="$REGISTRY"

if ! curl -fsS --max-time 15 "${REGISTRY}vite" >/dev/null 2>&1; then
  echo "ERROR: Cannot reach npm registry at ${REGISTRY}" >&2
  echo "  For Databricks: npm config set registry https://npm-proxy.cloud.databricks.com/" >&2
  exit 1
fi
echo "Using npm registry: ${REGISTRY}"

echo "Installing frontend dependencies..."
npm install --no-audit --no-fund

echo "Building static assets -> frontend/dist/"
npm run build

echo "Done. Run: uv run agent-memory-app"
