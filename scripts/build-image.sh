#!/usr/bin/env bash
# 构建全实例共享的 Hermes 镜像（只需执行一次，多个 instance 复用同一镜像）
#
# 用法：
#   bash scripts/build-image.sh                 # 使用 .env.example 中的构建参数
#   bash scripts/build-image.sh --default       # 同上（显式使用默认 env）
#   bash scripts/build-image.sh writer          # 借用 instances/writer/.env 中的构建参数
#   bash scripts/build-image.sh writer --no-cache
#   bash scripts/build-image.sh writer --pull
#   bash scripts/build-image.sh writer --pull --no-cache
#
# 说明：
#   所有 instance 的 LOCAL_IMAGE_NAME 默认为 hermes-agent-webui:latest。
#   首次 build 后，后续 create-instance + up-instance 无需再 docker compose build。

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

test -f "$BASE_DIR/.dockerignore" || { echo "ERROR: .dockerignore missing" >&2; exit 1; }
grep -q '^instances/$' "$BASE_DIR/.dockerignore" || { echo "ERROR: .dockerignore must exclude instances/" >&2; exit 1; }

NO_CACHE=0
PULL=0
PROFILE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --no-cache) NO_CACHE=1 ;;
    --pull) PULL=1 ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *)
      if [ -z "$PROFILE" ]; then
        PROFILE="$1"
      else
        echo "[build-image] ERROR: unknown arg: $1" >&2
        exit 1
      fi
      ;;
  esac
  shift
done

if [ -f "$BASE_DIR/.env" ]; then
  ENV_FILE="$BASE_DIR/.env"
elif [ -f "$BASE_DIR/.env.example" ]; then
  ENV_FILE="$BASE_DIR/.env.example"
else
  echo "[build-image] ERROR: 找不到 .env 或 .env.example" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

LOCAL_IMAGE="${LOCAL_IMAGE_NAME:-hermes-agent-webui:latest}"

echo "[build-image] PROFILE=${PROFILE:-<default>}"
echo "[build-image] ENV_FILE=${ENV_FILE}"
echo "[build-image] LOCAL_IMAGE_NAME=${LOCAL_IMAGE}"
echo "[build-image] PYTHON_BASE_IMAGE=${PYTHON_BASE_IMAGE:-python:3.12-slim-bookworm}"
echo "[build-image] USE_CN_MIRRORS=${USE_CN_MIRRORS:-1}"
echo "[build-image] APT_MIRROR=${APT_MIRROR:-https://mirrors.aliyun.com/debian}"
echo "[build-image] PIP_INDEX_URL=${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
echo "[build-image] NPM_REGISTRY=${NPM_REGISTRY:-https://registry.npmmirror.com}"
echo "[build-image] BUILD_APT_PROXY=${BUILD_APT_PROXY:-}"
echo

BUILD_ARGS=(--progress=plain)
if [ "$NO_CACHE" = "1" ]; then
  BUILD_ARGS+=(--no-cache)
fi
if [ "$PULL" = "1" ]; then
  BUILD_ARGS+=(--pull)
fi

docker compose --env-file "$ENV_FILE" -p hermes-build build "${BUILD_ARGS[@]}"

echo
echo "== image doctor =="
bash "$BASE_DIR/scripts/doctor-image.sh" "$LOCAL_IMAGE"

echo
echo "OK: 镜像已就绪 → $LOCAL_IMAGE"
echo "验证镜像源: docker run --rm $LOCAL_IMAGE /usr/local/bin/verify-mirrors.sh"
echo "后续实例: bash scripts/create-instance.sh <profile> <port> <expert>"
echo "          bash scripts/up-instance.sh <profile>"
echo "镜像更新后批量重建容器: bash scripts/recreate-all-instances.sh"
