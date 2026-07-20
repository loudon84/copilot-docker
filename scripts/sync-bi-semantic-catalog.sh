#!/usr/bin/env bash
# Sync expert-templates/<expert>/semantic (+ policies) into instance finance-bi paths.
set -euo pipefail

PROFILE="${1:?usage: sync-bi-semantic-catalog.sh <profile> [expert]}"
EXPERT="${2:-bi-strategic-office}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$BASE_DIR/instances/$PROFILE/data/hermes"
TPL="$BASE_DIR/expert-templates/$EXPERT"

[ -d "$TPL" ] || { echo "ERROR: expert template not found: $EXPERT"; exit 1; }

mkdir -p "$DATA_DIR/finance-bi/semantic" "$DATA_DIR/finance-bi/policies" "$DATA_DIR/finance-bi/state"

if [ -d "$TPL/semantic" ]; then
  rm -rf "$DATA_DIR/finance-bi/semantic"
  mkdir -p "$DATA_DIR/finance-bi/semantic"
  cp -R "$TPL/semantic/." "$DATA_DIR/finance-bi/semantic/"
  echo "[bi] synced semantic catalog -> $DATA_DIR/finance-bi/semantic"
else
  echo "[bi] WARN: no semantic/ in template $EXPERT"
fi

if [ -d "$TPL/policies" ]; then
  mkdir -p "$DATA_DIR/finance-bi/policies"
  cp -R "$TPL/policies/." "$DATA_DIR/finance-bi/policies/"
  # also keep a copy under /data/hermes/policies for general tooling
  mkdir -p "$DATA_DIR/policies"
  cp -R "$TPL/policies/." "$DATA_DIR/policies/" 2>/dev/null || true
  echo "[bi] synced policies -> $DATA_DIR/finance-bi/policies"
fi

# remove template copies that should live under finance-bi only (optional cleanup of root)
# keep skills/SOUL etc. from inject; leave semantic/ under hermes root if copied by inject
if [ -d "$DATA_DIR/semantic" ] && [ -d "$DATA_DIR/finance-bi/semantic" ]; then
  # fine to keep both; runtime uses FINANCE_BI_CATALOG_PATH
  :
fi

echo "OK: sync-bi-semantic-catalog $PROFILE ($EXPERT)"
