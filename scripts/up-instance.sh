#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:?usage: up-instance.sh <profile> [--build]}"
BUILD_FLAG="${2:-}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$BASE_DIR/instances/$PROFILE/.env"
[ -f "$ENV_FILE" ] || { echo "ERROR: missing env file: $ENV_FILE"; exit 1; }
cd "$BASE_DIR"
if [ "$BUILD_FLAG" = "--build" ]; then
  docker compose --env-file "$ENV_FILE" -p "hermes-$PROFILE" build
fi
docker compose --env-file "$ENV_FILE" -p "hermes-$PROFILE" up -d
echo "OK: started hermes-$PROFILE"
echo "WebUI: http://<server-ip>:$(grep '^HERMES_WEBUI_PORT=' "$ENV_FILE" | cut -d= -f2-)"
echo "Password: $(grep '^HERMES_WEBUI_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
