#!/usr/bin/env bash
# Post-start initialization for bi-strategic-office (PRD v1.11.1 hotfix).
# Runs after container is up. Does NOT stop the container on failure.
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE=""
INSTANCE_DIR=""
DATA_DIR=""
REPO_ROOT=""
CONTAINER=""
DEEP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --instance-dir) INSTANCE_DIR="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --repo-root) REPO_ROOT="$2"; shift 2 ;;
    --container) CONTAINER="$2"; shift 2 ;;
    --deep) DEEP=1; shift ;;
    -h|--help)
      echo "usage: post-start.sh --profile <p> --instance-dir <d> --data-dir <d> --repo-root <d> --container <name> [--deep]"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

fail() {
  echo "ERROR: post-start failed: $*" >&2
  echo "Hint: bash \"$PACKAGE_ROOT/bin/doctor.sh\" --profile \"$PROFILE\" --container \"$CONTAINER\"" >&2
  echo "Hint: container left running; fix SQLBOT_* then re-run up-instance or post-start" >&2
  echo "Hint: do NOT fall back to hermes-finance-bi-plugin" >&2
  exit 1
}

[[ -n "$PROFILE" ]] || fail "missing --profile"
[[ -n "$DATA_DIR" ]] || fail "missing --data-dir"
[[ -n "$CONTAINER" ]] || fail "missing --container"

echo "[post-start] profile=$PROFILE container=$CONTAINER"

STATE="$(docker inspect --format '{{.State.Status}}' "$CONTAINER" 2>/dev/null || echo missing)"
[[ "$STATE" == "running" ]] || fail "container not running (state=$STATE)"

if ! docker exec "$CONTAINER" bash -lc 'test -d /data/hermes'; then
  fail "/data/hermes not mounted in container"
fi

PLUGIN_HOST="$DATA_DIR/plugins/hermes-sqlbot-adapter"
REQ_FILE="$PLUGIN_HOST/requirements.txt"
[[ -f "$REQ_FILE" ]] || fail "requirements.txt missing at $REQ_FILE"

HASH_FILE="$DATA_DIR/sqlbot-adapter/.requirements.sha256"
mkdir -p "$DATA_DIR/sqlbot-adapter/state" "$DATA_DIR/sqlbot-adapter/audit"
NEW_HASH=""
if command -v sha256sum >/dev/null 2>&1; then
  NEW_HASH="$(sha256sum "$REQ_FILE" | awk '{print $1}')"
elif command -v shasum >/dev/null 2>&1; then
  NEW_HASH="$(shasum -a 256 "$REQ_FILE" | awk '{print $1}')"
else
  NEW_HASH="$(python -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$REQ_FILE")"
fi

NEED_PIP=1
if [[ -f "$HASH_FILE" ]]; then
  OLD_HASH="$(tr -d ' \n\r' < "$HASH_FILE" || true)"
  if [[ "$OLD_HASH" == "$NEW_HASH" ]]; then
    echo "[post-start] requirements hash unchanged — skip pip install"
    NEED_PIP=0
  fi
fi

if [[ "$NEED_PIP" = "1" ]]; then
  echo "[post-start] installing adapter requirements into /app/venv"
  docker cp "$REQ_FILE" "$CONTAINER:/tmp/hermes-sqlbot-adapter-requirements.txt" \
    || fail "docker cp requirements"
  docker exec -u root "$CONTAINER" bash -lc '
    set -euo pipefail
    /app/venv/bin/python -m pip install -r /tmp/hermes-sqlbot-adapter-requirements.txt
    chown -R 1000:1000 /app/venv
  ' || fail "pip install hermes-sqlbot-adapter requirements"
  printf '%s\n' "$NEW_HASH" > "$HASH_FILE"
  echo "[post-start] wrote $HASH_FILE"
fi

# Enforce pinned versions (mcp / anyio / httpx)
docker exec "$CONTAINER" /app/venv/bin/python - <<'PY' || fail "dependency version pin check"
import importlib.metadata as m
want = {"mcp": "1.26.0", "anyio": "4.14.2", "httpx": "0.28.1"}
for name, ver in want.items():
    got = m.version(name)
    if got != ver:
        raise SystemExit(f"{name}={got} want={ver}")
    print(f"OK {name}=={ver}")
PY

docker exec -u root "$CONTAINER" bash -lc '
  chown -R 1000:1000 /data/hermes/plugins/hermes-sqlbot-adapter 2>/dev/null || true
  chmod -R u+rwX,g+rwX /data/hermes/plugins/hermes-sqlbot-adapter 2>/dev/null || true
  mkdir -p /data/hermes/sqlbot-adapter/state /data/hermes/sqlbot-adapter/audit
  chown -R 1000:1000 /data/hermes/sqlbot-adapter 2>/dev/null || true
