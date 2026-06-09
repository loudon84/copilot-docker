#!/usr/bin/env bash
# 本地 Docker Registry 链路健康检查
#
# 用法：bash scripts/doctor-local-registry.sh

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

LOCAL_REGISTRY_ENV="$BASE_DIR/local-registry.env"
if [ -f "$LOCAL_REGISTRY_ENV" ]; then
  # shellcheck disable=SC1090
  set -a
  source "$LOCAL_REGISTRY_ENV"
  set +a
else
  echo "WARN: $LOCAL_REGISTRY_ENV 不存在，使用默认值" >&2
fi

LOCAL_REGISTRY_HOST="${LOCAL_REGISTRY_HOST:-192.168.102.247}"
LOCAL_REGISTRY_PORT="${LOCAL_REGISTRY_PORT:-9900}"
LOCAL_REGISTRY_CONTAINER_NAME="${LOCAL_REGISTRY_CONTAINER_NAME:-local-registry}"
REGISTRY_ADDR="${LOCAL_REGISTRY_HOST}:${LOCAL_REGISTRY_PORT}"
REGISTRY_URL="http://${REGISTRY_ADDR}"

IMAGE_REPO="${IMAGE_REPO:-${REGISTRY_ADDR}/hermes-webui-expert}"
IMAGE_TAG="${IMAGE_TAG:-v2026.6.1}"
FULL_IMAGE="${IMAGE_REPO}:${IMAGE_TAG}"
REPO_NAME="${IMAGE_REPO#*/}"

PASS=0
FAIL=0

check() {
  local status="$1"
  local msg="$2"
  if [ "$status" = "pass" ]; then
    echo "[pass] $msg"
    PASS=$((PASS + 1))
  else
    echo "[fail] $msg"
    FAIL=$((FAIL + 1))
  fi
}

echo "========================================"
echo "本地 Registry 健康检查"
echo "========================================"
echo "Registry: ${REGISTRY_URL}"
echo "Image:    ${FULL_IMAGE}"
echo

# 1. registry 容器状态
if command -v docker >/dev/null 2>&1; then
  if docker ps --format '{{.Names}}' | grep -qx "$LOCAL_REGISTRY_CONTAINER_NAME"; then
    check pass "registry container running ($LOCAL_REGISTRY_CONTAINER_NAME)"
  else
    check fail "registry container not running ($LOCAL_REGISTRY_CONTAINER_NAME)"
  fi
else
  check fail "docker not installed"
fi

# 2. /v2/_catalog
if curl -fsS "${REGISTRY_URL}/v2/_catalog" >/dev/null 2>&1; then
  CATALOG=$(curl -fsS "${REGISTRY_URL}/v2/_catalog")
  check pass "${REGISTRY_URL}/v2/_catalog reachable"
  echo "       $CATALOG"
else
  check fail "${REGISTRY_URL}/v2/_catalog unreachable"
fi

# 3. hermes-webui-expert tags
TAGS_URL="${REGISTRY_URL}/v2/${REPO_NAME}/tags/list"
if curl -fsS "$TAGS_URL" >/dev/null 2>&1; then
  TAGS_JSON=$(curl -fsS "$TAGS_URL")
  if echo "$TAGS_JSON" | grep -q "\"${IMAGE_TAG}\""; then
    check pass "${REPO_NAME}:${IMAGE_TAG} exists"
  else
    check fail "${REPO_NAME}:${IMAGE_TAG} not found in registry"
    echo "       $TAGS_JSON"
  fi
else
  check fail "${TAGS_URL} unreachable (image may not be pushed yet)"
fi

# 4. docker insecure registry 配置
if command -v docker >/dev/null 2>&1; then
  if docker info 2>/dev/null | grep -q "$REGISTRY_ADDR"; then
    check pass "docker insecure registry configured ($REGISTRY_ADDR)"
  else
    check fail "docker insecure registry not configured ($REGISTRY_ADDR)"
    echo "       执行: sudo bash scripts/configure-insecure-registry.sh"
  fi
else
  check fail "docker not available for insecure registry check"
fi

# 5. docker pull
if command -v docker >/dev/null 2>&1; then
  if docker pull "$FULL_IMAGE" >/dev/null 2>&1; then
    check pass "docker pull succeeded ($FULL_IMAGE)"
  else
    check fail "docker pull failed ($FULL_IMAGE)"
  fi
else
  check fail "docker not available for pull test"
fi

echo
echo "========================================"
echo "结果: ${PASS} pass, ${FAIL} fail"
echo "========================================"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
