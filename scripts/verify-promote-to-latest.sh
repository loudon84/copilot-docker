#!/usr/bin/env bash
set -euo pipefail

# Promote the verified image to :latest by retagging only.
# This does not restart existing production containers.
# Usage:
#   bash scripts/promote-verify-to-latest.sh
#   bash scripts/promote-verify-to-latest.sh hermes-agent-webui:verify-xxx
#   bash scripts/promote-verify-to-latest.sh verify-agent
#   bash scripts/promote-verify-to-latest.sh verify-agent hermes-agent-webui:latest

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

strip_cr() {
  printf '%s' "$1" | tr -d '\r'
}

load_verify_env() {
  if [ -f .build/verify-image.env ]; then
    # shellcheck disable=SC1091
    source .build/verify-image.env
  fi
  VERIFY_IMAGE_NAME="$(strip_cr "${VERIFY_IMAGE_NAME:-}")"
  VERIFY_IMAGE_TAG="$(strip_cr "${VERIFY_IMAGE_TAG:-}")"
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

  if [ -n "$arg" ]; then
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

    echo "ERROR: cannot resolve verify image from arg: $arg" >&2
    echo "       pass a local image ref (hermes-agent-webui:verify-...) or a verify profile name." >&2
    return 1
  fi

  load_verify_env
  if [ -n "$VERIFY_IMAGE_NAME" ] && docker image inspect "$VERIFY_IMAGE_NAME" >/dev/null 2>&1; then
    printf '%s' "$VERIFY_IMAGE_NAME"
    return 0
  fi
  if [ -n "$VERIFY_IMAGE_TAG" ] && docker image inspect "$VERIFY_IMAGE_TAG" >/dev/null 2>&1; then
    printf '%s' "$VERIFY_IMAGE_TAG"
    return 0
  fi

  echo "ERROR: verify image is required." >&2
  echo "       Run: bash scripts/build-verify-image.sh" >&2
  echo "       Or:  bash scripts/promote-verify-to-latest.sh <verify_image|verify_profile>" >&2
  return 1
}

VERIFY_ARG="$(strip_cr "${1:-}")"
LATEST_TAG="$(strip_cr "${2:-hermes-agent-webui:latest}")"
VERIFY_IMAGE="$(resolve_verify_image "$VERIFY_ARG")"

if [ -z "$LATEST_TAG" ]; then
  echo "ERROR: latest tag must not be empty." >&2
  exit 1
fi

BEFORE_LATEST_ID=""
if docker image inspect "$LATEST_TAG" >/dev/null 2>&1; then
  BEFORE_LATEST_ID="$(docker image inspect "$LATEST_TAG" --format '{{.Id}}')"
  echo "[promote] latest before: $LATEST_TAG -> $BEFORE_LATEST_ID"
else
  echo "[promote] latest before: $LATEST_TAG -> <missing>"
fi

VERIFY_ID="$(docker image inspect "$VERIFY_IMAGE" --format '{{.Id}}')"
echo "[promote] verify image: $VERIFY_IMAGE -> $VERIFY_ID"

if [ -n "$BEFORE_LATEST_ID" ] && [ "$BEFORE_LATEST_ID" = "$VERIFY_ID" ]; then
  echo "[promote] skip: latest already points to verify image id"
else
  echo "[promote] tagging $VERIFY_IMAGE -> $LATEST_TAG"
  docker tag "$VERIFY_IMAGE" "$LATEST_TAG"
fi

AFTER_LATEST_ID="$(docker image inspect "$LATEST_TAG" --format '{{.Id}}')"
echo "[promote] latest after : $LATEST_TAG -> $AFTER_LATEST_ID"

if [ "$AFTER_LATEST_ID" != "$VERIFY_ID" ]; then
  echo "ERROR: promote failed; latest tag id does not match verify image id." >&2
  echo "       verify=$VERIFY_ID" >&2
  echo "       latest=$AFTER_LATEST_ID" >&2
  exit 1
fi

mkdir -p .build
cat > .build/latest-image.env <<ENV
LATEST_IMAGE_NAME=${LATEST_TAG}
PROMOTED_FROM=${VERIFY_IMAGE}
PROMOTED_AT=$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)
PROMOTED_IMAGE_ID=${AFTER_LATEST_ID}
ENV

cat <<INFO
[promote] done. latest tag id now matches verify image.
Existing containers are not changed; recreate production instances to pick up :latest.

  bash scripts/recreate-instance-from-latest.sh <profile>
  # promote + recreate + drop verify tag:
  bash scripts/recreate-instance-from-latest.sh <profile> <verify_profile> --drop-verify
  # or manually after all containers use :latest:
  bash scripts/drop-verify-image.sh ${VERIFY_IMAGE}
INFO
