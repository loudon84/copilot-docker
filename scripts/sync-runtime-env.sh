#!/usr/bin/env bash
# 将 instances/<profile>/.env 中的 runtime/API 变量同步到 data/hermes/.env
# Hermes gateway 读取 $HERMES_HOME/.env，而非 compose 的 instances/<profile>/.env
set -euo pipefail

PROFILE="${1:?usage: sync-runtime-env.sh <profile>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_ENV="$BASE_DIR/instances/$PROFILE/.env"
TARGET_ENV="$BASE_DIR/instances/$PROFILE/data/hermes/.env"
SYNC_PY="$BASE_DIR/scripts/lib/sync_runtime_env.py"

if [ ! -f "$SOURCE_ENV" ]; then
  echo "ERROR: missing source env: $SOURCE_ENV" >&2
  exit 1
fi

mkdir -p "$(dirname "$TARGET_ENV")"
python3 "$SYNC_PY" --source "$SOURCE_ENV" --target "$TARGET_ENV"
chmod 600 "$TARGET_ENV" 2>/dev/null || true
