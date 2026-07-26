#!/usr/bin/env bash
# Doctor for bi-strategic-office package / instance (PRD v1.11).
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE=""
INSTANCE_DIR=""
DATA_DIR=""
CONTAINER=""
PACKAGE_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --package-only) PACKAGE_ONLY=1; shift ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --instance-dir) INSTANCE_DIR="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --container) CONTAINER="$2"; shift 2 ;;
    --package-root) PACKAGE_ROOT="$2"; shift 2 ;;
    -h|--help)
      echo "usage: doctor.sh --package-only"
      echo "       doctor.sh --profile <p> --data-dir <d> --container <name>"
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
  pass "adapter plugin present under data/hermes/plugins"
else
  fail "adapter plugin missing under $PLUGIN_DIR"
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
    pass "session store dir writable"
  else
    fail "sqlbot-adapter/state not writable"
  fi
else
  fail "sqlbot-adapter/state missing"
fi

if [[ -d "$DATA_DIR/sqlbot-adapter/audit" ]]; then
  if touch "$DATA_DIR/sqlbot-adapter/audit/.write_probe" 2>/dev/null; then
    rm -f "$DATA_DIR/sqlbot-adapter/audit/.write_probe"
    pass "audit dir writable"
  else
    fail "sqlbot-adapter/audit not writable"
  fi
else
  fail "sqlbot-adapter/audit missing"
fi

if [[ -f "$DATA_DIR/sqlbot-adapter/package-state.yaml" ]] || [[ -f "$DATA_DIR/finance-bi/package-state.yaml" ]]; then
  pass "package-state.yaml present"
else
  warn "package-state.yaml missing"
fi

if [[ -f "$INSTANCE_ENV" ]]; then
  for key in SQLBOT_MCP_URL SQLBOT_USERNAME SQLBOT_PASSWORD SQLBOT_WORKSPACE_ID SQLBOT_DEFAULT_DATASOURCE_ID; do
    if grep -qE "^${key}=" "$INSTANCE_ENV"; then
      pass "env has $key"
    else
      fail "env missing $key"
    fi
  done
  MCP_VAL="$(grep -E '^SQLBOT_MCP_URL=' "$INSTANCE_ENV" | head -1 | cut -d= -f2- || true)"
  if [[ -z "$MCP_VAL" ]]; then
    warn "SQLBOT_MCP_URL is empty — ask/followup will return SQLBOT_NOT_CONFIGURED"
  else
    pass "SQLBOT_MCP_URL is set"
    if command -v curl >/dev/null 2>&1; then
      if curl -fsS -o /dev/null --connect-timeout 5 --max-time 15 "$MCP_VAL" 2>/dev/null \
        || curl -fsS -o /dev/null --connect-timeout 5 --max-time 15 -X POST -H 'Content-Type: application/json' -d '{}' "$MCP_VAL" 2>/dev/null; then
        pass "SQLBot MCP address reachable"
      else
        warn "SQLBot MCP address probe inconclusive (auth body may be required)"
      fi
    fi
  fi
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
  CLI_OUT="$(
    docker exec -u hermeswebui -e HERMES_HOME=/data/hermes "$CONTAINER" bash -lc '
      if command -v script >/dev/null 2>&1 && [ -x /app/venv/bin/hermes ]; then
        script -qfc "/app/venv/bin/hermes plugins list" /dev/null 2>/dev/null || true
        script -qfc "/app/venv/bin/hermes tools --summary" /dev/null 2>/dev/null || true
      fi
    ' 2>/dev/null || true
  )"
  if echo "$CLI_OUT" | grep -qiE 'hermes-sqlbot-adapter|finance-bi|Finance-Bi|finance_bi'; then
    pass "Hermes CLI lists finance-bi / adapter"
  else
    warn "Hermes CLI listing empty/unavailable"
  fi
  if echo "$CLI_OUT" | grep -qiE 'hermes-finance-bi-plugin'; then
    fail "Hermes CLI still lists hermes-finance-bi-plugin"
  fi
else
  warn "container not available; skipped runtime plugin checks"
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "doctor.sh: FAILED"
  exit 1
fi
echo "doctor.sh: OK"
exit 0
