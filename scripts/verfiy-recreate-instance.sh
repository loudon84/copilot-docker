#!/usr/bin/env bash
set -euo pipefail

# Recreate one existing production instance from hermes-agent-webui:latest.
# Usage:
#   bash scripts/recreate-instance-from-latest.sh common-writer
#   bash scripts/recreate-instance-from-latest.sh common-writer verify-agent
#   bash scripts/recreate-instance-from-latest.sh common-writer verify-agent --drop-verify

PROFILE="${1:?usage: recreate-instance-from-latest.sh <profile> [verify_profile_or_image] [--drop-verify]}"
shift

VERIFY_SOURCE=""
DROP_VERIFY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --drop-verify)
      DROP_VERIFY=1
      ;;
    *)
      if [ -n "$VERIFY_SOURCE" ]; then
        echo "ERROR: unknown arg: $1" >&2
        exit 1
      fi
      VERIFY_SOURCE="$1"
      ;;
  esac
  shift
done
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
ENV_FILE="instances/${PROFILE}/.env"
CONTAINER="hermes-${PROFILE}"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 1
fi

set_env() {
  local key="$1"
  local value="$2"
  local file="$3"
  local tmp
  tmp="$(mktemp)"
  grep -v -E "^${key}=" "$file" > "$tmp" || true
  printf '%s=%s\n' "$key" "$value" >> "$tmp"
  mv "$tmp" "$file"
}

set_env LOCAL_IMAGE_NAME "hermes-agent-webui:latest" "$ENV_FILE"

if [ -n "$VERIFY_SOURCE" ]; then
  echo "[recreate] promoting verify image to latest first: $VERIFY_SOURCE"
  bash "$ROOT_DIR/scripts/promote-verify-to-latest.sh" "$VERIFY_SOURCE"
fi

echo "[recreate] removing old container: $CONTAINER"
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

echo "[recreate] starting from hermes-agent-webui:latest"
docker compose --env-file "$ENV_FILE" up -d --force-recreate --no-build hermes-agent-webui

echo "[recreate] running commit:"
docker exec "$CONTAINER" bash -lc 'cd /opt/hermes-agent && git rev-parse HEAD && git log -1 --oneline'

if [ "$DROP_VERIFY" = "1" ]; then
  echo "[recreate] dropping promoted verify tag"
  bash "$ROOT_DIR/scripts/drop-verify-image.sh" "${VERIFY_SOURCE:-}"
fi
