#!/usr/bin/env bash
# Container entrypoint helper: sync compose-injected env -> /data/hermes/.env
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-/data/hermes}"
TARGET_ENV="$HERMES_HOME/.env"
SYNC_PY="/usr/local/bin/sync_runtime_env.py"

if [ ! -f "$SYNC_PY" ]; then
  echo "[sync-runtime-env] WARN: $SYNC_PY missing; skip"
  exit 0
fi

python3 "$SYNC_PY" --target "$TARGET_ENV"
chmod 600 "$TARGET_ENV" 2>/dev/null || true
