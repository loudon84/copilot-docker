#!/usr/bin/env bash
set -euo pipefail

# Build a non-latest validation image for copilot-docker.
# Usage:
#   bash scripts/build-verify-image.sh
# Optional env:
#   VERIFY_IMAGE_TAG=hermes-agent-webui:verify-xxx
#   HERMES_AGENT_REPO=http://git.superic.com/aiplatform/hermes-agent.git
#   HERMES_AGENT_REF=master
#   HERMES_WEBUI_REPO=http://git.superic.com/aiplatform/hermes-webui.git
#   HERMES_WEBUI_REF=master
#   INSTALL_GBRAIN=1
#   NO_CACHE=1
#   PULL=1

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f Dockerfile ]; then
  echo "ERROR: Dockerfile not found in $ROOT_DIR" >&2
  exit 1
fi

HERMES_AGENT_REPO="${HERMES_AGENT_REPO:-http://git.superic.com/aiplatform/hermes-agent.git}"
HERMES_AGENT_REF="${HERMES_AGENT_REF:-master}"
HERMES_WEBUI_REPO="${HERMES_WEBUI_REPO:-http://git.superic.com/aiplatform/hermes-webui.git}"
HERMES_WEBUI_REF="${HERMES_WEBUI_REF:-master}"
GBRAIN_REPO="${GBRAIN_REPO:-http://git.superic.com/aiplatform/gbrain.git}"
GBRAIN_REF="${GBRAIN_REF:-master}"

PYTHON_BASE_IMAGE="${PYTHON_BASE_IMAGE:-python:3.12-slim-bookworm}"
INSTALL_GBRAIN="${INSTALL_GBRAIN:-1}"
BUN_VERSION="${BUN_VERSION:-bun-v1.2.15}"
INSTALL_FILESYSTEM_MCP="${INSTALL_FILESYSTEM_MCP:-1}"
INSTALL_CLAWSEC="${INSTALL_CLAWSEC:-0}"
CLAWSEC_REPO="${CLAWSEC_REPO:-http://git.superic.com/aiplatform/clawsec.git}"
USE_CN_MIRRORS="${USE_CN_MIRRORS:-1}"
APT_MIRROR="${APT_MIRROR:-https://mirrors.aliyun.com/debian}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"
BUILD_APT_PROXY="${BUILD_APT_PROXY:-}"

resolve_rev() {
  local repo="$1"
  local ref="$2"
  git ls-remote "$repo" "$ref" | awk 'NR==1 {print $1}'
}

echo "[verify-build] resolving remote revisions..."
HERMES_AGENT_REV="$(resolve_rev "$HERMES_AGENT_REPO" "$HERMES_AGENT_REF")"
HERMES_WEBUI_REV="$(resolve_rev "$HERMES_WEBUI_REPO" "$HERMES_WEBUI_REF")"

if [ -z "$HERMES_AGENT_REV" ]; then
  echo "ERROR: cannot resolve Hermes Agent revision: $HERMES_AGENT_REPO $HERMES_AGENT_REF" >&2
  exit 1
fi
if [ -z "$HERMES_WEBUI_REV" ]; then
  echo "ERROR: cannot resolve Hermes WebUI revision: $HERMES_WEBUI_REPO $HERMES_WEBUI_REF" >&2
  exit 1
fi

SHORT_AGENT_REV="${HERMES_AGENT_REV:0:12}"
STAMP="$(date +%Y%m%d%H%M%S)"
VERIFY_IMAGE_TAG="${VERIFY_IMAGE_TAG:-hermes-agent-webui:verify-${SHORT_AGENT_REV}-${STAMP}}"
HERMES_VERSION="${HERMES_VERSION:-agent-${SHORT_AGENT_REV}}"

BUILD_FLAGS=()
if [ "${NO_CACHE:-1}" = "1" ]; then
  BUILD_FLAGS+=(--no-cache)
fi
if [ "${PULL:-1}" = "1" ]; then
  BUILD_FLAGS+=(--pull)
fi

mkdir -p .build
cat > .build/verify-image.env <<ENV
VERIFY_IMAGE_NAME=${VERIFY_IMAGE_TAG}
HERMES_AGENT_REPO=${HERMES_AGENT_REPO}
HERMES_AGENT_REF=${HERMES_AGENT_REF}
HERMES_AGENT_REV=${HERMES_AGENT_REV}
HERMES_WEBUI_REPO=${HERMES_WEBUI_REPO}
HERMES_WEBUI_REF=${HERMES_WEBUI_REF}
HERMES_WEBUI_REV=${HERMES_WEBUI_REV}
HERMES_VERSION=${HERMES_VERSION}
ENV

cat <<INFO
[verify-build] image              : ${VERIFY_IMAGE_TAG}
[verify-build] hermes-agent        : ${HERMES_AGENT_REF} -> ${HERMES_AGENT_REV}
[verify-build] hermes-webui        : ${HERMES_WEBUI_REF} -> ${HERMES_WEBUI_REV}
[verify-build] no-cache / pull     : ${NO_CACHE:-1} / ${PULL:-1}
INFO

docker build "${BUILD_FLAGS[@]}" \
  --build-arg PYTHON_BASE_IMAGE="$PYTHON_BASE_IMAGE" \
  --build-arg HERMES_WEBUI_REPO="$HERMES_WEBUI_REPO" \
  --build-arg HERMES_WEBUI_REF="$HERMES_WEBUI_REF" \
  --build-arg HERMES_AGENT_REPO="$HERMES_AGENT_REPO" \
  --build-arg HERMES_AGENT_REF="$HERMES_AGENT_REF" \
  --build-arg HERMES_VERSION="$HERMES_VERSION" \
  --build-arg INSTALL_GBRAIN="$INSTALL_GBRAIN" \
  --build-arg GBRAIN_REPO="$GBRAIN_REPO" \
  --build-arg GBRAIN_REF="$GBRAIN_REF" \
  --build-arg BUN_VERSION="$BUN_VERSION" \
  --build-arg INSTALL_FILESYSTEM_MCP="$INSTALL_FILESYSTEM_MCP" \
  --build-arg INSTALL_CLAWSEC="$INSTALL_CLAWSEC" \
  --build-arg CLAWSEC_REPO="$CLAWSEC_REPO" \
  --build-arg USE_CN_MIRRORS="$USE_CN_MIRRORS" \
  --build-arg APT_MIRROR="$APT_MIRROR" \
  --build-arg PIP_INDEX_URL="$PIP_INDEX_URL" \
  --build-arg NPM_REGISTRY="$NPM_REGISTRY" \
  --build-arg BUILD_APT_PROXY="$BUILD_APT_PROXY" \
  -t "$VERIFY_IMAGE_TAG" \
  .

echo "[verify-build] built image id:"
docker image inspect "$VERIFY_IMAGE_TAG" --format '{{.Id}}'

echo "[verify-build] verifying image runtime versions and Hermes Agent commit..."
docker run --rm "$VERIFY_IMAGE_TAG" bash -lc '
set -e
node -v
npm -v
cd /opt/hermes-agent
ACTUAL_REV="$(git rev-parse HEAD)"
echo "hermes-agent image HEAD=${ACTUAL_REV}"
git log -1 --oneline
'

echo "[verify-build] done. Metadata saved to .build/verify-image.env"
echo "[verify-build] next: bash scripts/create-verify-instance.sh <base_profile> <verify_profile> <webui_port>"
