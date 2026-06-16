#!/usr/bin/env bash
# 为已有实例 .env 补齐 API Server 配置（不覆盖已有 API_SERVER_KEY / WebUI 密码）
set -euo pipefail

PROFILE="${1:?usage: migrate-instance-env.sh <profile>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$BASE_DIR/instances/$PROFILE/.env"
INSTANCE_DIR="$BASE_DIR/instances/$PROFILE"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 1
fi

append_if_missing() {
  local key="$1"
  local value="$2"
  if ! grep -q "^${key}=" "$ENV_FILE"; then
    echo "${key}=${value}" >> "$ENV_FILE"
    echo "[migrate] appended ${key}"
  fi
}

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

WEBUI_PORT="${HERMES_WEBUI_PORT:-8787}"
BASE_PORT="${HERMES_BASE_PORT:-20000}"
GATEWAY_PORT="${HERMES_GATEWAY_PORT:-$((BASE_PORT + WEBUI_PORT))}"

append_if_missing "HERMES_GATEWAY_BIND" "0.0.0.0"
append_if_missing "HERMES_GATEWAY_PORT" "$GATEWAY_PORT"
append_if_missing "API_SERVER_ENABLED" "true"
append_if_missing "API_SERVER_HOST" "0.0.0.0"
append_if_missing "API_SERVER_PORT" "8642"
append_if_missing "API_SERVER_MODEL_NAME" "${HERMES_PROFILE:-$PROFILE}"
append_if_missing "API_SERVER_CORS_ORIGINS" ""
append_if_missing "GATEWAY_ALLOW_ALL_USERS" "true"

if ! grep -q '^API_SERVER_KEY=' "$ENV_FILE"; then
  API_KEY="$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-40)"
  echo "API_SERVER_KEY=${API_KEY}" >> "$ENV_FILE"
  echo "[migrate] appended API_SERVER_KEY (generated)"
fi

chmod 600 "$ENV_FILE" 2>/dev/null || true

# shellcheck disable=SC1090
. "$ENV_FILE"
GATEWAY_PORT="${HERMES_GATEWAY_PORT:-$GATEWAY_PORT}"
WEBUI_PORT="${HERMES_WEBUI_PORT:-8787}"

cat > "$INSTANCE_DIR/agent-api.json" <<EOF_JSON
{
  "profile": "${HERMES_PROFILE:-$PROFILE}",
  "base_url": "http://127.0.0.1:${GATEWAY_PORT}",
  "openai_base_url": "http://127.0.0.1:${GATEWAY_PORT}/v1",
  "health_url": "http://127.0.0.1:${GATEWAY_PORT}/health",
  "models_url": "http://127.0.0.1:${GATEWAY_PORT}/v1/models",
  "skills_url": "http://127.0.0.1:${GATEWAY_PORT}/v1/skills",
  "toolsets_url": "http://127.0.0.1:${GATEWAY_PORT}/v1/toolsets",
  "api_key_env": "API_SERVER_KEY",
  "container_name": "hermes-${HERMES_PROFILE:-$PROFILE}",
  "webui_url": "http://127.0.0.1:${WEBUI_PORT}"
}
EOF_JSON

echo "[migrate] OK: $ENV_FILE"
echo "[migrate] agent-api.json updated"

bash "$BASE_DIR/scripts/sync-runtime-env.sh" "$PROFILE"
