#!/usr/bin/env bash
# Update installed bi-strategic-office package assets (PRD v1.11.1 hotfix).
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE=""
INSTANCE_DIR=""
DATA_DIR=""
REPO_ROOT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --instance-dir) INSTANCE_DIR="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --repo-root) REPO_ROOT="$2"; shift 2 ;;
    -h|--help)
      echo "usage: update.sh --profile <p> --instance-dir <d> --data-dir <d> --repo-root <d>"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

[[ -n "$PROFILE" && -n "$INSTANCE_DIR" && -n "$DATA_DIR" && -n "$REPO_ROOT" ]] \
  || { echo "ERROR: --profile/--instance-dir/--data-dir/--repo-root required" >&2; exit 1; }

PYTHON_BIN="$(command -v python3 || command -v python || true)"
NEW_VERSION="$(tr -d ' \n\r' < "$PACKAGE_ROOT/VERSION")"
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$DATA_DIR/.backup/update-$TS"
mkdir -p "$BACKUP_DIR"

echo "[update] package version=$NEW_VERSION"
if [[ -n "$PYTHON_BIN" ]]; then
  OLD="$("$PYTHON_BIN" "$PACKAGE_ROOT/lib/package_state.py" read --data-dir "$DATA_DIR" 2>/dev/null || true)"
  echo "[update] current package-state:"
  echo "$OLD" | sed 's/^/  /' || true
fi

# Backup plugin + SQLite before overwrite (rollback hint on failure)
echo "[update] backup → $BACKUP_DIR"
if [[ -d "$DATA_DIR/plugins/hermes-sqlbot-adapter" ]]; then
  mkdir -p "$BACKUP_DIR/plugins"
  cp -a "$DATA_DIR/plugins/hermes-sqlbot-adapter" "$BACKUP_DIR/plugins/" 2>/dev/null || true
fi
if [[ -f "$DATA_DIR/sqlbot-adapter/state/sqlbot_sessions.db" ]]; then
  mkdir -p "$BACKUP_DIR/sqlbot-adapter/state"
  cp -a "$DATA_DIR/sqlbot-adapter/state/sqlbot_sessions.db"* "$BACKUP_DIR/sqlbot-adapter/state/" 2>/dev/null || true
fi
if [[ -f "$DATA_DIR/sqlbot-adapter/package-state.yaml" ]]; then
  mkdir -p "$BACKUP_DIR/sqlbot-adapter"
  cp -a "$DATA_DIR/sqlbot-adapter/package-state.yaml" "$BACKUP_DIR/sqlbot-adapter/" 2>/dev/null || true
fi

rollback() {
  echo "ERROR: update failed — restoring plugin from $BACKUP_DIR" >&2
  if [[ -d "$BACKUP_DIR/plugins/hermes-sqlbot-adapter" ]]; then
    rm -rf "$DATA_DIR/plugins/hermes-sqlbot-adapter"
    cp -a "$BACKUP_DIR/plugins/hermes-sqlbot-adapter" "$DATA_DIR/plugins/" || true
  fi
  echo "Hint: SQLite backup at $BACKUP_DIR/sqlbot-adapter/state (sessions preserved if restore needed)" >&2
  exit 1
}

bash "$PACKAGE_ROOT/bin/install.sh" \
  --profile "$PROFILE" \
  --instance-dir "$INSTANCE_DIR" \
  --data-dir "$DATA_DIR" \
  --repo-root "$REPO_ROOT" \
  || rollback

# Schema migration is idempotent via init_state (called by install.sh)
echo "OK: update complete (schema_version=2, sessions preserved)"
echo "Next: bash scripts/up-instance.sh $PROFILE  # to run post-start / refresh deps"
echo "Rollback: restore plugin from $BACKUP_DIR/plugins/hermes-sqlbot-adapter if needed"
exit 0
