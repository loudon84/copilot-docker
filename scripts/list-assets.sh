#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:?usage: list-assets.sh <profile>}"
CONTAINER="hermes-$PROFILE"

docker inspect "$CONTAINER" >/dev/null 2>&1 || {
  echo "ERROR: container not found: $CONTAINER"
  exit 1
}

docker exec "$CONTAINER" bash -lc '
echo "== /data/hermes assets =="
for d in skills tools plugins mcp policies skill-bundles gbrain; do
  echo
  echo "[$d]"
  if [ -d /data/hermes/$d ]; then
    find /data/hermes/$d -maxdepth 2 -mindepth 1 | sort | sed "s|^|  |"
  else
    echo "  missing"
  fi
done

echo
echo "== compatibility paths =="
ls -ld /home/hermeswebui/.hermes/tools 2>/dev/null || true
ls -ld /home/hermeswebui/.hermes/plugins 2>/dev/null || true
'
