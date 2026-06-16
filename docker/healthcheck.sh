#!/usr/bin/env bash
set -euo pipefail

curl -fsS http://127.0.0.1:8787/health >/dev/null

if [ "${API_SERVER_ENABLED:-true}" = "true" ] || [ "${API_SERVER_ENABLED:-true}" = "1" ]; then
  curl -fsS "http://127.0.0.1:${API_SERVER_PORT:-8642}/health" >/dev/null
fi
