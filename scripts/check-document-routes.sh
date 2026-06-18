#!/usr/bin/env bash
# 检查实例文档路径路由是否符合 v1.6 规范
#
# 用法:
#   bash scripts/check-document-routes.sh writer
#   bash scripts/check-document-routes.sh --all
#   bash scripts/check-document-routes.sh writer --fix

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALIDATE_PY="$BASE_DIR/scripts/lib/validate_document_routes.py"
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
      sed -n '1,12p' "$0"
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

run_check() {
  local p="$1"
  local data_dir="$BASE_DIR/instances/$p/data/hermes"
  if [ ! -d "$data_dir" ]; then
    echo "SKIP: instance not found: $p ($data_dir)" >&2
    return 0
  fi
  local args=("$data_dir")
  if [ "$FIX" = "1" ]; then
    args+=(--fix)
  fi
  python3 "$VALIDATE_PY" "${args[@]}"
}

if [ "$ALL" = "1" ]; then
  exit_code=0
  found=0
  for inst in "$BASE_DIR/instances"/*; do
    [ -d "$inst" ] || continue
    p="$(basename "$inst")"
    [ -d "$inst/data/hermes" ] || continue
    found=1
    echo
    if ! run_check "$p"; then
      exit_code=1
    fi
  done
  if [ "$found" = "0" ]; then
    echo "No instances under $BASE_DIR/instances" >&2
    exit 1
  fi
  exit "$exit_code"
fi

if [ -z "$PROFILE" ]; then
  echo "ERROR: usage: check-document-routes.sh <profile> | --all [--fix]" >&2
  exit 1
fi

run_check "$PROFILE"
