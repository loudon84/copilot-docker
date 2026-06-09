#!/usr/bin/env bash
# 构建 hermes-webui-expert 镜像并推送到本地 HTTP Registry
#
# 采用 --load 构建到本地 daemon，再 docker push，避免 buildx --push 与 insecure registry 不兼容。
#
# 快速开始：
#   cp local-registry.env.example local-registry.env
#   bash scripts/start-local-registry.sh
#   sudo bash scripts/configure-insecure-registry.sh
#   bash scripts/build-push-local-registry.sh
#
# 选项：
#   --dry-run   只打印命令，不执行
#   --no-push   仅构建到本地，不推送
#   --tag TAG   覆盖 IMAGE_TAG

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

DRY_RUN=0
NO_PUSH=0
TAG_OVERRIDE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --no-push) NO_PUSH=1 ;;
    --tag)
      shift
      TAG_OVERRIDE="${1:?--tag requires a value}"
      ;;
    -h|--help)
      sed -n '2,16p' "$0"
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
  echo "[config] loaded $LOCAL_REGISTRY_ENV"
else
  echo "ERROR: 请复制 local-registry.env.example 为 local-registry.env 并编辑" >&2
  exit 1
fi

LOCAL_REGISTRY_HOST="${LOCAL_REGISTRY_HOST:-192.168.102.247}"
LOCAL_REGISTRY_PORT="${LOCAL_REGISTRY_PORT:-9900}"
REGISTRY_URL="http://${LOCAL_REGISTRY_HOST}:${LOCAL_REGISTRY_PORT}"

IMAGE_REPO="${IMAGE_REPO:-}"
IMAGE_TAG="${TAG_OVERRIDE:-${IMAGE_TAG:-v$(date +%Y.%m.%d)}}"
HERMES_WEBUI_REPO="${HERMES_WEBUI_REPO:-http://git.superic.com/aiplatform/hermes-webui.git}"
HERMES_WEBUI_REF="${HERMES_WEBUI_REF:-master}"
HERMES_AGENT_REPO="${HERMES_AGENT_REPO:-http://git.superic.com/aiplatform/hermes-agent.git}"
HERMES_AGENT_REF="${HERMES_AGENT_REF:-master}"
INSTALL_GBRAIN="${INSTALL_GBRAIN:-1}"
GBRAIN_REPO="${GBRAIN_REPO:-http://git.superic.com/aiplatform/gbrain.git}"
INSTALL_FILESYSTEM_MCP="${INSTALL_FILESYSTEM_MCP:-1}"
INSTALL_CLAWSEC="${INSTALL_CLAWSEC:-0}"
CLAWSEC_REPO="${CLAWSEC_REPO:-http://git.superic.com/aiplatform/clawsec.git}"
BUILD_PLATFORM="${BUILD_PLATFORM:-linux/amd64}"

if [ -z "$IMAGE_REPO" ]; then
  echo "ERROR: 请设置 IMAGE_REPO（local-registry.env）" >&2
  exit 1
fi

FULL_IMAGE="${IMAGE_REPO}:${IMAGE_TAG}"
REPO_NAME="${IMAGE_REPO#*/}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker 未安装" >&2
  exit 1
fi

BUILD_ARGS=(
  --build-arg "HERMES_WEBUI_REPO=${HERMES_WEBUI_REPO}"
  --build-arg "HERMES_WEBUI_REF=${HERMES_WEBUI_REF}"
  --build-arg "HERMES_AGENT_REPO=${HERMES_AGENT_REPO}"
  --build-arg "HERMES_AGENT_REF=${HERMES_AGENT_REF}"
  --build-arg "HERMES_VERSION=${IMAGE_TAG}"
  --build-arg "INSTALL_GBRAIN=${INSTALL_GBRAIN}"
  --build-arg "GBRAIN_REPO=${GBRAIN_REPO}"
  --build-arg "INSTALL_FILESYSTEM_MCP=${INSTALL_FILESYSTEM_MCP}"
  --build-arg "INSTALL_CLAWSEC=${INSTALL_CLAWSEC}"
  --build-arg "CLAWSEC_REPO=${CLAWSEC_REPO}"
)

