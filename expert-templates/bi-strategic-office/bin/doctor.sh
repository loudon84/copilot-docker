#!/usr/bin/env bash
# Doctor for bi-strategic-office package / instance (PRD v1.11.1 hotfix).
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE=""
INSTANCE_DIR=""
DATA_DIR=""
CONTAINER=""
PACKAGE_ONLY=0
DEEP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --package-only) PACKAGE_ONLY=1; shift ;;
    --deep) DEEP=1; shift ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --instance-dir) INSTANCE_DIR="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --container) CONTAINER="$2"; shift 2 ;;
    --package-root) PACKAGE_ROOT="$2"; shift 2 ;;
    -h|--help)
      echo "usage: doctor.sh --package-only"
      echo "       doctor.sh --profile <p> [--data-dir <d>] [--container <name>] [--deep]"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

FAIL=0
pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; FAIL=1; }
warn() { echo "WARN: $*"; }

if [[ "$PACKAGE_ONLY" = "1" ]]; then
  bash "$PACKAGE_ROOT/bin/validate.sh" --package-root "$PACKAGE_ROOT" || FAIL=1
  PLUGIN="$PACKAGE_ROOT/plugins/hermes-sqlbot-adapter"
  if [[ -f "$PLUGIN/plugin.yaml" ]] && [[ -f "$PLUGIN/__init__.py" ]]; then
    pass "plugin.yaml + __init__.py"
  else
    fail "plugin entry files missing"
  fi
  for tool in finance_bi_ask finance_bi_followup finance_bi_explain finance_bi_reset; do
    if grep -q "$tool" "$PLUGIN/plugin.yaml" 2>/dev/null; then
      pass "tool listed: $tool"
    else
      fail "tool not listed: $tool"
    fi
  done
  if grep -q 'SQLBOT_SESSION_ENCRYPTION_KEY' "$PLUGIN/plugin.yaml" 2>/dev/null; then
    pass "plugin requires SQLBOT_SESSION_ENCRYPTION_KEY"
  else
    fail "plugin.yaml missing SQLBOT_SESSION_ENCRYPTION_KEY"
  fi
  if [[ -d "$PACKAGE_ROOT/plugins/hermes-finance-bi-plugin" ]]; then
    fail "legacy hermes-finance-bi-plugin must not remain in package"
  else
    pass "legacy finance-bi plugin absent"
  fi
  if [[ -f "$PACKAGE_ROOT/config/sqlbot.example.env" ]]; then
    pass "config/sqlbot.example.env present"
  else
    fail "config/sqlbot.example.env missing"
  fi
  if [[ -f "$PACKAGE_ROOT/plugins/hermes-sqlbot-adapter/scripts/init_state.py" ]]; then
    pass "init_state.py present"
  else
    fail "init_state.py missing"
  fi
  if [[ -f "$PACKAGE_ROOT/memories/test_sqlbot.py" ]]; then
    fail "duplicate memories/test_sqlbot.py must be removed"
  else
    pass "no duplicate MCP test script under memories/"
  fi
  VER="$(tr -d ' \n\r' < "$PACKAGE_ROOT/VERSION" 2>/dev/null || true)"
  if [[ "$VER" == "1.11.1" ]]; then
    pass "VERSION=1.11.1"
  else
    fail "VERSION expected 1.11.1, got '$VER'"
  fi
  if [[ "$FAIL" -ne 0 ]]; then
    echo "doctor.sh (package-only): FAILED"
    exit 1
  fi
  echo "doctor.sh (package-only): OK"
  exit 0
fi

if [[ -z "$DATA_DIR" && -n "$PROFILE" ]]; then
  REPO_GUESS="$(cd "$PACKAGE_ROOT/../.." && pwd)"
  DATA_DIR="$REPO_GUESS/instances/$PROFILE/data/hermes"
fi
[[ -n "$DATA_DIR" ]] || { echo "ERROR: --data-dir or --profile required" >&2; exit 1; }
[[ -d "$DATA_DIR" ]] || { echo "ERROR: data dir missing: $DATA_DIR" >&2; exit 1; }

if [[ -z "$CONTAINER" && -n "$PROFILE" ]]; then
  CONTAINER="hermes-$PROFILE"
fi
if [[ -z "$INSTANCE_DIR" && -n "$PROFILE" ]]; then
  INSTANCE_DIR="$(cd "$DATA_DIR/../.." && pwd)"
fi

PLUGIN_DIR="$DATA_DIR/plugins/hermes-sqlbot-adapter"
INSTANCE_ENV="${INSTANCE_DIR:-}/.env"

if [[ -f "$PLUGIN_DIR/plugin.yaml" ]] && [[ -f "$PLUGIN_DIR/__init__.py" ]]; then
  pass "Adapter plugin installed"
else
  fail "Adapter plugin missing under $PLUGIN_DIR"