' || true

# Ensure schema exists (idempotent)
docker exec -u hermeswebui \
  -e HERMES_HOME=/data/hermes \
  -e PYTHONPATH=/data/hermes/plugins/hermes-sqlbot-adapter \
  "$CONTAINER" \
  /app/venv/bin/python /data/hermes/plugins/hermes-sqlbot-adapter/scripts/init_state.py \
    --data-dir /data/hermes \
  || fail "init_state.py"

docker exec -u hermeswebui -e HERMES_HOME=/data/hermes "$CONTAINER" bash -lc '
  if [ -x /app/venv/bin/hermes ]; then
    if command -v script >/dev/null 2>&1; then
      script -qfc "/app/venv/bin/hermes plugins enable hermes-sqlbot-adapter" /dev/null 2>/dev/null || true
    else
      /app/venv/bin/hermes plugins enable hermes-sqlbot-adapter 2>/dev/null || true
    fi
  fi
' || true

CLI_OUT="$(
  docker exec -u hermeswebui -e HERMES_HOME=/data/hermes "$CONTAINER" bash -lc '
    if command -v script >/dev/null 2>&1 && [ -x /app/venv/bin/hermes ]; then
      script -qfc "/app/venv/bin/hermes plugins list" /dev/null 2>/dev/null || true
      script -qfc "/app/venv/bin/hermes tools --summary" /dev/null 2>/dev/null || true
    fi
  ' 2>/dev/null || true
)"

if echo "$CLI_OUT" | grep -qiE 'hermes-sqlbot-adapter|finance-bi|Finance-Bi|finance_bi'; then
  echo "[post-start] PASS: plugin/toolset visible in hermes CLI"
else
  echo "WARN: hermes CLI listing did not clearly show finance-bi; continuing with doctor"
fi

if echo "$CLI_OUT" | grep -qiE 'hermes-finance-bi-plugin'; then
  fail "legacy hermes-finance-bi-plugin still visible — must not coexist with adapter"
fi

docker exec "$CONTAINER" bash -lc '
  test -d /data/hermes/sqlbot-adapter/state && touch /data/hermes/sqlbot-adapter/state/.write_probe && rm -f /data/hermes/sqlbot-adapter/state/.write_probe
' || fail "sqlbot-adapter/state not writable"

# Env check (keys only — never print secrets)
INSTANCE_ENV="${INSTANCE_DIR:-}/.env"
if [[ -f "$INSTANCE_ENV" ]]; then
  for key in SQLBOT_MCP_URL SQLBOT_USERNAME SQLBOT_PASSWORD SQLBOT_WORKSPACE_ID SQLBOT_DEFAULT_DATASOURCE_ID SQLBOT_SESSION_ENCRYPTION_KEY; do
    if ! grep -qE "^${key}=" "$INSTANCE_ENV"; then
      fail "env missing $key"
    fi
  done
  MCP_URL="$(grep -E '^SQLBOT_MCP_URL=' "$INSTANCE_ENV" | head -1 | cut -d= -f2- || true)"
  ENC_KEY="$(grep -E '^SQLBOT_SESSION_ENCRYPTION_KEY=' "$INSTANCE_ENV" | head -1 | cut -d= -f2- || true)"
  if [[ -z "$MCP_URL" ]]; then
    fail "SQLBOT_MCP_URL is empty — set SQLBot MCP endpoint then re-run"
  fi
  if [[ -z "$ENC_KEY" ]]; then
    fail "SQLBOT_SESSION_ENCRYPTION_KEY is empty — set Fernet key then re-run"
  fi
else
  fail "instance .env missing"
fi

# Default: MCP initialize + ping only (no mcp_start)
docker exec -u hermeswebui \
  -e HERMES_HOME=/data/hermes \
  -e PYTHONPATH=/data/hermes/plugins/hermes-sqlbot-adapter \
  "$CONTAINER" \
  /app/venv/bin/python /data/hermes/plugins/hermes-sqlbot-adapter/scripts/connection_test.py \
  || fail "MCP initialize/ping failed"

DOCTOR_ARGS=(
  --profile "$PROFILE"
  --instance-dir "${INSTANCE_DIR:-}"
  --data-dir "$DATA_DIR"
  --container "$CONTAINER"
)
if [[ "$DEEP" = "1" ]]; then
  DOCTOR_ARGS+=(--deep)
fi

bash "$PACKAGE_ROOT/bin/doctor.sh" "${DOCTOR_ARGS[@]}" || fail "doctor.sh"

echo "OK: post-start complete for $PROFILE"
exit 0
