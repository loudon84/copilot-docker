#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:?usage: create-instance.sh <profile> <webui_port> <expert>}"
PORT="${2:?usage: create-instance.sh <profile> <webui_port> <expert>}"
EXPERT="${3:?usage: create-instance.sh <profile> <webui_port> <expert>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTANCE_DIR="$BASE_DIR/instances/$PROFILE"
DATA_DIR="$INSTANCE_DIR/data/hermes"
mkdir -p "$DATA_DIR" "$DATA_DIR/workspace" "$DATA_DIR/obsidian-vault" "$DATA_DIR/memories" "$DATA_DIR/skills" "$DATA_DIR/hindsight" "$DATA_DIR/logs" "$DATA_DIR/sessions"
if [ ! -f "$INSTANCE_DIR/.env" ]; then
  PASS="$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-24)"
  cat > "$INSTANCE_DIR/.env" <<EOF_ENV
UID=$(id -u)
GID=$(id -g)
HERMES_WEBUI_IMAGE=ghcr.io/nesquena/hermes-webui:latest
HERMES_AGENT_REPO=https://github.com/NousResearch/hermes-agent.git
HERMES_AGENT_REF=main
LOCAL_IMAGE_NAME=hermes-agent-webui:obsidian-hindsight
HERMES_WEBUI_BIND=0.0.0.0
HERMES_WEBUI_PORT=$PORT
HERMES_WEBUI_PASSWORD=$PASS
HERMES_PROFILE=$PROFILE
HERMES_EXPERT=$EXPERT
HINDSIGHT_API_URL=http://hindsight.superic.com:8888
HINDSIGHT_BANK_ID=hermes-$PROFILE
EOF_ENV
  chmod 600 "$INSTANCE_DIR/.env"
fi
bash "$BASE_DIR/scripts/inject-expert.sh" "$PROFILE" "$EXPERT"
echo "Instance created: $PROFILE"
echo "WebUI: http://<server-ip>:$PORT"
echo "Password: $(grep HERMES_WEBUI_PASSWORD "$INSTANCE_DIR/.env" | cut -d= -f2-)"
