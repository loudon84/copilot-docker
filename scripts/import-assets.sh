#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:?usage: import-assets.sh <target_profile> <bundle_name> [--restart]}"
BUNDLE="${2:?usage: import-assets.sh <target_profile> <bundle_name> [--restart]}"
RESTART="${3:-}"

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="$BASE_DIR/asset-bundles/$BUNDLE"
TARGET_DIR="$BASE_DIR/instances/$PROFILE/data/hermes"
CONTAINER="hermes-$PROFILE"

[ -d "$BUNDLE_DIR" ] || { echo "ERROR: bundle not found: $BUNDLE_DIR"; exit 1; }
[ -f "$BUNDLE_DIR/data-hermes-assets.tgz" ] || { echo "ERROR: missing archive: $BUNDLE_DIR/data-hermes-assets.tgz"; exit 1; }
[ -d "$TARGET_DIR" ] || { echo "ERROR: target instance data dir not found: $TARGET_DIR"; exit 1; }

mkdir -p \
  "$TARGET_DIR/skills" \
  "$TARGET_DIR/tools" \
  "$TARGET_DIR/plugins" \
  "$TARGET_DIR/mcp" \
  "$TARGET_DIR/policies" \
  "$TARGET_DIR/skill-bundles" \
  "$TARGET_DIR/gbrain" \
  "$TARGET_DIR/.backup"

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$TARGET_DIR/.backup/import-$BUNDLE-$TS"
mkdir -p "$BACKUP_DIR"

for d in skills tools plugins mcp policies skill-bundles gbrain; do
  if [ -d "$TARGET_DIR/$d" ]; then
    cp -a "$TARGET_DIR/$d" "$BACKUP_DIR/$d" || true
  fi
done

tar xzf "$BUNDLE_DIR/data-hermes-assets.tgz" -C "$TARGET_DIR"

chown -R 1000:1000 \
  "$TARGET_DIR/skills" \
  "$TARGET_DIR/tools" \
  "$TARGET_DIR/plugins" \
  "$TARGET_DIR/mcp" \
  "$TARGET_DIR/policies" \
  "$TARGET_DIR/skill-bundles" \
  "$TARGET_DIR/gbrain" 2>/dev/null || true

chmod -R u+rwX,g+rwX \
  "$TARGET_DIR/skills" \
  "$TARGET_DIR/tools" \
  "$TARGET_DIR/plugins" \
  "$TARGET_DIR/mcp" \
  "$TARGET_DIR/policies" \
  "$TARGET_DIR/skill-bundles" \
  "$TARGET_DIR/gbrain" 2>/dev/null || true

if docker inspect "$CONTAINER" >/dev/null 2>&1; then
  docker exec -u root "$CONTAINER" bash -lc '
    mkdir -p /data/hermes/tools /data/hermes/plugins /home/hermeswebui/.hermes

    if [ ! -L /home/hermeswebui/.hermes/tools ]; then
      rm -rf /home/hermeswebui/.hermes/tools
      ln -sfn /data/hermes/tools /home/hermeswebui/.hermes/tools
    fi

    if [ ! -L /home/hermeswebui/.hermes/plugins ]; then
      rm -rf /home/hermeswebui/.hermes/plugins
      ln -sfn /data/hermes/plugins /home/hermeswebui/.hermes/plugins
    fi

    chown -R 1000:1000 /data/hermes /home/hermeswebui/.hermes || true
    chmod -R u+rwX,g+rwX /data/hermes /home/hermeswebui/.hermes || true
  '

  if [ -s "$BUNDLE_DIR/requirements.txt" ]; then
    docker cp "$BUNDLE_DIR/requirements.txt" "$CONTAINER:/tmp/hermes-bundle-requirements.txt"
    docker exec -u root "$CONTAINER" bash -lc '
      /app/venv/bin/python -m pip install -r /tmp/hermes-bundle-requirements.txt
      chown -R 1000:1000 /app/venv
    '
  fi

  if [ -s "$BUNDLE_DIR/npm-global.txt" ]; then
    docker cp "$BUNDLE_DIR/npm-global.txt" "$CONTAINER:/tmp/hermes-bundle-npm-global.txt"
    docker exec -u root "$CONTAINER" bash -lc '
      while IFS= read -r pkg; do
        case "$pkg" in
          ""|\#*) continue ;;
          *) npm install -g "$pkg" ;;
        esac
      done < /tmp/hermes-bundle-npm-global.txt
    '
  fi

  if [ -f "$BUNDLE_DIR/verify.sh" ]; then
    docker cp "$BUNDLE_DIR/verify.sh" "$CONTAINER:/tmp/hermes-bundle-verify.sh"
    docker exec -u root "$CONTAINER" bash -lc 'chmod +x /tmp/hermes-bundle-verify.sh'
  fi

  if [ "$RESTART" = "--restart" ]; then
    docker restart "$CONTAINER"
  fi
fi

echo "OK: imported bundle '$BUNDLE' into profile '$PROFILE'"
echo "Backup: $BACKUP_DIR"
