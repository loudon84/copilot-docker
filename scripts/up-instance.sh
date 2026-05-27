#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:?usage: up-instance.sh <profile>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"
ENV_FILE="instances/$PROFILE/.env"
[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE. Run scripts/create-instance.sh first."; exit 1; }
docker compose --env-file "$ENV_FILE" -p "hermes-$PROFILE" build --pull
docker compose --env-file "$ENV_FILE" -p "hermes-$PROFILE" up -d
docker compose --env-file "$ENV_FILE" -p "hermes-$PROFILE" ps
