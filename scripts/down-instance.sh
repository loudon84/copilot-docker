#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:?usage: down-instance.sh <profile>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$BASE_DIR/instances/$PROFILE/.env"
[ -f "$ENV_FILE" ] || { echo "ERROR: missing env file: $ENV_FILE"; exit 1; }
cd "$BASE_DIR"
docker compose --env-file "$ENV_FILE" -p "hermes-$PROFILE" down
echo "OK: stopped hermes-$PROFILE"