fi

if [[ -d "$DATA_DIR/plugins/hermes-finance-bi-plugin" ]]; then
  fail "legacy hermes-finance-bi-plugin still installed — remove it"
else
  pass "legacy finance-bi plugin not installed"
fi

if [[ -d "$DATA_DIR/workspace/exports/bi" ]]; then
  if touch "$DATA_DIR/workspace/exports/bi/.write_probe" 2>/dev/null; then
    rm -f "$DATA_DIR/workspace/exports/bi/.write_probe"
    pass "export dir writable"
  else
    fail "export dir not writable"
  fi
else
  fail "workspace/exports/bi missing"
fi

if [[ -d "$DATA_DIR/sqlbot-adapter/state" ]]; then
  if touch "$DATA_DIR/sqlbot-adapter/state/.write_probe" 2>/dev/null; then
    rm -f "$DATA_DIR/sqlbot-adapter/state/.write_probe"
    pass "Session store writable"
  else
    fail "sqlbot-adapter/state not writable"
  fi
else
  fail "sqlbot-adapter/state missing"
fi

if [[ -d "$DATA_DIR/sqlbot-adapter/audit" ]]; then
  if touch "$DATA_DIR/sqlbot-adapter/audit/.write_probe" 2>/dev/null; then
    rm -f "$DATA_DIR/sqlbot-adapter/audit/.write_probe"
    pass "Audit directory writable"
  else
    fail "sqlbot-adapter/audit not writable"
  fi
else
  fail "sqlbot-adapter/audit missing"
fi

if [[ -f "$DATA_DIR/sqlbot-adapter/package-state.yaml" ]]; then
  pass "package-state.yaml present"
  if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
    PY="$(command -v python3 || command -v python)"
    if "$PY" - <<PY
import yaml
from pathlib import Path
p = Path(r"$DATA_DIR") / "sqlbot-adapter" / "package-state.yaml"
data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
sv = data.get("schema_version")
ev = str(data.get("expert_version") or "")
if sv != 2:
    raise SystemExit(f"schema_version={sv} expected 2")
if ev != "1.11.1":
    raise SystemExit(f"expert_version={ev} expected 1.11.1")
PY
    then
      pass "package-state schema_version=2 / expert_version=1.11.1"
    else
      warn "package-state schema/version mismatch (re-run install/update)"
    fi
  fi
else
  warn "package-state.yaml missing"
fi

REQUIRED_ENV_KEYS=(
  SQLBOT_MCP_URL
  SQLBOT_USERNAME
  SQLBOT_PASSWORD
  SQLBOT_WORKSPACE_ID
  SQLBOT_DEFAULT_DATASOURCE_ID
  SQLBOT_SESSION_ENCRYPTION_KEY
)

if [[ -f "$INSTANCE_ENV" ]]; then
  ENV_OK=1
  for key in "${REQUIRED_ENV_KEYS[@]}"; do
    if grep -qE "^${key}=" "$INSTANCE_ENV"; then
      :
    else
      fail "env missing $key"
      ENV_OK=0
    fi
  done
  if [[ "$ENV_OK" = "1" ]]; then
    pass "SQLBot env configured (keys present)"
  fi
  # Values: check non-empty for critical ones without printing secrets
  for key in SQLBOT_MCP_URL SQLBOT_SESSION_ENCRYPTION_KEY; do
    VAL="$(grep -E "^${key}=" "$INSTANCE_ENV" | head -1 | cut -d= -f2- || true)"
    if [[ -z "$VAL" ]]; then
      fail "$key is empty"
    else
      pass "$key is set"
    fi
  done
else
  fail "instance .env missing"
fi

if [[ -f "$DATA_DIR/config.yaml" ]]; then
  if grep -q 'hermes-sqlbot-adapter' "$DATA_DIR/config.yaml"; then
    pass "config.yaml references hermes-sqlbot-adapter"
  else
    fail "config.yaml missing hermes-sqlbot-adapter"
  fi
  if grep -q 'hermes-finance-bi-plugin' "$DATA_DIR/config.yaml"; then
    fail "config.yaml still references hermes-finance-bi-plugin"
  else
    pass "legacy plugin not enabled in config"
  fi
else
  fail "config.yaml missing"
fi

run_in_container_py() {
  local script="$1"
  shift
  docker exec -u hermeswebui \
    -e HERMES_HOME=/data/hermes \
    -e PYTHONPATH=/data/hermes/plugins/hermes-sqlbot-adapter \
    "$CONTAINER" \
    /app/venv/bin/python "/data/hermes/plugins/hermes-sqlbot-adapter/scripts/$script" "$@"
}

