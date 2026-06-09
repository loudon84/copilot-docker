#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTANCES_ROOT="$BASE_DIR/instances"
REQUIRED_DIRS=(skills tools plugins mcp policies skill-bundles gbrain)

if [ ! -d "$INSTANCES_ROOT" ]; then
  echo "WARN: no instances directory: $INSTANCES_ROOT"
  exit 0
fi

repaired=0

for DATA_DIR in "$INSTANCES_ROOT"/*/data/hermes; do
  [ -d "$DATA_DIR" ] || continue
  PROFILE="$(basename "$(dirname "$(dirname "$DATA_DIR")")")"
  echo "[repair] $PROFILE -> $DATA_DIR"

  for d in "${REQUIRED_DIRS[@]}"; do
    mkdir -p "$DATA_DIR/$d"
  done

  rm -f "$DATA_DIR/tools/tools" 2>/dev/null || true
  rm -f "$DATA_DIR/plugins/plugins" 2>/dev/null || true

  chown -R 1000:1000 \
    "$DATA_DIR/tools" \
    "$DATA_DIR/plugins" \
    "$DATA_DIR/skills" \
    "$DATA_DIR/mcp" \
    "$DATA_DIR/policies" \
    "$DATA_DIR/skill-bundles" \
    "$DATA_DIR/gbrain" 2>/dev/null || true

  chmod -R u+rwX,g+rwX \
    "$DATA_DIR/tools" \
    "$DATA_DIR/plugins" \
    "$DATA_DIR/skills" \
    "$DATA_DIR/mcp" \
    "$DATA_DIR/policies" \
    "$DATA_DIR/skill-bundles" \
    "$DATA_DIR/gbrain" 2>/dev/null || true

  repaired=$((repaired + 1))
done

echo "OK: repaired $repaired instance(s)"
