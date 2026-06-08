#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:-writer}"
CONTAINER="hermes-${PROFILE}"
if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "ERROR: container not running: $CONTAINER"
  exit 1
fi

docker exec -u root -i "$CONTAINER" bash <<'EOS'
set -euo pipefail
export HERMES_HOME=/data/hermes
export HERMES_CONFIG_PATH=/data/hermes/config.yaml

echo "[container] $(hostname)"
echo "[user] $(id)"
echo "[paths]"
for p in /data/hermes /data/hermes/config.yaml /data/hermes/skills /data/hermes/obsidian-vault /data/hermes/gbrain /opt/hermes-agent /app/venv/bin/python; do
  if [ -e "$p" ]; then echo "PASS $p"; else echo "MISS $p"; fi
done

echo
if command -v gbrain >/dev/null 2>&1; then
  echo "[gbrain] $(command -v gbrain)"
  gbrain --help >/dev/null 2>&1 && echo "PASS gbrain help" || echo "WARN gbrain help failed"
else
  echo "WARN gbrain not installed"
fi

echo
if [ -x /app/venv/bin/hermes ]; then
  /app/venv/bin/hermes --version || true
  /app/venv/bin/hermes skills list | head -80 || true
else
  /app/venv/bin/python -m hermes_cli.main --version || true
fi

echo
curl -fsS http://127.0.0.1:8787/health || true
EOS
