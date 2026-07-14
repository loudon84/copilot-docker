#!/usr/bin/env bash
# 将 memory / mcp_servers / gbrain / curator / security / terminal 合并进 config.yaml
# 保留已有 model、providers 等配置，仅补齐或更新 runtime 段。
#
# 用法：
#   bash scripts/patch-config-runtime.sh <profile>
#   bash scripts/patch-config-runtime.sh <profile> --profile-home /data/hermes/profiles/x ...
#   bash scripts/patch-config-runtime.sh common-writer

set -euo pipefail

PROFILE="${1:?usage: patch-config-runtime.sh <profile> [--profile-home ...] }"
shift || true

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$BASE_DIR/instances/$PROFILE/.env"
PATCH_PY="$BASE_DIR/scripts/lib/patch_config_runtime.py"

PROFILE_HOME="/data/hermes"
WORKSPACE_PATH=""
VAULT_PATH=""
GBRAIN_HOME=""
HINDSIGHT_BANK_ID_OVERRIDE=""
KANBAN_DISPATCHER="omit"
ENABLE_DELEGATION="0"
CONFIG_FILE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --profile-home)
      PROFILE_HOME="${2:?}"
      shift 2
      ;;
    --workspace-path)
      WORKSPACE_PATH="${2:?}"
      shift 2
      ;;
    --vault-path)
      VAULT_PATH="${2:?}"
      shift 2
      ;;
    --gbrain-home)
      GBRAIN_HOME="${2:?}"
      shift 2
      ;;
    --hindsight-bank-id)
      HINDSIGHT_BANK_ID_OVERRIDE="${2:?}"
      shift 2
      ;;
    --kanban-dispatcher)
      KANBAN_DISPATCHER="${2:?}"
      shift 2
      ;;
    --enable-kanban-dispatcher)
      # Backward-compatible alias: 1→on, 0→off
      if [ "${2:?}" = "1" ] || [ "$2" = "true" ]; then
        KANBAN_DISPATCHER="on"
      else
        KANBAN_DISPATCHER="off"
      fi
      shift 2
      ;;
    --enable-delegation)
      ENABLE_DELEGATION="${2:?}"
      shift 2
      ;;
    --config)
      CONFIG_FILE="${2:?}"
      shift 2
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: missing env file: $ENV_FILE" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

HINDSIGHT_API_URL="${HINDSIGHT_API_URL:-http://hindsight.superic.com:8888}"
HINDSIGHT_BANK_ID="${HINDSIGHT_BANK_ID_OVERRIDE:-${HINDSIGHT_BANK_ID:-hermes-$PROFILE}}"
GBRAIN_ENABLED="${GBRAIN_ENABLED:-1}"
GBRAIN_COMMAND="${GBRAIN_COMMAND:-/usr/local/bin/gbrain}"

if [ -z "$CONFIG_FILE" ]; then
  if [ "$PROFILE_HOME" = "/data/hermes" ]; then
    CONFIG_FILE="$BASE_DIR/instances/$PROFILE/data/hermes/config.yaml"
  else
    # Map container profile home to host instance path when under /data/hermes/...
    REL="${PROFILE_HOME#/data/hermes}"
    REL="${REL#/}"
    if [ -n "$REL" ]; then
      CONFIG_FILE="$BASE_DIR/instances/$PROFILE/data/hermes/$REL/config.yaml"
    else
      CONFIG_FILE="$BASE_DIR/instances/$PROFILE/data/hermes/config.yaml"
    fi
  fi
fi

mkdir -p "$(dirname "$CONFIG_FILE")"
if [ ! -f "$CONFIG_FILE" ]; then
  cp "$BASE_DIR/expert-templates/base/config.yaml" "$CONFIG_FILE"
  sed -i "s|__PROFILE__|$PROFILE|g; s|__EXPERT__|${HERMES_EXPERT:-base}|g; s|__HINDSIGHT_API_URL__|$HINDSIGHT_API_URL|g" "$CONFIG_FILE"
fi

EXTRA_ARGS=()
if [ -n "$WORKSPACE_PATH" ]; then
  EXTRA_ARGS+=(--workspace-path "$WORKSPACE_PATH")
fi
if [ -n "$VAULT_PATH" ]; then
  EXTRA_ARGS+=(--vault-path "$VAULT_PATH")
fi
if [ -n "$GBRAIN_HOME" ]; then
  EXTRA_ARGS+=(--gbrain-home "$GBRAIN_HOME")
fi

PYTHON=python3
command -v python3 >/dev/null 2>&1 || PYTHON=python

"$PYTHON" "$PATCH_PY" \
  --config "$CONFIG_FILE" \
  --profile "$PROFILE" \
  --hindsight-api-url "$HINDSIGHT_API_URL" \
  --hindsight-bank-id "$HINDSIGHT_BANK_ID" \
  --gbrain-enabled "$GBRAIN_ENABLED" \
  --gbrain-command "$GBRAIN_COMMAND" \
  --profile-home "$PROFILE_HOME" \
  --kanban-dispatcher "$KANBAN_DISPATCHER" \
  --enable-delegation "$ENABLE_DELEGATION" \
  "${EXTRA_ARGS[@]}"
