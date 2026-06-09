#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:?usage: doctor-paths.sh <profile> [--fix]}"
FIX=0

shift || true
while [ $# -gt 0 ]; do
  case "$1" in
    --fix) FIX=1 ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
  shift
done

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$BASE_DIR/instances/$PROFILE/data/hermes"
CONTAINER="hermes-$PROFILE"
REQUIRED_DIRS=(skills tools plugins mcp policies skill-bundles gbrain)

if [ "$FIX" = "1" ]; then
  mkdir -p "$DATA_DIR"
  for d in "${REQUIRED_DIRS[@]}"; do
    mkdir -p "$DATA_DIR/$d"
  done
  rm -f "$DATA_DIR/tools/tools" 2>/dev/null || true
  rm -f "$DATA_DIR/plugins/plugins" 2>/dev/null || true
  chown -R 1000:1000 \
    "$DATA_DIR/tools" \
    "$DATA_DIR/plugins" \
    "$DATA_DIR/skills" \
    "$DATA_DIR/mcp" \
    "$DATA_DIR/policies" \
    "$DATA_DIR/skill-bundles" \
    "$DATA_DIR/gbrain" 2>/dev/null || true
  chmod -R u+rwX,g+rwX \
    "$DATA_DIR/tools" \
    "$DATA_DIR/plugins" \
    "$DATA_DIR/skills" \
    "$DATA_DIR/mcp" \
    "$DATA_DIR/policies" \
    "$DATA_DIR/skill-bundles" \
    "$DATA_DIR/gbrain" 2>/dev/null || true
fi

ERRORS=0

if [ ! -d "$DATA_DIR" ]; then
  echo "ERROR: missing data dir: $DATA_DIR"
  ERRORS=1
else
  echo "PASS $DATA_DIR"
fi

for d in "${REQUIRED_DIRS[@]}"; do
  if [ ! -d "$DATA_DIR/$d" ]; then
    echo "ERROR: missing directory: $DATA_DIR/$d"
    ERRORS=1
  else
    echo "PASS $DATA_DIR/$d"
  fi
done

for bad in "$DATA_DIR/tools/tools" "$DATA_DIR/plugins/plugins"; do
  if [ -e "$bad" ]; then
    echo "ERROR: invalid nested path: $bad"
    ERRORS=1
  else
    echo "PASS no $(basename "$(dirname "$bad")")/$(basename "$bad")"
  fi
done

if [ -d "$DATA_DIR" ] && [ -w "$DATA_DIR" ]; then
  echo "PASS data dir writable"
elif [ -d "$DATA_DIR" ]; then
  echo "ERROR: data dir not writable: $DATA_DIR"
  ERRORS=1
fi

if docker inspect "$CONTAINER" >/dev/null 2>&1; then
  if ! docker exec "$CONTAINER" bash -lc '
ERRORS=0

for p in /data/hermes/tools /data/hermes/plugins; do
  if [ -d "$p" ]; then
    echo "PASS $p"
  else
    echo "ERROR missing $p"
    ERRORS=1
  fi
done

if mountpoint -q /home/hermeswebui/.hermes/tools; then
  echo "PASS ~/.hermes/tools is mountpoint"
else
  echo "ERROR ~/.hermes/tools is not a mountpoint"
  ERRORS=1
fi

if mountpoint -q /home/hermeswebui/.hermes/plugins; then
  echo "PASS ~/.hermes/plugins is mountpoint"
else
  echo "ERROR ~/.hermes/plugins is not a mountpoint"
  ERRORS=1
fi

if [ "$(id -u)" = "1000" ] && [ "$(id -g)" = "1000" ]; then
  echo "PASS UID/GID 1000"
else
  echo "ERROR expected UID/GID 1000, got $(id -u):$(id -g)"
  ERRORS=1
fi

if [ -w /app/venv ]; then
  echo "PASS /app/venv writable"
else
  echo "ERROR /app/venv not writable"
  ERRORS=1
fi

if [ -e /data/hermes/tools/tools ] || [ -e /data/hermes/plugins/plugins ]; then
  echo "ERROR nested tools/plugins path exists in container"
  ERRORS=1
fi

exit "$ERRORS"
'; then
    ERRORS=1
  fi
fi

if [ "$ERRORS" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi

echo "PASS"
