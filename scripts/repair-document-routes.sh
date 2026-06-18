#!/usr/bin/env bash
# 修复实例文档路径：补全目录、patch config、检查 SOUL、可选迁移 Obsidian 违规文件
#
# 用法:
#   bash scripts/repair-document-routes.sh writer
#   bash scripts/repair-document-routes.sh finance --fix
#   bash scripts/repair-document-routes.sh --all --fix

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/init_hermes_dirs.sh
source "$BASE_DIR/scripts/lib/init_hermes_dirs.sh"

FIX=0
ALL=0
PROFILE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --all)
      ALL=1
      ;;
    --fix)
      FIX=1
      ;;
    -h|--help)
      sed -n '1,10p' "$0"
      exit 0
      ;;
    -*)
      echo "ERROR: unknown option: $1" >&2
      exit 1
      ;;
    *)
      PROFILE="$1"
      ;;
  esac
  shift
done

repair_one() {
  local p="$1"
  local data_dir="$BASE_DIR/instances/$p/data/hermes"
  local instance_dir="$BASE_DIR/instances/$p"

  if [ ! -d "$instance_dir" ]; then
    echo "SKIP: instance not found: $p" >&2
    return 0
  fi

  echo "=== Repair document routes: $p ==="

  echo "[1/5] Init standard directories"
  init_hermes_dirs "$data_dir"

  echo "[2/5] Fix permissions"
  chown -R 1000:1000 "$data_dir" 2>/dev/null || true
  chmod -R u+rwX,g+rwX "$data_dir" 2>/dev/null || true

  echo "[3/5] Patch config.yaml (workspace MCP)"
  if [ -f "$instance_dir/.env" ]; then
    bash "$BASE_DIR/scripts/patch-config-runtime.sh" "$p" 2>/dev/null || true
  else
    echo "WARN: no .env for $p, skip patch-config-runtime"
  fi

  echo "[4/5] Re-inject base policies if template exists"
  TPL_BASE="$BASE_DIR/expert-templates/base"
  if [ -d "$TPL_BASE/policies" ]; then
    mkdir -p "$data_dir/policies"
    cp -f "$TPL_BASE/policies/document-routing.yaml" "$data_dir/policies/" 2>/dev/null || true
  fi
  if [ -f "$TPL_BASE/workspace/AGENTS.md" ]; then
    mkdir -p "$data_dir/workspace"
    cp -f "$TPL_BASE/workspace/AGENTS.md" "$data_dir/workspace/AGENTS.md" 2>/dev/null || true
  fi

  echo "[5/5] Validate routes"
  local check_args=("$p")
  if [ "$FIX" = "1" ]; then
    check_args+=(--fix)
  fi
  bash "$BASE_DIR/scripts/check-document-routes.sh" "${check_args[@]}" || true

  echo "Done: $p"
  echo
}

if [ "$ALL" = "1" ]; then
  found=0
  for inst in "$BASE_DIR/instances"/*; do
    [ -d "$inst" ] || continue
    p="$(basename "$inst")"
    [ -d "$inst/data/hermes" ] || continue
    found=1
    repair_one "$p"
  done
  if [ "$found" = "0" ]; then
    echo "No instances under $BASE_DIR/instances" >&2
    exit 1
  fi
  exit 0
fi

if [ -z "$PROFILE" ]; then
  echo "ERROR: usage: repair-document-routes.sh <profile> | --all [--fix]" >&2
  exit 1
fi

repair_one "$PROFILE"
