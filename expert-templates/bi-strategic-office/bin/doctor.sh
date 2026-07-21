#!/usr/bin/env bash
# Doctor for bi-strategic-office package / instance (PRD v1.10 §17).
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

# --- package-only mode ---
if [[ "$PACKAGE_ONLY" = "1" ]]; then
  bash "$PACKAGE_ROOT/bin/validate.sh" --package-root "$PACKAGE_ROOT" || FAIL=1
  PLUGIN="$PACKAGE_ROOT/plugins/hermes-finance-bi-plugin"
  if [[ -f "$PLUGIN/plugin.yaml" ]] && [[ -f "$PLUGIN/__init__.py" ]]; then
    pass "plugin.yaml + __init__.py"
  else
    fail "plugin entry files missing"
  fi
  for tool in finance_bi_ask finance_bi_followup finance_bi_explain finance_bi_catalog_search finance_bi_validate_result finance_bi_export_result; do
    if grep -q "$tool" "$PLUGIN/plugin.yaml" 2>/dev/null; then
      pass "tool listed: $tool"
    else
      fail "tool not listed: $tool"
    fi
  done
  if [[ -d "$PACKAGE_ROOT/runtime/semantic/datasets" ]]; then
    pass "runtime semantic datasets present"
  else
    fail "runtime/semantic/datasets missing"
  fi
  if [[ "$FAIL" -ne 0 ]]; then
    echo "doctor.sh (package-only): FAILED"
    exit 1
  fi
  echo "doctor.sh (package-only): OK"
  exit 0
fi

# --- instance mode ---
if [[ -z "$DATA_DIR" && -n "$PROFILE" ]]; then
  # Best-effort locate when caller only passed profile
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

PLUGIN_DIR="$DATA_DIR/plugins/hermes-finance-bi-plugin"
INSTANCE_ENV="${INSTANCE_DIR:-}/.env"

if [[ -f "$PLUGIN_DIR/plugin.yaml" ]] && [[ -f "$PLUGIN_DIR/__init__.py" ]]; then
  pass "plugin present under data/hermes/plugins"
else
  fail "plugin missing under $PLUGIN_DIR"
fi

if [[ -d "$DATA_DIR/finance-bi/semantic/datasets" ]]; then
  pass "semantic catalog present"
else
  fail "finance-bi/semantic/datasets missing"
fi

if [[ -d "$DATA_DIR/finance-bi/policies" ]]; then
  pass "policies present"
else
  fail "finance-bi/policies missing"
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

if [[ -d "$DATA_DIR/finance-bi/state" ]]; then
  if touch "$DATA_DIR/finance-bi/state/.write_probe" 2>/dev/null; then
    rm -f "$DATA_DIR/finance-bi/state/.write_probe"
    pass "state dir writable"
  else
    fail "state dir not writable"
  fi
else
  fail "finance-bi/state missing"
fi

if [[ -f "$DATA_DIR/finance-bi/package-state.yaml" ]]; then
  pass "package-state.yaml present"
else
  warn "package-state.yaml missing"
fi

# Env keys present (do not print values)
if [[ -f "$INSTANCE_ENV" ]]; then
  for key in FINANCE_BI_DSN FINANCE_BI_DIALECT FINANCE_BI_CATALOG_PATH FINANCE_BI_STATE_DB; do
    if grep -qE "^${key}=" "$INSTANCE_ENV"; then
      pass "env has $key"
    else
      fail "env missing $key"
    fi
  done
  DSN_VAL="$(grep -E '^FINANCE_BI_DSN=' "$INSTANCE_ENV" | head -1 | cut -d= -f2- || true)"
  if [[ -z "$DSN_VAL" ]]; then
    warn "FINANCE_BI_DSN is empty — ask/followup will return DATASOURCE_UNAVAILABLE until configured"
  else
    pass "FINANCE_BI_DSN is set"
  fi
else
  fail "instance .env missing"
fi

# config opt-in
if [[ -f "$DATA_DIR/config.yaml" ]]; then
  if grep -q 'hermes-finance-bi-plugin' "$DATA_DIR/config.yaml"; then
    pass "config.yaml references hermes-finance-bi-plugin"
  else
    fail "config.yaml missing hermes-finance-bi-plugin"
  fi
else
  fail "config.yaml missing"
fi

# Host-side catalog load
export FINANCE_BI_CATALOG_PATH="$DATA_DIR/finance-bi/semantic"
export FINANCE_BI_POLICY_PATH="$DATA_DIR/finance-bi/policies"
export FINANCE_BI_STATE_DB="$DATA_DIR/finance-bi/state/finance_bi.db"
export FINANCE_BI_EXPORT_DIR="$DATA_DIR/workspace/exports/bi"
export FINANCE_BI_DIALECT=sqlite
export FINANCE_BI_DSN="sqlite:///$DATA_DIR/finance-bi/state/doctor_probe.db"
export FINANCE_BI_ALLOWED_ENTITIES=""
export PYTHONPATH="$PLUGIN_DIR${PYTHONPATH:+:$PYTHONPATH}"

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [[ -n "$PYTHON_BIN" ]]; then
  if "$PYTHON_BIN" - <<'PY'
import os, sys
from pathlib import Path
try:
    from finance_bi.catalog import SemanticCatalog
    cat = SemanticCatalog(Path(os.environ["FINANCE_BI_CATALOG_PATH"])).load()
    assert cat.datasets, "no datasets"
    print(f"catalog_ok datasets={len(cat.datasets)} metrics={len(cat.metrics)}")
except Exception as e:
    print(f"catalog_error: {type(e).__name__}: {e}")
    sys.exit(1)
PY
  then
    pass "semantic catalog loads"
  else
    fail "semantic catalog failed to load"
  fi
else
  warn "python not found; skipped catalog load"
fi

# Container checks
if [[ -n "$CONTAINER" ]] && docker inspect "$CONTAINER" >/dev/null 2>&1; then
  STATE="$(docker inspect --format '{{.State.Status}}' "$CONTAINER" 2>/dev/null || echo unknown)"
  if [[ "$STATE" == "running" ]]; then
    pass "container running"
  else
    fail "container state=$STATE"
  fi
  if docker exec "$CONTAINER" bash -lc 'test -f /data/hermes/plugins/hermes-finance-bi-plugin/plugin.yaml'; then
    pass "container sees plugin.yaml"
  else
    fail "container missing plugin.yaml"
  fi
  CLI_OUT="$(
    docker exec -u hermeswebui -e HERMES_HOME=/data/hermes "$CONTAINER" bash -lc '
      if command -v script >/dev/null 2>&1 && [ -x /app/venv/bin/hermes ]; then
        script -qfc "/app/venv/bin/hermes plugins list" /dev/null 2>/dev/null || true
        script -qfc "/app/venv/bin/hermes tools --summary" /dev/null 2>/dev/null || true
      fi
    ' 2>/dev/null || true
  )"
  if echo "$CLI_OUT" | grep -qiE 'hermes-finance-bi|finance-bi|Finance-Bi|finance_bi'; then
    pass "Hermes CLI lists finance-bi"
  else
    warn "Hermes CLI listing empty/unavailable"
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
