#!/usr/bin/env bash
set -euo pipefail

# Check verification container status, health endpoint, ports, and image commit.
# Usage:
#   bash scripts/check-verify-instance.sh verify-agent

PROFILE="${1:?usage: check-verify-instance.sh <verify_profile>}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
ENV_FILE="instances/${PROFILE}/.env"
CONTAINER="hermes-${PROFILE}"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 1
fi

WEBUI_PORT="$(grep -E '^HERMES_WEBUI_PORT=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"
GATEWAY_PORT="$(grep -E '^HERMES_GATEWAY_PORT=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"
IMAGE="$(grep -E '^LOCAL_IMAGE_NAME=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"

echo "[check] container: $CONTAINER"
docker ps --filter "name=^/${CONTAINER}$" --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'

echo "[check] expected image: $IMAGE"
docker inspect "$CONTAINER" --format 'container image id: {{.Image}}'
docker image inspect "$IMAGE" --format 'tag image id      : {{.Id}}'

echo "[check] hermes-agent commit:"
docker exec "$CONTAINER" bash -lc 'cd /opt/hermes-agent && git rev-parse HEAD && git log -1 --oneline'

echo "[check] health:"
curl -fsS "http://127.0.0.1:${WEBUI_PORT}/health" || true
printf '\n'

echo "[check] ports: WebUI=${WEBUI_PORT}, Gateway=${GATEWAY_PORT}"
