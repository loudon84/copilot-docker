#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:?usage: inject-expert.sh <profile> <expert>}"
EXPERT="${2:?usage: inject-expert.sh <profile> <expert>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$BASE_DIR/instances/$PROFILE/data/hermes"
TPL_BASE="$BASE_DIR/expert-templates/base"
TPL_EXPERT="$BASE_DIR/expert-templates/$EXPERT"
[ -d "$TPL_EXPERT" ] || { echo "Expert template not found: $EXPERT"; exit 1; }
mkdir -p "$DATA_DIR" "$DATA_DIR/.backup"
TS="$(date +%Y%m%d-%H%M%S)"
for f in config.yaml SOUL.md memories/MEMORY.md memories/USER.md hindsight/config.json workspace/AGENTS.md; do
  [ -f "$DATA_DIR/$f" ] && mkdir -p "$DATA_DIR/.backup/$TS/$(dirname "$f")" && cp "$DATA_DIR/$f" "$DATA_DIR/.backup/$TS/$f"
done
cp -R "$TPL_BASE/." "$DATA_DIR/"
cp -R "$TPL_EXPERT/." "$DATA_DIR/"
find "$DATA_DIR" -type f \( -name '*.md' -o -name '*.yaml' -o -name '*.json' -o -name '.env' \) -print0 | while IFS= read -r -d '' file; do
  sed -i "s|__PROFILE__|$PROFILE|g; s|__EXPERT__|$EXPERT|g; s|__HINDSIGHT_API_URL__|http://hindsight.superic.com:8888|g" "$file"
done
mkdir -p \
  "$DATA_DIR/workspace/materials" \
  "$DATA_DIR/workspace/references" \
  "$DATA_DIR/workspace/drafts" \
  "$DATA_DIR/workspace/exports" \
  "$DATA_DIR/obsidian-vault/00-Inbox" \
  "$DATA_DIR/obsidian-vault/10-Articles" \
  "$DATA_DIR/obsidian-vault/20-Research" \
  "$DATA_DIR/obsidian-vault/30-Templates" \
  "$DATA_DIR/obsidian-vault/40-Content-Calendar" \
  "$DATA_DIR/obsidian-vault/50-Policies" \
  "$DATA_DIR/obsidian-vault/60-Reports" \
  "$DATA_DIR/obsidian-vault/90-Archive" \
  "$DATA_DIR/sessions" "$DATA_DIR/logs" "$DATA_DIR/webui"
chmod 600 "$DATA_DIR/.env" 2>/dev/null || true
echo "Injected expert '$EXPERT' into instance '$PROFILE'"
