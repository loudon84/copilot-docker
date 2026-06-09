#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:?usage: up-instance.sh <profile> [--build]}"
BUILD_FLAG="${2:-}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$BASE_DIR/instances/$PROFILE/.env"
[ -f "$ENV_FILE" ] || { echo "ERROR: missing env file: $ENV_FILE"; exit 1; }
cd "$BASE_DIR"

DATA_DIR="$BASE_DIR/instances/$PROFILE/data/hermes"
mkdir -p \
  "$DATA_DIR/tools" \
  "$DATA_DIR/plugins" \
  "$DATA_DIR/skills" \
  "$DATA_DIR/mcp" \
  "$DATA_DIR/policies" \
  "$DATA_DIR/skill-bundles" \
  "$DATA_DIR/gbrain"
rm -f "$DATA_DIR/tools/tools" 2>/dev/null || true
rm -f "$DATA_DIR/plugins/plugins" 2>/dev/null || true
chown -R 1000:1000 "$DATA_DIR/tools" "$DATA_DIR/plugins" "$DATA_DIR/skills" 2>/dev/null || true
chmod -R u+rwX,g+rwX "$DATA_DIR/tools" "$DATA_DIR/plugins" "$DATA_DIR/skills" 2>/dev/null || true

LOCAL_IMAGE=$(grep '^LOCAL_IMAGE_NAME=' "$ENV_FILE" | cut -d= -f2-)
LOCAL_IMAGE="${LOCAL_IMAGE:-hermes-agent-webui:latest}"

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

sleep 3
STATE=$(docker inspect --format '{{.State.Status}}' "hermes-$PROFILE" 2>/dev/null || echo "unknown")
if [ "$STATE" = "restarting" ]; then
  echo "ERROR: container is restarting"
  docker logs --tail=80 "hermes-$PROFILE"
  exit 1
fi

docker inspect "hermes-$PROFILE" >/dev/null 2>&1
docker logs --tail=80 "hermes-$PROFILE" >/dev/null 2>&1 || true

echo "OK: started hermes-$PROFILE"
echo "WebUI: http://<server-ip>:$(grep '^HERMES_WEBUI_PORT=' "$ENV_FILE" | cut -d= -f2-)"
echo "Password: $(grep '^HERMES_WEBUI_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
