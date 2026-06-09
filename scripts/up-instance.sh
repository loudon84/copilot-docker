#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:?usage: up-instance.sh <profile> [--build]}"
BUILD_FLAG="${2:-}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$BASE_DIR/instances/$PROFILE/.env"
[ -f "$ENV_FILE" ] || { echo "ERROR: missing env file: $ENV_FILE"; exit 1; }
cd "$BASE_DIR"

LOCAL_IMAGE=$(grep '^LOCAL_IMAGE_NAME=' "$ENV_FILE" | cut -d= -f2-)
LOCAL_IMAGE="${LOCAL_IMAGE:-hermes-agent-webui:self-evolution}"

if [ "$BUILD_FLAG" = "--build" ]; then
  echo "[build] 强制重建镜像: $LOCAL_IMAGE"
  docker compose --env-file "$ENV_FILE" -p "hermes-$PROFILE" build
elif ! docker image inspect "$LOCAL_IMAGE" >/dev/null 2>&1; then
  echo "[build] 镜像 $LOCAL_IMAGE 不存在，首次构建..."
  echo "        提示: 多实例部署可先 bash scripts/build-image.sh 构建一次，后续实例无需重复 build"
  docker compose --env-file "$ENV_FILE" -p "hermes-$PROFILE" build
else
  echo "[skip] 复用已有镜像: $LOCAL_IMAGE"
fi

docker compose --env-file "$ENV_FILE" -p "hermes-$PROFILE" up -d
echo "OK: started hermes-$PROFILE"
echo "WebUI: http://<server-ip>:$(grep '^HERMES_WEBUI_PORT=' "$ENV_FILE" | cut -d= -f2-)"
echo "Password: $(grep '^HERMES_WEBUI_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
