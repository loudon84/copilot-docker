#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:?usage: up-instance.sh <profile> [--build] [--no-cache]}"
shift || true

BUILD_FLAG=0
NO_CACHE_FLAG=0

while [ $# -gt 0 ]; do
  case "$1" in
    --build) BUILD_FLAG=1 ;;
    --no-cache) NO_CACHE_FLAG=1 ;;
    -h|--help)
      echo "usage: up-instance.sh <profile> [--build] [--no-cache]"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
  shift
done

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$BASE_DIR/instances/$PROFILE/.env"
[ -f "$ENV_FILE" ] || { echo "ERROR: missing env file: $ENV_FILE"; exit 1; }
cd "$BASE_DIR"

DATA_DIR="$BASE_DIR/instances/$PROFILE/data/hermes"
mkdir -p \
  "$DATA_DIR/tools" \
  "$DATA_DIR/plugins" \
  "$DATA_DIR/skills" \
  "$DATA_DIR/skill-inbox" \
  "$DATA_DIR/mcp" \
  "$DATA_DIR/policies" \
  "$DATA_DIR/skill-bundles" \
  "$DATA_DIR/gbrain"
rm -f "$DATA_DIR/tools/tools" 2>/dev/null || true
rm -f "$DATA_DIR/plugins/plugins" 2>/dev/null || true
chown -R 1000:1000 "$DATA_DIR/tools" "$DATA_DIR/plugins" "$DATA_DIR/skills" "$DATA_DIR/skill-inbox" 2>/dev/null || true
chmod -R u+rwX,g+rwX "$DATA_DIR/tools" "$DATA_DIR/plugins" "$DATA_DIR/skills" "$DATA_DIR/skill-inbox" 2>/dev/null || true

LOCAL_IMAGE=$(grep '^LOCAL_IMAGE_NAME=' "$ENV_FILE" | cut -d= -f2-)
LOCAL_IMAGE="${LOCAL_IMAGE:-hermes-agent-webui:latest}"

BUILD_ARGS=(--progress=plain)
if [ "$NO_CACHE_FLAG" = "1" ]; then
  BUILD_ARGS+=(--no-cache)
fi

if [ "$NO_CACHE_FLAG" = "1" ]; then
  echo "[build] 无缓存重建镜像: $LOCAL_IMAGE"
  docker compose --env-file "$ENV_FILE" -p "hermes-$PROFILE" build "${BUILD_ARGS[@]}"
elif [ "$BUILD_FLAG" = "1" ]; then
  echo "[build] 强制重建镜像: $LOCAL_IMAGE"
  docker compose --env-file "$ENV_FILE" -p "hermes-$PROFILE" build "${BUILD_ARGS[@]}"
elif ! docker image inspect "$LOCAL_IMAGE" >/dev/null 2>&1; then
  echo "[build] 镜像 $LOCAL_IMAGE 不存在，首次构建..."
  echo "        提示: 多实例部署可先 bash scripts/build-image.sh 构建一次，后续实例无需重复 build"
  docker compose --env-file "$ENV_FILE" -p "hermes-$PROFILE" build --progress=plain
else
  echo "[skip] 复用已有镜像: $LOCAL_IMAGE"
  echo "       提示：如果 Dockerfile 已修改，请执行："
  echo "         bash scripts/up-instance.sh $PROFILE --no-cache"
  echo "       提示：如果只需要让当前实例使用最新 image，请执行："
  echo "         docker compose --env-file instances/$PROFILE/.env -p hermes-$PROFILE up -d --no-build --force-recreate"
fi

docker compose --env-file "$ENV_FILE" -p "hermes-$PROFILE" up -d --no-build

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
GATEWAY_PORT="$(grep '^HERMES_GATEWAY_PORT=' "$ENV_FILE" | cut -d= -f2-)"
if [ -z "$GATEWAY_PORT" ]; then
  BASE_PORT="$(grep '^HERMES_BASE_PORT=' "$ENV_FILE" | cut -d= -f2-)"
  WEBUI_PORT="$(grep '^HERMES_WEBUI_PORT=' "$ENV_FILE" | cut -d= -f2-)"
  BASE_PORT="${BASE_PORT:-20000}"
  WEBUI_PORT="${WEBUI_PORT:-8787}"
  GATEWAY_PORT=$((BASE_PORT + WEBUI_PORT))
fi
echo "Gateway: http://<server-ip>:${GATEWAY_PORT} (nodeskclaw / 外部 Agent 接入)"
echo "Password: $(grep '^HERMES_WEBUI_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
