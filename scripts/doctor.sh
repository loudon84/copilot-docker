#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:?usage: doctor.sh <profile>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$BASE_DIR/instances/$PROFILE/.env"
DATA_DIR="$BASE_DIR/instances/$PROFILE/data/hermes"
source "$ENV_FILE"
echo "[profile] $PROFILE"
echo "[webui] http://127.0.0.1:${HERMES_WEBUI_PORT}"
echo "[health]"
curl -fsS "http://127.0.0.1:${HERMES_WEBUI_PORT}/health" || true
echo
for p in config.yaml .env SOUL.md memories/MEMORY.md memories/USER.md hindsight/config.json workspace/AGENTS.md; do
  [ -f "$DATA_DIR/$p" ] && echo "PASS file $p" || echo "FAIL missing $p"
done
echo "[hindsight]"
cat "$DATA_DIR/hindsight/config.json" | jq '{mode, api_url, bank_id_template, recall_budget, recall_prefetch_method, recall_max_tokens, auto_recall, auto_retain, retain_async, retain_every_n_turns, memory_mode}' || true
