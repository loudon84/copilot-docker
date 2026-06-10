#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:?usage: create-instance.sh <profile> <webui_port> <expert>}"
PORT="${2:?usage: create-instance.sh <profile> <webui_port> <expert>}"
EXPERT="${3:?usage: create-instance.sh <profile> <webui_port> <expert>}"

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTANCE_DIR="$BASE_DIR/instances/$PROFILE"
DATA_DIR="$INSTANCE_DIR/data/hermes"

mkdir -p \
  "$DATA_DIR" \
  "$DATA_DIR/workspace" \
  "$DATA_DIR/workspace/materials" \
  "$DATA_DIR/workspace/references" \
  "$DATA_DIR/workspace/drafts" \
  "$DATA_DIR/workspace/exports" \
  "$DATA_DIR/workspace/artifacts" \
  "$DATA_DIR/obsidian-vault" \
  "$DATA_DIR/obsidian-vault/00-Inbox" \
  "$DATA_DIR/obsidian-vault/10-Articles" \
  "$DATA_DIR/obsidian-vault/20-Research" \
  "$DATA_DIR/obsidian-vault/30-Templates" \
  "$DATA_DIR/obsidian-vault/40-Skills" \
  "$DATA_DIR/obsidian-vault/50-Memory" \
  "$DATA_DIR/obsidian-vault/60-Reports" \
  "$DATA_DIR/obsidian-vault/70-Brain" \
  "$DATA_DIR/obsidian-vault/80-Product-Spec" \
  "$DATA_DIR/obsidian-vault/90-Archive" \
  "$DATA_DIR/memories" \
  "$DATA_DIR/skills" \
  "$DATA_DIR/tools" \
  "$DATA_DIR/plugins" \
  "$DATA_DIR/hindsight" \
  "$DATA_DIR/gbrain" \
  "$DATA_DIR/evolution/runs" \
  "$DATA_DIR/evolution/reports" \
  "$DATA_DIR/skill-bundles" \
  "$DATA_DIR/skill-inbox" \
  "$DATA_DIR/attachments" \
  "$DATA_DIR/policies" \
  "$DATA_DIR/mcp" \
  "$DATA_DIR/backups" \
  "$DATA_DIR/logs" \
  "$DATA_DIR/sessions" \
  "$DATA_DIR/webui"

if [ ! -f "$INSTANCE_DIR/.env" ]; then
  PASS="$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-24)"
  cat > "$INSTANCE_DIR/.env" <<EOF_ENV
UID=1000
GID=1000
HERMES_WEBUI_REPO=http://git.superic.com/aiplatform/hermes-webui.git
HERMES_WEBUI_REF=master
HERMES_AGENT_REPO=http://git.superic.com/aiplatform/hermes-agent.git
HERMES_AGENT_REF=master
HERMES_VERSION=git-build
LOCAL_IMAGE_NAME=hermes-agent-webui:latest
HERMES_WEBUI_BIND=0.0.0.0
HERMES_WEBUI_PORT=$PORT
HERMES_WEBUI_PASSWORD=$PASS
HERMES_PROFILE=$PROFILE
HERMES_EXPERT=$EXPERT
HINDSIGHT_API_URL=http://hindsight.superic.com:8888
HINDSIGHT_BANK_ID=hermes-$PROFILE
INSTALL_GBRAIN=1
GBRAIN_REPO=http://git.superic.com/aiplatform/gbrain.git
INSTALL_FILESYSTEM_MCP=1
INSTALL_CLAWSEC=0
CLAWSEC_REPO=http://git.superic.com/aiplatform/clawsec.git
GBRAIN_ENABLED=1
HERMES_CURATOR_ENABLED=1
HERMES_SELF_EVOLUTION_ENABLED=0

USE_CN_MIRRORS=1
APT_MIRROR=https://mirrors.aliyun.com/debian
PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
NPM_REGISTRY=https://registry.npmmirror.com

EOF_ENV
  chmod 600 "$INSTANCE_DIR/.env"
fi

chown -R 1000:1000 "$DATA_DIR" 2>/dev/null || true
chmod -R u+rwX,g+rwX "$DATA_DIR" 2>/dev/null || true
chmod 600 "$INSTANCE_DIR/.env" 2>/dev/null || true

bash "$BASE_DIR/scripts/inject-expert.sh" "$PROFILE" "$EXPERT"

echo "Instance created: $PROFILE"
echo "WebUI: http://<server-ip>:$PORT"
echo "Password: $(grep HERMES_WEBUI_PASSWORD "$INSTANCE_DIR/.env" | cut -d= -f2-)"
echo "Env file: $INSTANCE_DIR/.env"
echo "Hint: 镜像全实例共享；若尚未 build，先执行 bash scripts/build-image.sh，再 bash scripts/up-instance.sh $PROFILE"
