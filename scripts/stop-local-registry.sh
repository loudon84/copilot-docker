#!/usr/bin/env bash
# 停止并删除本地 Docker Registry 容器
#
# 用法：
#   bash scripts/stop-local-registry.sh
#   bash scripts/stop-local-registry.sh --remove-data

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

REMOVE_DATA=0

while [ $# -gt 0 ]; do
  case "$1" in
    --remove-data) REMOVE_DATA=1 ;;
    -h|--help)
      echo "用法: bash scripts/stop-local-registry.sh [--remove-data]"
      echo "  --remove-data  同时删除 registry 数据目录"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
  shift
done

LOCAL_REGISTRY_ENV="$BASE_DIR/local-registry.env"
if [ -f "$LOCAL_REGISTRY_ENV" ]; then
  # shellcheck disable=SC1090
  set -a
  source "$LOCAL_REGISTRY_ENV"
  set +a
fi

LOCAL_REGISTRY_CONTAINER_NAME="${LOCAL_REGISTRY_CONTAINER_NAME:-local-registry}"
LOCAL_REGISTRY_DATA_DIR="${LOCAL_REGISTRY_DATA_DIR:-/data/docker-registry}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker 未安装" >&2
  exit 1
fi

if ! docker ps -a --format '{{.Names}}' | grep -qx "$LOCAL_REGISTRY_CONTAINER_NAME"; then
  echo "[skip] 容器 $LOCAL_REGISTRY_CONTAINER_NAME 不存在"
else
  echo "[stop] 停止并删除容器: $LOCAL_REGISTRY_CONTAINER_NAME"
  docker stop "$LOCAL_REGISTRY_CONTAINER_NAME" 2>/dev/null || true
  docker rm "$LOCAL_REGISTRY_CONTAINER_NAME"
  echo "[ok] 容器已删除"
fi

if [ "$REMOVE_DATA" = "1" ]; then
  echo "[remove] 删除数据目录: $LOCAL_REGISTRY_DATA_DIR"
  sudo rm -rf "$LOCAL_REGISTRY_DATA_DIR"
  echo "[ok] 数据目录已删除"
else
  echo "[keep] 保留数据目录: $LOCAL_REGISTRY_DATA_DIR"
  echo "       如需删除，执行: bash scripts/stop-local-registry.sh --remove-data"
fi
