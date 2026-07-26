#!/usr/bin/env bash
# Update installed bi-strategic-office package assets (PRD v1.11).
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

echo "[update] package version=$NEW_VERSION"
if [[ -n "$PYTHON_BIN" ]]; then
  OLD="$("$PYTHON_BIN" "$PACKAGE_ROOT/lib/package_state.py" read --data-dir "$DATA_DIR" 2>/dev/null || true)"
  echo "[update] current package-state:"
  echo "$OLD" | sed 's/^/  /' || true
fi

bash "$PACKAGE_ROOT/bin/install.sh" \
  --profile "$PROFILE" \
  --instance-dir "$INSTANCE_DIR" \
  --data-dir "$DATA_DIR" \
  --repo-root "$REPO_ROOT"

echo "OK: update complete"
echo "Next: bash scripts/up-instance.sh $PROFILE  # to run post-start / refresh deps"
exit 0
