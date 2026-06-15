#!/usr/bin/env bash
# 将 memory / mcp_servers / gbrain / curator / security / terminal 合并进 config.yaml
# 保留已有 model、providers 等配置，仅补齐或更新 runtime 段。
#
# 用法：
#   bash scripts/patch-config-runtime.sh <profile>
#   bash scripts/patch-config-runtime.sh common-writer

set -euo pipefail

PROFILE="${1:?usage: patch-config-runtime.sh <profile>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$BASE_DIR/instances/$PROFILE/.env"
CONFIG_FILE="$BASE_DIR/instances/$PROFILE/data/hermes/config.yaml"
PATCH_PY="$BASE_DIR/scripts/lib/patch_config_runtime.py"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: missing env file: $ENV_FILE" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

HINDSIGHT_API_URL="${HINDSIGHT_API_URL:-http://hindsight.superic.com:8888}"
HINDSIGHT_BANK_ID="${HINDSIGHT_BANK_ID:-hermes-$PROFILE}"
GBRAIN_ENABLED="${GBRAIN_ENABLED:-1}"
GBRAIN_COMMAND="${GBRAIN_COMMAND:-/usr/local/bin/gbrain}"

mkdir -p "$(dirname "$CONFIG_FILE")"
if [ ! -f "$CONFIG_FILE" ]; then
  cp "$BASE_DIR/expert-templates/base/config.yaml" "$CONFIG_FILE"
  sed -i "s|__PROFILE__|$PROFILE|g; s|__EXPERT__|${HERMES_EXPERT:-base}|g; s|__HINDSIGHT_API_URL__|$HINDSIGHT_API_URL|g" "$CONFIG_FILE"
fi

python3 "$PATCH_PY" \
  --config "$CONFIG_FILE" \
  --profile "$PROFILE" \
  --hindsight-api-url "$HINDSIGHT_API_URL" \
  --hindsight-bank-id "$HINDSIGHT_BANK_ID" \
  --gbrain-enabled "$GBRAIN_ENABLED" \
  --gbrain-command "$GBRAIN_COMMAND"
