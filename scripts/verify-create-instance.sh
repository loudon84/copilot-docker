#!/usr/bin/env bash
set -euo pipefail

# Create and start an isolated verification instance from a non-latest image.
# Usage:
#   bash scripts/create-verify-instance.sh common-writer verify-agent 18900
# Optional:
#   VERIFY_IMAGE_NAME=hermes-agent-webui:verify-xxx bash scripts/create-verify-instance.sh common-writer verify-agent 18900
#   COPY_DATA=1   # default 1: copy base profile data for realistic validation

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_PROFILE="${1:?usage: create-verify-instance.sh <base_profile> <verify_profile> <webui_port> [gateway_port]}"
VERIFY_PROFILE="${2:?usage: create-verify-instance.sh <base_profile> <verify_profile> <webui_port> [gateway_port]}"
WEBUI_PORT="${3:?usage: create-verify-instance.sh <base_profile> <verify_profile> <webui_port> [gateway_port]}"
GATEWAY_PORT="${4:-$((20000 + WEBUI_PORT))}"

if [ -f .build/verify-image.env ]; then
  # shellcheck disable=SC1091
  source .build/verify-image.env
fi
VERIFY_IMAGE_NAME="${VERIFY_IMAGE_NAME:?VERIFY_IMAGE_NAME is required. Run build-verify-image.sh first or export VERIFY_IMAGE_NAME.}"

BASE_DIR="instances/${BASE_PROFILE}"
VERIFY_DIR="instances/${VERIFY_PROFILE}"
BASE_ENV="${BASE_DIR}/.env"
VERIFY_ENV="${VERIFY_DIR}/.env"

if [ ! -f "$BASE_ENV" ]; then
  echo "ERROR: base env not found: $BASE_ENV" >&2
  exit 1
fi

mkdir -p "$VERIFY_DIR"
cp "$BASE_ENV" "$VERIFY_ENV"

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

random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 24 | tr -d '=+/[:space:]' | cut -c1-24
  else
    date +%s%N | sha256sum | cut -c1-24
  fi
}

set_env LOCAL_IMAGE_NAME "$VERIFY_IMAGE_NAME" "$VERIFY_ENV"
set_env HERMES_PROFILE "$VERIFY_PROFILE" "$VERIFY_ENV"
set_env HERMES_WEBUI_PORT "$WEBUI_PORT" "$VERIFY_ENV"
set_env HERMES_GATEWAY_PORT "$GATEWAY_PORT" "$VERIFY_ENV"
set_env HERMES_WEBUI_BIND "0.0.0.0" "$VERIFY_ENV"
set_env HERMES_GATEWAY_BIND "0.0.0.0" "$VERIFY_ENV"
set_env HINDSIGHT_BANK_ID "hermes-${VERIFY_PROFILE}" "$VERIFY_ENV"

# Use separate verification secrets unless explicitly provided.
set_env HERMES_WEBUI_PASSWORD "${VERIFY_WEBUI_PASSWORD:-$(random_secret)}" "$VERIFY_ENV"
set_env API_SERVER_KEY "${VERIFY_API_SERVER_KEY:-$(random_secret)}" "$VERIFY_ENV"

COPY_DATA="${COPY_DATA:-1}"
if [ "$COPY_DATA" = "1" ] && [ -d "${BASE_DIR}/data" ]; then
  echo "[verify-instance] copying data from ${BASE_DIR}/data to ${VERIFY_DIR}/data"
  mkdir -p "${VERIFY_DIR}"
  rsync -a --delete "${BASE_DIR}/data/" "${VERIFY_DIR}/data/"
else
  echo "[verify-instance] creating empty data directory"
  mkdir -p "${VERIFY_DIR}/data/hermes"
fi

echo "[verify-instance] removing old verify container if exists: hermes-${VERIFY_PROFILE}"
docker rm -f "hermes-${VERIFY_PROFILE}" >/dev/null 2>&1 || true

echo "[verify-instance] starting verify instance"
docker compose --env-file "$VERIFY_ENV" up -d --force-recreate --no-build hermes-agent-webui

echo "[verify-instance] compose status"
docker compose --env-file "$VERIFY_ENV" ps

echo "[verify-instance] image + commit inside container"
docker exec "hermes-${VERIFY_PROFILE}" bash -lc '
set -e
printf "container image runtime check\n"
node -v || true
npm -v || true
cd /opt/hermes-agent
printf "hermes-agent HEAD="
git rev-parse HEAD
git log -1 --oneline
'

WEBUI_PASSWORD="$(grep -E '^HERMES_WEBUI_PASSWORD=' "$VERIFY_ENV" | tail -1 | cut -d= -f2-)"
API_KEY="$(grep -E '^API_SERVER_KEY=' "$VERIFY_ENV" | tail -1 | cut -d= -f2-)"
cat <<INFO
[verify-instance] done.
WebUI   : http://127.0.0.1:${WEBUI_PORT}
Gateway : http://127.0.0.1:${GATEWAY_PORT}
Profile : ${VERIFY_PROFILE}
Image   : ${VERIFY_IMAGE_NAME}
Password: ${WEBUI_PASSWORD}
API key : ${API_KEY}
Env file: ${VERIFY_ENV}
INFO
