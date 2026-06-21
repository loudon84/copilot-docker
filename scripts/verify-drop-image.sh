#!/usr/bin/env bash
set -euo pipefail

# Remove a promoted verify image tag after production containers use :latest.
# This only drops the verify tag alias; image layers stay while :latest references them.
# Usage:
#   bash scripts/drop-verify-image.sh
#   bash scripts/drop-verify-image.sh hermes-agent-webui:verify-xxx
#   bash scripts/drop-verify-image.sh verify-agent
# Optional:
#   PRUNE_OLD_LATEST=1   # also remove dangling images left by the previous :latest

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

strip_cr() {
  printf '%s' "$1" | tr -d '\r'
}

image_from_profile_env() {
  local profile="$1"
  local env_file="instances/${profile}/.env"
  if [ ! -f "$env_file" ]; then
    return 1
  fi
  strip_cr "$(grep -E '^LOCAL_IMAGE_NAME=' "$env_file" | tail -1 | cut -d= -f2-)"
}

resolve_verify_image() {
  local arg
  arg="$(strip_cr "${1:-}")"
  if [ -z "$arg" ]; then
    return 1
  fi
  if docker image inspect "$arg" >/dev/null 2>&1; then
    printf '%s' "$arg"
    return 0
  fi
  local profile_image
  profile_image="$(image_from_profile_env "$arg" || true)"
  if [ -n "$profile_image" ] && docker image inspect "$profile_image" >/dev/null 2>&1; then
    printf '%s' "$profile_image"
    return 0
  fi
  printf '%s' "$arg"
}

LATEST_TAG="${LATEST_TAG:-hermes-agent-webui:latest}"
VERIFY_ARG="$(strip_cr "${1:-}")"
VERIFY_IMAGE=""

if [ -n "$VERIFY_ARG" ]; then
  VERIFY_IMAGE="$(resolve_verify_image "$VERIFY_ARG")"
elif [ -f .build/latest-image.env ]; then
  # shellcheck disable=SC1091
  source .build/latest-image.env
  VERIFY_IMAGE="$(strip_cr "${PROMOTED_FROM:-}")"
fi

if [ -z "$VERIFY_IMAGE" ]; then
  echo "ERROR: verify image is required." >&2
  echo "       bash scripts/drop-verify-image.sh <verify_image|verify_profile>" >&2
  exit 1
fi

if ! docker image inspect "$VERIFY_IMAGE" >/dev/null 2>&1; then
  echo "[drop-verify] skip: image not found: $VERIFY_IMAGE"
  exit 0
fi

if ! docker image inspect "$LATEST_TAG" >/dev/null 2>&1; then
  echo "ERROR: latest tag not found: $LATEST_TAG" >&2
  exit 1
fi

VERIFY_ID="$(docker image inspect "$VERIFY_IMAGE" --format '{{.Id}}')"
LATEST_ID="$(docker image inspect "$LATEST_TAG" --format '{{.Id}}')"

if [ "$VERIFY_ID" != "$LATEST_ID" ]; then
  echo "ERROR: refuse to drop verify tag; latest id differs from verify id." >&2
  echo "       verify=$VERIFY_ID" >&2
  echo "       latest=$LATEST_ID" >&2
  exit 1
fi

mapfile -t USING_CONTAINERS < <(docker ps -a --filter "ancestor=${VERIFY_IMAGE}" --format '{{.Names}}')
if [ "${#USING_CONTAINERS[@]}" -gt 0 ]; then
  echo "ERROR: containers still reference verify image: ${USING_CONTAINERS[*]}" >&2
  echo "       stop/remove them first, e.g. docker rm -f hermes-<verify_profile>" >&2
  exit 1
fi

echo "[drop-verify] removing tag only: $VERIFY_IMAGE"
docker rmi "$VERIFY_IMAGE"

if [ "${PRUNE_OLD_LATEST:-0}" = "1" ]; then
  echo "[drop-verify] pruning dangling images from previous :latest"
  docker image prune -f
fi

echo "[drop-verify] done. $LATEST_TAG still references image id $LATEST_ID"
