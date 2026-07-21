#!/usr/bin/env bash
# Sync runtime/semantic (+ policies) into instance finance-bi paths (PRD v1.10 §19).
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE=""
INSTANCE_DIR=""
DATA_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --instance-dir) INSTANCE_DIR="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --package-root) PACKAGE_ROOT="$2"; shift 2 ;;
    -h|--help)
      echo "usage: sync-semantic-catalog.sh --profile <p> --instance-dir <d> --data-dir <d>"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$DATA_DIR" ]]; then
  echo "ERROR: --data-dir is required" >&2
  exit 1
fi

SEMANTIC_SRC="$PACKAGE_ROOT/runtime/semantic"
POLICY_SRC="$PACKAGE_ROOT/runtime/policies"
SEMANTIC_DST="$DATA_DIR/finance-bi/semantic"
POLICY_DST="$DATA_DIR/finance-bi/policies"
BACKUP_ROOT="$DATA_DIR/.backup/semantic-$(date +%Y%m%d-%H%M%S)"

[[ -d "$SEMANTIC_SRC" ]] || { echo "ERROR: semantic source missing: $SEMANTIC_SRC" >&2; exit 1; }

mkdir -p "$DATA_DIR/finance-bi/semantic" "$DATA_DIR/finance-bi/policies" "$DATA_DIR/finance-bi/state"

# Backup existing catalog if present
if [[ -d "$SEMANTIC_DST" ]] && [[ -n "$(ls -A "$SEMANTIC_DST" 2>/dev/null || true)" ]]; then
  mkdir -p "$BACKUP_ROOT"
  cp -a "$SEMANTIC_DST" "$BACKUP_ROOT/semantic" || true
  echo "[bi] backed up existing semantic -> $BACKUP_ROOT/semantic"
fi
if [[ -d "$POLICY_DST" ]] && [[ -n "$(ls -A "$POLICY_DST" 2>/dev/null || true)" ]]; then
  mkdir -p "$BACKUP_ROOT"
  cp -a "$POLICY_DST" "$BACKUP_ROOT/policies" || true
fi

# Sync semantic (replace content, keep parent)
TMP_SEMANTIC="$(mktemp -d "${TMPDIR:-/tmp}/bi-semantic.XXXXXX")"
cleanup() { rm -rf "$TMP_SEMANTIC"; }
trap cleanup EXIT

cp -R "$SEMANTIC_SRC/." "$TMP_SEMANTIC/"
rm -rf "$SEMANTIC_DST"
mkdir -p "$SEMANTIC_DST"
cp -R "$TMP_SEMANTIC/." "$SEMANTIC_DST/"
echo "[bi] synced semantic catalog -> $SEMANTIC_DST"

if [[ -d "$POLICY_SRC" ]]; then
  mkdir -p "$POLICY_DST"
  cp -R "$POLICY_SRC/." "$POLICY_DST/"
  mkdir -p "$DATA_DIR/policies"
  cp -R "$POLICY_SRC/." "$DATA_DIR/policies/" 2>/dev/null || true
  echo "[bi] synced policies -> $POLICY_DST"
fi

# Basic validation: datasets dir must exist
if [[ ! -d "$SEMANTIC_DST/datasets" ]]; then
  echo "ERROR: semantic sync failed validation (datasets missing)" >&2
  if [[ -d "$BACKUP_ROOT/semantic" ]]; then
    rm -rf "$SEMANTIC_DST"
    mkdir -p "$SEMANTIC_DST"
    cp -R "$BACKUP_ROOT/semantic/." "$SEMANTIC_DST/"
    echo "[bi] restored previous semantic catalog from backup"
  fi
  exit 1
fi

echo "OK: sync-semantic-catalog ${PROFILE:-unknown}"
exit 0
