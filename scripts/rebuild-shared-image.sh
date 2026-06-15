#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-common-writer}"
BUILD_FLAG="${2:---no-cache}"

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$BASE_DIR/instances/$PROFILE/.env"

[ -f "$ENV_FILE" ] || {
  echo "ERROR: missing env file: $ENV_FILE"
  exit 1
}

cd "$BASE_DIR"

IMAGE_NAME="$(grep '^LOCAL_IMAGE_NAME=' "$ENV_FILE" | cut -d= -f2-)"
IMAGE_NAME="${IMAGE_NAME:-hermes-agent-webui:latest}"

if [ "$BUILD_FLAG" = "--no-cache" ]; then
  docker compose --env-file "$ENV_FILE" \
    -p hermes-image-build \
    build --no-cache --pull --progress=plain
else
  docker compose --env-file "$ENV_FILE" \
    -p hermes-image-build \
    build --pull --progress=plain
fi

echo "== built image =="
docker image inspect "$IMAGE_NAME" \
  --format 'IMAGE={{.RepoTags}} ID={{.Id}} CREATED={{.Created}}'

bash "$BASE_DIR/scripts/doctor-image.sh" "$IMAGE_NAME"

echo "OK: shared image rebuilt and verified: $IMAGE_NAME"
