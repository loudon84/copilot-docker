#!/usr/bin/env bash
# 启动本地 Docker Registry（registry:2，宿主机端口 → 容器 5000）
#
# 快速开始：
#   cp local-registry.env.example local-registry.env
#   bash scripts/start-local-registry.sh

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

LOCAL_REGISTRY_ENV="$BASE_DIR/local-registry.env"
if [ -f "$LOCAL_REGISTRY_ENV" ]; then
  # shellcheck disable=SC1090
  set -a
  source "$LOCAL_REGISTRY_ENV"
  set +a
  echo "[config] loaded $LOCAL_REGISTRY_ENV"
else
  echo "WARN: $LOCAL_REGISTRY_ENV 不存在，使用默认值（建议 cp local-registry.env.example local-registry.env）" >&2
fi

LOCAL_REGISTRY_HOST="${LOCAL_REGISTRY_HOST:-192.168.102.247}"
LOCAL_REGISTRY_PORT="${LOCAL_REGISTRY_PORT:-9900}"
LOCAL_REGISTRY_CONTAINER_NAME="${LOCAL_REGISTRY_CONTAINER_NAME:-local-registry}"
LOCAL_REGISTRY_DATA_DIR="${LOCAL_REGISTRY_DATA_DIR:-/data/docker-registry}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker 未安装" >&2
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -qx "$LOCAL_REGISTRY_CONTAINER_NAME"; then
  if docker ps --format '{{.Names}}' | grep -qx "$LOCAL_REGISTRY_CONTAINER_NAME"; then
    echo "[status] 容器 $LOCAL_REGISTRY_CONTAINER_NAME 已在运行"
    docker ps --filter "name=^${LOCAL_REGISTRY_CONTAINER_NAME}$" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
    echo
    echo "Registry URL: http://${LOCAL_REGISTRY_HOST}:${LOCAL_REGISTRY_PORT}"
    echo "验证: curl http://${LOCAL_REGISTRY_HOST}:${LOCAL_REGISTRY_PORT}/v2/_catalog"
    exit 0
  fi
  echo "[status] 容器 $LOCAL_REGISTRY_CONTAINER_NAME 已存在但未运行，正在启动..."
  docker start "$LOCAL_REGISTRY_CONTAINER_NAME"
  echo "[ok] 已启动 $LOCAL_REGISTRY_CONTAINER_NAME"
  echo "Registry URL: http://${LOCAL_REGISTRY_HOST}:${LOCAL_REGISTRY_PORT}"
  exit 0
fi

echo "[setup] 创建数据目录: $LOCAL_REGISTRY_DATA_DIR"
sudo mkdir -p "$LOCAL_REGISTRY_DATA_DIR"

echo "[start] 启动 registry:2 → ${LOCAL_REGISTRY_HOST}:${LOCAL_REGISTRY_PORT} (容器内 5000)"
docker run -d \
  --name "$LOCAL_REGISTRY_CONTAINER_NAME" \
  --restart=always \
  -p "${LOCAL_REGISTRY_PORT}:5000" \
  -v "${LOCAL_REGISTRY_DATA_DIR}:/var/lib/registry" \
  registry:2

echo
echo "========================================"
echo "本地 Registry 已启动"
echo "========================================"
echo
echo "  URL:    http://${LOCAL_REGISTRY_HOST}:${LOCAL_REGISTRY_PORT}"
echo "  容器:   $LOCAL_REGISTRY_CONTAINER_NAME"
echo "  数据:   $LOCAL_REGISTRY_DATA_DIR"
echo
echo "说明: registry:2 默认监听容器内 5000 端口，宿主机使用 ${LOCAL_REGISTRY_PORT} 需 -p ${LOCAL_REGISTRY_PORT}:5000"
echo
echo "下一步:"
echo "  1. sudo bash scripts/configure-insecure-registry.sh"
echo "  2. bash scripts/build-push-local-registry.sh"
echo "  3. bash scripts/doctor-local-registry.sh"
echo
