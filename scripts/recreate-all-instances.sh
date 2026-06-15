#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

for ENV_FILE in instances/*/.env; do
  PROFILE="$(basename "$(dirname "$ENV_FILE")")"

  echo "== recreate hermes-$PROFILE =="
  docker compose --env-file "$ENV_FILE" \
    -p "hermes-$PROFILE" \
    up -d --no-build --force-recreate
done

echo "== containers =="
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'