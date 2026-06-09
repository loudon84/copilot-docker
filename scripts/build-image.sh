#!/usr/bin/env bash
# 构建全实例共享的 Hermes 镜像（只需执行一次，多个 instance 复用同一镜像）
#
# 用法：
#   bash scripts/build-image.sh
#   bash scripts/build-image.sh writer          # 借用 instances/writer/.env 中的构建参数
#   bash scripts/build-image.sh --no-cache      # 强制无缓存重建
#
# 说明：
#   所有 instance 的 LOCAL_IMAGE_NAME 默认为 hermes-agent-webui:lastest。
#   首次 build 后，后续 create-instance + up-instance 无需再 docker compose build。

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

NO_CACHE=0
PROFILE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --no-cache) NO_CACHE=1 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      PROFILE="$1"
      ;;
  esac
  shift
done

if [ -n "$PROFILE" ] && [ -f "$BASE_DIR/instances/$PROFILE/.env" ]; then
  ENV_FILE="$BASE_DIR/instances/$PROFILE/.env"
elif [ -f "$BASE_DIR/instances/writer/.env" ]; then
  ENV_FILE="$BASE_DIR/instances/writer/.env"
elif [ -f "$BASE_DIR/.env.example" ]; then
  ENV_FILE="$BASE_DIR/.env.example"
else
  echo "ERROR: 找不到 .env 文件，请先 create-instance 或提供 .env.example" >&2
  exit 1
fi

LOCAL_IMAGE=$(grep '^LOCAL_IMAGE_NAME=' "$ENV_FILE" | cut -d= -f2-)
LOCAL_IMAGE="${LOCAL_IMAGE:-hermes-agent-webui:lastest}"

BUILD_ARGS=()
if [ "$NO_CACHE" = "1" ]; then
  BUILD_ARGS+=(--no-cache)
fi

echo "[build] 共享镜像: $LOCAL_IMAGE"
echo "[env]   $ENV_FILE"
echo "[hint]  构建完成后，所有 instance 共用此镜像，无需逐实例 build"
echo

docker compose --env-file "$ENV_FILE" -p hermes-build "${BUILD_ARGS[@]}" build

echo
echo "OK: 镜像已就绪 → $LOCAL_IMAGE"
echo "后续实例: bash scripts/create-instance.sh <profile> <port> <expert>"
echo "          bash scripts/up-instance.sh <profile>"