if [[ -n "$CONTAINER" ]] && docker inspect "$CONTAINER" >/dev/null 2>&1; then
  STATE="$(docker inspect --format '{{.State.Status}}' "$CONTAINER" 2>/dev/null || echo unknown)"
  if [[ "$STATE" == "running" ]]; then
    pass "container running"
  else
    fail "container state=$STATE"
  fi
  if docker exec "$CONTAINER" bash -lc 'test -f /data/hermes/plugins/hermes-sqlbot-adapter/plugin.yaml'; then
    pass "container sees adapter plugin.yaml"
  else
    fail "container missing adapter plugin.yaml"
  fi

  # Dependency version pins
  DEP_OUT="$(
    docker exec "$CONTAINER" /app/venv/bin/python - <<'PY' 2>/dev/null || true
import importlib.metadata as m
want = {"mcp": "1.26.0", "anyio": "4.14.2", "httpx": "0.28.1"}
ok = True
for name, ver in want.items():
    try:
        got = m.version(name)
    except Exception:
        print(f"MISSING {name}")
        ok = False
        continue
    if got != ver:
        print(f"MISMATCH {name}={got} want={ver}")
        ok = False
    else:
        print(f"OK {name}=={ver}")
raise SystemExit(0 if ok else 1)
PY
  )"
  if echo "$DEP_OUT" | grep -q '^MISMATCH\|^MISSING'; then
    fail "dependency versions: $DEP_OUT"
  elif [[ -n "$DEP_OUT" ]]; then
    pass "pinned deps mcp/anyio/httpx"
  else
    warn "dependency version check unavailable"
  fi

  CLI_OUT="$(
    docker exec -u hermeswebui -e HERMES_HOME=/data/hermes "$CONTAINER" bash -lc '
      if command -v script >/dev/null 2>&1 && [ -x /app/venv/bin/hermes ]; then
        script -qfc "/app/venv/bin/hermes plugins list" /dev/null 2>/dev/null || true
        script -qfc "/app/venv/bin/hermes tools --summary" /dev/null 2>/dev/null || true
      fi
    ' 2>/dev/null || true
  )"
  if echo "$CLI_OUT" | grep -qiE 'hermes-sqlbot-adapter|finance-bi|Finance-Bi|finance_bi'; then
    pass "Finance-Bi toolset registered"
  else
    warn "Hermes CLI listing empty/unavailable"
  fi
  if echo "$CLI_OUT" | grep -qiE 'hermes-finance-bi-plugin'; then
    fail "Hermes CLI still lists hermes-finance-bi-plugin"
  fi

  # Default: MCP initialize + ping (no mcp_start / no chat_id)
  if MCP_OUT="$(run_in_container_py connection_test.py 2>&1)"; then
    pass "MCP initialize"
    pass "MCP ping"
  else
    if echo "$MCP_OUT" | grep -q 'SQLBOT_INITIALIZE_FAILED\|INITIALIZE'; then
      fail "MCP initialize — $MCP_OUT"
    elif echo "$MCP_OUT" | grep -q 'TRANSPORT\|network\|SSE\|unreachable\|Connect'; then
      fail "SQLBot MCP endpoint reachable — $MCP_OUT"
    else
      fail "SQLBot MCP — $MCP_OUT"
    fi
  fi

  # tools/list is WARN-only
  if LIST_OUT="$(run_in_container_py connection_test.py --list-tools 2>&1)"; then
    if echo "$LIST_OUT" | grep -qi 'WARN\|empty\|incompatible'; then
      warn "MCP tools/list incompatible or empty"
    else
      pass "MCP tools/list (debug only)"
    fi
  else
    warn "MCP tools/list incompatible"
  fi

  if [[ "$DEEP" = "1" ]]; then
    echo "[doctor] --deep: mcp_start + workspace/datasource (+ optional question)"
    if DEEP_OUT="$(run_in_container_py direct_flow_test.py --skip-question 2>&1)"; then
      pass "mcp_start"
      pass "workspace access"
      pass "datasource access"
      # Optional SQL probe (may FAIL with datasource session error — still FAIL per PRD)
      if Q_OUT="$(run_in_container_py direct_flow_test.py 2>&1)"; then
        pass "SQL execution"
      else
        CODE="$(echo "$Q_OUT" | grep -oE 'SQLBOT_[A-Z_]+|L5 FAIL[^:]*:[[:space:]]*[A-Z_]+' | head -1 || true)"
        fail "SQL execution — code: ${CODE:-unknown}; $Q_OUT"
      fi
    else
      if echo "$DEEP_OUT" | grep -q 'AUTH'; then
        fail "mcp_start / auth — $DEEP_OUT"
      else
        fail "deep probe — $DEEP_OUT"
      fi
    fi
  fi
else
  warn "container not available; skipped runtime MCP checks"
  if [[ "$DEEP" = "1" ]]; then
    fail "--deep requires a running container"
  fi
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "doctor.sh: FAILED"
  exit 1
fi
echo "doctor.sh: OK"
exit 0
