#!/usr/bin/env bash
set -euo pipefail

log() {
  echo "[entrypoint] $*"
}

export PATH="/app/venv/bin:/usr/local/bin:${PATH:-}"
export HERMES_HOME="${HERMES_HOME:-/data/hermes}"
export HERMES_CONFIG_PATH="${HERMES_CONFIG_PATH:-/data/hermes/config.yaml}"
export API_SERVER_ENABLED="${API_SERVER_ENABLED:-true}"
export API_SERVER_HOST="${API_SERVER_HOST:-0.0.0.0}"
export API_SERVER_PORT="${API_SERVER_PORT:-8642}"

mkdir -p "$HERMES_HOME" "$HERMES_HOME/logs"

# Hermes gateway 读取 $HERMES_HOME/.env，需将 compose 注入的 API_SERVER_* 同步进去
if [ -x /usr/local/bin/sync-runtime-env.sh ]; then
  /usr/local/bin/sync-runtime-env.sh
fi

log "HERMES_PROFILE=${HERMES_PROFILE:-default}"
log "HERMES_HOME=$HERMES_HOME"
log "HERMES_CONFIG_PATH=$HERMES_CONFIG_PATH"
log "HERMES_WEBUI_PORT=${HERMES_WEBUI_PORT:-8787}"
log "API_SERVER_ENABLED=${API_SERVER_ENABLED}"
log "API_SERVER_HOST=${API_SERVER_HOST}"
log "API_SERVER_PORT=${API_SERVER_PORT}"
log "API_SERVER_MODEL_NAME=${API_SERVER_MODEL_NAME:-}"

HERMES_GATEWAY_PID=""

start_gateway() {
  if /app/venv/bin/hermes gateway run --help >/dev/null 2>&1; then
    /app/venv/bin/hermes gateway run
  else
    /app/venv/bin/hermes gateway
  fi
}

if [ "${API_SERVER_ENABLED}" = "true" ] || [ "${API_SERVER_ENABLED}" = "1" ] || [ "${API_SERVER_ENABLED}" = "yes" ]; then
  if [ -z "${API_SERVER_KEY:-}" ]; then
    log "ERROR: API_SERVER_KEY is required when API_SERVER_ENABLED=true"
    exit 1
  fi

  log "Starting Hermes Agent API Server via hermes gateway..."
  start_gateway > "$HERMES_HOME/logs/hermes-gateway.log" 2>&1 &
  HERMES_GATEWAY_PID=$!
  log "Hermes gateway pid=$HERMES_GATEWAY_PID"

  for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${API_SERVER_PORT}/health" >/dev/null 2>&1; then
      log "Hermes Agent API Server is ready on ${API_SERVER_HOST}:${API_SERVER_PORT}"
      break
    fi

    if ! kill -0 "$HERMES_GATEWAY_PID" >/dev/null 2>&1; then
      log "ERROR: Hermes gateway exited during startup"
      tail -200 "$HERMES_HOME/logs/hermes-gateway.log" || true
      exit 1
    fi

    sleep 1
  done

  if ! curl -fsS "http://127.0.0.1:${API_SERVER_PORT}/health" >/dev/null 2>&1; then
    log "ERROR: Hermes Agent API Server did not become ready"
    tail -200 "$HERMES_HOME/logs/hermes-gateway.log" || true
    exit 1
  fi
else
  log "API server disabled; skip hermes gateway startup"
fi

log "Starting Hermes WebUI..."
/hermeswebui_init.bash &
HERMES_WEBUI_PID=$!
log "Hermes WebUI pid=$HERMES_WEBUI_PID"

if [ -n "$HERMES_GATEWAY_PID" ]; then
  wait -n "$HERMES_WEBUI_PID" "$HERMES_GATEWAY_PID"
else
  wait -n "$HERMES_WEBUI_PID"
fi
EXIT_CODE=$?

log "A core process exited; stopping container. exit=$EXIT_CODE"

if [ -n "$HERMES_GATEWAY_PID" ]; then
  kill "$HERMES_GATEWAY_PID" >/dev/null 2>&1 || true
fi

kill "$HERMES_WEBUI_PID" >/dev/null 2>&1 || true

exit "$EXIT_CODE"
