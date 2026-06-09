#!/usr/bin/env bash
set -euo pipefail

BUNDLE="${1:?usage: promote-bundle-to-template.sh <bundle_name> <expert>}"
EXPERT="${2:?usage: promote-bundle-to-template.sh <bundle_name> <expert>}"

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="$BASE_DIR/asset-bundles/$BUNDLE"
TPL_DIR="$BASE_DIR/expert-templates/$EXPERT"

[ -d "$BUNDLE_DIR" ] || { echo "ERROR: bundle not found: $BUNDLE_DIR"; exit 1; }
[ -f "$BUNDLE_DIR/data-hermes-assets.tgz" ] || { echo "ERROR: missing archive: $BUNDLE_DIR/data-hermes-assets.tgz"; exit 1; }
[ -d "$TPL_DIR" ] || { echo "ERROR: expert template not found: $TPL_DIR"; exit 1; }

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BASE_DIR/expert-templates/.backup/$EXPERT-$TS"
mkdir -p "$(dirname "$BACKUP_DIR")"
cp -a "$TPL_DIR" "$BACKUP_DIR"

tar xzf "$BUNDLE_DIR/data-hermes-assets.tgz" -C "$TPL_DIR"

for bad in "$TPL_DIR/tools/tools" "$TPL_DIR/plugins/plugins" \
           "$TPL_DIR/.env" "$TPL_DIR/sessions" "$TPL_DIR/logs" \
           "$TPL_DIR/webui" "$TPL_DIR/hindsight" "$TPL_DIR/workspace" \
           "$TPL_DIR/obsidian-vault" "$TPL_DIR/memories"; do
  if [ -e "$bad" ]; then
    echo "ERROR: prohibited path in template: $bad"
    exit 1
  fi
done

echo "OK: promoted bundle '$BUNDLE' to expert template '$EXPERT'"
echo "Backup: $BACKUP_DIR"