USE_BUILDX=0
if docker buildx version >/dev/null 2>&1; then
  USE_BUILDX=1
else
  echo "[warn] docker buildx 不可用，回退到 docker build" >&2
  echo "       如需跨平台构建，请安装: sudo apt-get install -y docker-buildx-plugin" >&2
  if [ "$BUILD_PLATFORM" != "linux/amd64" ] && [ "$(uname -m)" != "x86_64" ]; then
    echo "ERROR: 当前平台 $(uname -m) 且 BUILD_PLATFORM=${BUILD_PLATFORM}，必须安装 docker-buildx-plugin" >&2
    exit 1
  fi
fi

echo "[check] registry 可访问性: ${REGISTRY_URL}/v2/_catalog"
if [ "$DRY_RUN" = "0" ]; then
  if ! curl -fsS "${REGISTRY_URL}/v2/_catalog" >/dev/null 2>&1; then
    echo "ERROR: 无法访问 ${REGISTRY_URL}，请先执行 bash scripts/start-local-registry.sh" >&2
    exit 1
  fi
  echo "[pass] registry 可达"
fi

if [ "$USE_BUILDX" = "1" ]; then
  BUILDER_NAME="${BUILDX_BUILDER:-hermes-local-registry-builder}"
  if ! docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
    echo "[buildx] create builder: $BUILDER_NAME"
    if [ "$DRY_RUN" = "0" ]; then
      docker buildx create --name "$BUILDER_NAME" --use
    fi
  else
    if [ "$DRY_RUN" = "0" ]; then
      docker buildx use "$BUILDER_NAME"
    fi
  fi

  BUILD_CMD=(
    docker buildx build
    --platform "$BUILD_PLATFORM"
    -t "$FULL_IMAGE"
    "${BUILD_ARGS[@]}"
    --load
    .
  )
  echo "[build] ${FULL_IMAGE} (buildx --load)"
else
  BUILD_CMD=(
    docker build
    -t "$FULL_IMAGE"
    "${BUILD_ARGS[@]}"
    .
  )
  echo "[build] ${FULL_IMAGE} (docker build)"
fi
printf '  '; printf '%q ' "${BUILD_CMD[@]}"; echo

if [ "$DRY_RUN" = "1" ]; then
  echo
  echo "[dry-run] 将执行: docker push ${FULL_IMAGE}"
  exit 0
fi

"${BUILD_CMD[@]}"

if [ "$NO_PUSH" = "1" ]; then
  echo
  echo "[skip] --no-push: 镜像已加载到本地，未推送"
  echo "  docker images ${IMAGE_REPO}"
  exit 0
fi

echo
echo "[push] ${FULL_IMAGE}"
docker push "$FULL_IMAGE"

echo
echo "[verify] tags list"
TAGS_JSON=$(curl -fsS "${REGISTRY_URL}/v2/${REPO_NAME}/tags/list")
echo "$TAGS_JSON"

if ! echo "$TAGS_JSON" | grep -q "\"${IMAGE_TAG}\""; then
  echo "WARN: tag ${IMAGE_TAG} 未在 registry 中找到，请检查推送结果" >&2
fi

echo
echo "========================================"
echo "镜像已推送到本地 Registry"
echo "========================================"
echo
echo "  镜像: ${FULL_IMAGE}"
echo "  验证: curl ${REGISTRY_URL}/v2/${REPO_NAME}/tags/list"
echo
echo "nodeskclaw 配置："
echo
echo "1. 组织设置 → 镜像仓库 → Hermes 专家服务"
echo "   ${IMAGE_REPO}"
echo "   用户名、密码留空（本地 registry 无需认证）"
echo
echo "2. 组织设置 → 引擎版本 → Hermes 专家服务 → 发布新版本"
echo "   ${IMAGE_TAG}"
echo
echo "3. 部署时 nodeskclaw 将拉取："
echo "   ${FULL_IMAGE}"
echo
echo "4. 完整验证："
echo "   bash scripts/doctor-local-registry.sh"
echo
