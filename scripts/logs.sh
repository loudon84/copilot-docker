#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:?usage: logs.sh <profile> [webui|gateway|all]}"
MODE="${2:-webui}"

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

CONTAINER="hermes-$PROFILE"
GATEWAY_LOG="/data/hermes/logs/hermes-gateway.log"

case "$MODE" in
  webui)
    docker compose --env-file "instances/$PROFILE/.env" -p "hermes-$PROFILE" logs -f --tail=200 hermes-agent-webui
    ;;
  gateway)
    docker exec "$CONTAINER" tail -f -n 200 "$GATEWAY_LOG"
    ;;
  all)
    echo "[logs] gateway log: $GATEWAY_LOG"
    docker exec "$CONTAINER" tail -n 50 "$GATEWAY_LOG" 2>/dev/null || echo "WARN: gateway log not found"
    echo "---"
    docker compose --env-file "instances/$PROFILE/.env" -p "hermes-$PROFILE" logs -f --tail=200 hermes-agent-webui
    ;;
  -h|--help)
    echo "usage: logs.sh <profile> [webui|gateway|all]"
    exit 0
    ;;
  *)
    echo "ERROR: unknown mode: $MODE (use webui|gateway|all)" >&2
    exit 1
    ;;
esac
