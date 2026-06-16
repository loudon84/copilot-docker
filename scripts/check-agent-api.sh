#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:?usage: check-agent-api.sh <profile>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$BASE_DIR/instances/$PROFILE/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

PORT="${HERMES_GATEWAY_PORT:?HERMES_GATEWAY_PORT missing}"
KEY="${API_SERVER_KEY:?API_SERVER_KEY missing}"
BASE_URL="http://127.0.0.1:${PORT}"

echo "[check-agent-api] profile=$PROFILE"
echo "[check-agent-api] base_url=$BASE_URL"

echo "== health =="
curl -fsS "$BASE_URL/health"
echo

echo "== models =="
curl -fsS "$BASE_URL/v1/models" \
  -H "Authorization: Bearer $KEY"
echo

echo "== capabilities =="
curl -fsS "$BASE_URL/v1/capabilities" \
  -H "Authorization: Bearer $KEY"
echo

echo "== skills =="
curl -fsS "$BASE_URL/v1/skills" \
  -H "Authorization: Bearer $KEY"
echo

echo "[check-agent-api] OK"
