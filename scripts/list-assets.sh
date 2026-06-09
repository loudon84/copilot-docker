#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:?usage: list-assets.sh <profile>}"
CONTAINER="hermes-$PROFILE"
ERRORS=0

docker inspect "$CONTAINER" >/dev/null 2>&1 || {
  echo "ERROR: container not found: $CONTAINER"
  exit 1
}

docker exec "$CONTAINER" bash -lc '
ERRORS=0

echo "== /data/hermes assets =="
for d in skills tools plugins mcp policies skill-bundles gbrain; do
  echo
  echo "[$d]"
  if [ -d /data/hermes/$d ]; then
    find /data/hermes/$d -maxdepth 2 -mindepth 1 | sort | sed "s|^|  |"
  else
    echo "  missing"
    ERRORS=1
  fi
done

echo
echo "== compatibility paths =="
if mountpoint -q /home/hermeswebui/.hermes/tools; then
  echo "  PASS ~/.hermes/tools is mountpoint"
else
  echo "  ERROR ~/.hermes/tools is not a mountpoint"
  ERRORS=1
fi

if mountpoint -q /home/hermeswebui/.hermes/plugins; then
  echo "  PASS ~/.hermes/plugins is mountpoint"
else
  echo "  ERROR ~/.hermes/plugins is not a mountpoint"
  ERRORS=1
fi

echo
echo "== nested path checks =="
if [ -e /data/hermes/tools/tools ]; then
  echo "  ERROR tools/tools exists"
  ERRORS=1
else
  echo "  PASS no tools/tools"
fi

if [ -e /data/hermes/plugins/plugins ]; then
  echo "  ERROR plugins/plugins exists"
  ERRORS=1
else
  echo "  PASS no plugins/plugins"
fi

exit "$ERRORS"
' || ERRORS=1

if [ "$ERRORS" -ne 0 ]; then
  echo "ERROR: asset path checks failed for $CONTAINER"
  exit 1
fi

echo "OK: asset paths look healthy for $CONTAINER"
