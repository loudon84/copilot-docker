#!/usr/bin/env bash
# 一键构建并推送 Hermes 专家服务镜像到火山引擎镜像仓库（供 nodeskclaw 拉取）
#
# 快速开始：
#   cp registry.env.example registry.env
#   # 编辑 registry.env：IMAGE_REPO、IMAGE_TAG、REGISTRY_HOST
#   bash scripts/build-push-registry.sh --login
#
# 或仅用环境变量：
#   export IMAGE_REPO="cr.volces.com/<namespace>/hermes-webui-expert"
#   export IMAGE_TAG="v2026.6.8"
#   bash scripts/build-push-registry.sh --login
#
# 选项：
#   --login     构建前执行 docker login（需已配置 REGISTRY_HOST 或从 IMAGE_REPO 解析）
#   --dry-run   只打印 docker buildx 命令，不执行
#   --no-push   构建到本地，不推送
#   --tag TAG   覆盖 IMAGE_TAG

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

DO_LOGIN=0
DRY_RUN=0
NO_PUSH=0
TAG_OVERRIDE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --login) DO_LOGIN=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --no-push) NO_PUSH=1 ;;
    --tag)
      shift
      TAG_OVERRIDE="${1:?--tag requires a value}"
      ;;
    -h|--help)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
  shift
done

REGISTRY_ENV="$BASE_DIR/registry.env"
if [ -f "$REGISTRY_ENV" ]; then
  # shellcheck disable=SC1090
  set -a
  source "$REGISTRY_ENV"
  set +a
  echo "[config] loaded $REGISTRY_ENV"
fi

IMAGE_REPO="${IMAGE_REPO:-}"
IMAGE_TAG="${TAG_OVERRIDE:-${IMAGE_TAG:-v$(date +%Y.%m.%d)}}"
REGISTRY_HOST="${REGISTRY_HOST:-}"
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

if [ -z "$IMAGE_REPO" ] || [[ "$IMAGE_REPO" == *"<"*">"* ]]; then
  echo "ERROR: 请设置 IMAGE_REPO（复制 registry.env.example 为 registry.env 并编辑）" >&2
  echo "  示例: cr.volces.com/<namespace>/hermes-webui-expert" >&2
  exit 1
fi

if [ -z "$REGISTRY_HOST" ]; then
  REGISTRY_HOST="${IMAGE_REPO%%/*}"
fi

FULL_IMAGE="${IMAGE_REPO}:${IMAGE_TAG}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker 未安装" >&2
  exit 1
fi

if [ "$DO_LOGIN" = "1" ]; then
  echo "[login] docker login $REGISTRY_HOST"
  if [ "$DRY_RUN" = "1" ]; then
    echo "  (dry-run) docker login $REGISTRY_HOST"
  else
    docker login "$REGISTRY_HOST"
  fi
fi

if ! docker buildx version >/dev/null 2>&1; then
  echo "ERROR: docker buildx 不可用，请安装 docker-buildx-plugin" >&2
  exit 1
fi

BUILDER_NAME="${BUILDX_BUILDER:-hermes-registry-builder}"
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

PUSH_FLAG="--push"
if [ "$NO_PUSH" = "1" ]; then
  PUSH_FLAG="--load"
  if [ "$BUILD_PLATFORM" != "linux/amd64" ] && [ "$(uname -m)" != "x86_64" ]; then
    echo "WARN: --no-push 且非 amd64 本机时，跨平台 --load 可能失败；建议去掉 --no-push 直接 --push" >&2
  fi
fi

BUILD_CMD=(
  docker buildx build
  --platform "$BUILD_PLATFORM"
  -t "$FULL_IMAGE"
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
  "$PUSH_FLAG"
  .
)

echo "[build] ${FULL_IMAGE}"
echo "[platform] ${BUILD_PLATFORM}"
printf '  '; printf '%q ' "${BUILD_CMD[@]}"; echo

if [ "$DRY_RUN" = "1" ]; then
  echo
  echo "DRY-RUN: 未执行构建"
  exit 0
fi

"${BUILD_CMD[@]}"

echo
echo "========================================"
echo "镜像已就绪: ${FULL_IMAGE}"
echo "========================================"
echo
echo "nodeskclaw 配置："
echo
echo "1. 组织设置 → 镜像仓库 → Hermes 专家服务"
echo "   ${IMAGE_REPO}"
echo
echo "2. 组织设置 → 引擎版本 → Hermes 专家服务 → 发布新版本"
echo "   ${IMAGE_TAG}"
echo
echo "3. 部署时 nodeskclaw 将拉取："
echo "   ${FULL_IMAGE}"
echo
