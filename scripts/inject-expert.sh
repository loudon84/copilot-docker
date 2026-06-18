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

PRESERVE_FULL_CONFIG=0
if [ -f "$DATA_DIR/config.yaml" ] && grep -qE '^(model|providers):' "$DATA_DIR/config.yaml" 2>/dev/null; then
  PRESERVE_FULL_CONFIG=1
  mkdir -p "$DATA_DIR/.backup/$TS"
  cp "$DATA_DIR/config.yaml" "$DATA_DIR/.backup/$TS/config.yaml"
  echo "[config] 检测到完整 config（含 model/providers），将保留并仅合并 runtime 段"
fi

for f in SOUL.md memories/MEMORY.md memories/USER.md hindsight/config.json workspace/AGENTS.md; do
  [ -f "$DATA_DIR/$f" ] && mkdir -p "$DATA_DIR/.backup/$TS/$(dirname "$f")" && cp "$DATA_DIR/$f" "$DATA_DIR/.backup/$TS/$f"
done

if [ "$PRESERVE_FULL_CONFIG" = "0" ]; then
  [ -f "$DATA_DIR/config.yaml" ] && mkdir -p "$DATA_DIR/.backup/$TS" && cp "$DATA_DIR/config.yaml" "$DATA_DIR/.backup/$TS/config.yaml"
fi

for d in skills tools plugins mcp policies skill-bundles gbrain; do
  if [ -d "$DATA_DIR/$d" ]; then
    mkdir -p "$DATA_DIR/.backup/$TS"
    cp -a "$DATA_DIR/$d" "$DATA_DIR/.backup/$TS/$d"
  fi
done

cp -R "$TPL_BASE/." "$DATA_DIR/"
cp -R "$TPL_EXPERT/." "$DATA_DIR/"

if [ "$PRESERVE_FULL_CONFIG" = "1" ]; then
  cp "$DATA_DIR/.backup/$TS/config.yaml" "$DATA_DIR/config.yaml"
fi

find "$DATA_DIR" -type f \( -name '*.md' -o -name '*.yaml' -o -name '*.json' -o -name '.env' \) -print0 | while IFS= read -r -d '' file; do
  if [ "$PRESERVE_FULL_CONFIG" = "1" ] && [ "$file" = "$DATA_DIR/config.yaml" ]; then
    continue
  fi
  sed -i "s|__PROFILE__|$PROFILE|g; s|__EXPERT__|$EXPERT|g; s|__HINDSIGHT_API_URL__|http://hindsight.superic.com:8888|g" "$file"
done

bash "$BASE_DIR/scripts/patch-config-runtime.sh" "$PROFILE"

# shellcheck source=lib/init_hermes_dirs.sh
source "$BASE_DIR/scripts/lib/init_hermes_dirs.sh"
init_hermes_dirs "$DATA_DIR"
chmod 600 "$DATA_DIR/.env" 2>/dev/null || true
bash "$BASE_DIR/scripts/sync-runtime-env.sh" "$PROFILE" 2>/dev/null || true
echo "Injected expert '$EXPERT' into instance '$PROFILE'"
