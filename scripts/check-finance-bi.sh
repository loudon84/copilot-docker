#!/usr/bin/env bash
# Doctor for bi-strategic-office / finance-bi plugin (PRD v1.9).
set -euo pipefail

PROFILE="${1:?usage: check-finance-bi.sh <profile>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$BASE_DIR/instances/$PROFILE/data/hermes"
INSTANCE_ENV="$BASE_DIR/instances/$PROFILE/.env"
CONTAINER="hermes-$PROFILE"
PLUGIN_DIR="$DATA_DIR/plugins/hermes-finance-bi-plugin"
FAIL=0

pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; FAIL=1; }
warn() { echo "WARN: $*"; }

[ -d "$DATA_DIR" ] || { echo "ERROR: instance data missing: $DATA_DIR"; exit 1; }

# Plugin files
if [ -f "$PLUGIN_DIR/plugin.yaml" ] && [ -f "$PLUGIN_DIR/__init__.py" ]; then
  pass "plugin.yaml + __init__.py present"
else
  fail "plugin missing under plugins/hermes-finance-bi-plugin (run inject-expert.sh)"
fi

for tool in \
  finance_bi_ask \
  finance_bi_followup \
  finance_bi_explain \
  finance_bi_catalog_search \
  finance_bi_validate_result \
  finance_bi_export_result
do
  if grep -q "$tool" "$PLUGIN_DIR/plugin.yaml" 2>/dev/null; then
    pass "tool listed: $tool"
  else
    fail "tool not listed in plugin.yaml: $tool"
  fi
done

# Semantic catalog
if [ -d "$DATA_DIR/finance-bi/semantic/datasets" ]; then
  pass "semantic catalog present"
else
  fail "finance-bi/semantic/datasets missing"
fi

# Export dir
if [ -d "$DATA_DIR/workspace/exports/bi" ]; then
  pass "export dir present"
  touch "$DATA_DIR/workspace/exports/bi/.write_probe" 2>/dev/null && \
    rm -f "$DATA_DIR/workspace/exports/bi/.write_probe" && \
    pass "export dir writable" || fail "export dir not writable"
else
  fail "workspace/exports/bi missing"
fi

# Env keys
if [ -f "$INSTANCE_ENV" ]; then
  for key in FINANCE_BI_DSN FINANCE_BI_DIALECT FINANCE_BI_CATALOG_PATH FINANCE_BI_ALLOWED_ENTITIES FINANCE_BI_STATE_DB; do
    if grep -qE "^${key}=" "$INSTANCE_ENV"; then
      pass "env has $key"
    else
      fail "env missing $key"
    fi
  done
  DSN_VAL="$(grep -E '^FINANCE_BI_DSN=' "$INSTANCE_ENV" | head -1 | cut -d= -f2- || true)"
  if [ -z "$DSN_VAL" ]; then
    warn "FINANCE_BI_DSN is empty — ask/followup 会返回 DATASOURCE_UNAVAILABLE，直到配置只读 DSN"
  else
    pass "FINANCE_BI_DSN is set"
  fi
else
  fail "instance .env missing"
fi

# Catalog load via host python (no container required)
export FINANCE_BI_CATALOG_PATH="$DATA_DIR/finance-bi/semantic"
export FINANCE_BI_POLICY_PATH="$DATA_DIR/finance-bi/policies"
export FINANCE_BI_STATE_DB="$DATA_DIR/finance-bi/state/finance_bi.db"
export FINANCE_BI_EXPORT_DIR="$DATA_DIR/workspace/exports/bi"
export FINANCE_BI_DIALECT=sqlite
export FINANCE_BI_DSN="sqlite:///$DATA_DIR/finance-bi/state/doctor_probe.db"
export FINANCE_BI_ALLOWED_ENTITIES=HK01
export PYTHONPATH="$PLUGIN_DIR${PYTHONPATH:+:$PYTHONPATH}"

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_BIN" ]; then
  fail "python3/python not found for catalog check"
elif "$PYTHON_BIN" - <<'PY'
import sys
try:
    from finance_bi.catalog import SemanticCatalog
    from pathlib import Path
    import os
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

# Host-side: plugin register() importable
if [ -n "$PYTHON_BIN" ]; then
  if "$PYTHON_BIN" - <<PY
import importlib.util
import sys
from pathlib import Path
plugin = Path(r"$PLUGIN_DIR")
sys.path.insert(0, str(plugin))
spec = importlib.util.spec_from_file_location("hermes_finance_bi_plugin", plugin / "__init__.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
assert callable(getattr(mod, "register", None)), "register() missing"
print("register_ok")
PY
  then
    pass "plugin register() importable on host"
  else
    fail "plugin register() failed to import on host"
  fi
fi

# Container checks
if docker inspect "$CONTAINER" >/dev/null 2>&1; then
  if docker exec "$CONTAINER" bash -lc 'test -f /data/hermes/plugins/hermes-finance-bi-plugin/plugin.yaml'; then
    pass "container sees plugin.yaml"
  else
    fail "container missing /data/hermes/plugins/hermes-finance-bi-plugin/plugin.yaml"
  fi

  if docker exec "$CONTAINER" bash -lc 'test -w /data/hermes/workspace/exports/bi'; then
    pass "container export dir writable"
  else
    fail "container export dir not writable"
  fi

  # Prefer tools --summary (more reliable than plugins list text format)
  TOOLS_OUT="$(docker exec "$CONTAINER" bash -lc 'hermes tools --summary 2>/dev/null || hermes tools 2>/dev/null || true' || true)"
  PLUGINS_OUT="$(docker exec "$CONTAINER" bash -lc 'hermes plugins list 2>/dev/null || true' || true)"
  COMBINED="${TOOLS_OUT}"$'\n'"${PLUGINS_OUT}"

  if echo "$COMBINED" | grep -qiE 'finance_bi_ask|finance-bi|hermes-finance-bi'; then
    pass "Hermes runtime exposes finance-bi tools/plugin"
  else
    # Fallback: prove Python can load plugin inside container venv
    if docker exec "$CONTAINER" bash -lc '
      export PYTHONPATH=/data/hermes/plugins/hermes-finance-bi-plugin
      /app/venv/bin/python - <<EOF
import importlib.util
from pathlib import Path
p = Path("/data/hermes/plugins/hermes-finance-bi-plugin/__init__.py")
spec = importlib.util.spec_from_file_location("hermes_finance_bi_plugin", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
assert callable(mod.register)
print("container_register_ok")
EOF
    '; then
      warn "plugin code loads in container, but hermes CLI did not list finance-bi yet"
      warn "→ 执行: bash scripts/inject-expert.sh $PROFILE bi-strategic-office && bash scripts/restart-instance.sh $PROFILE"
      warn "→ 再查: docker exec $CONTAINER hermes tools --summary | grep finance_bi"
    else
      fail "plugin neither listed by hermes nor importable in container"
    fi
  fi

  # Env inside Hermes home
  if docker exec "$CONTAINER" bash -lc 'grep -qE "^FINANCE_BI_CATALOG_PATH=" /data/hermes/.env 2>/dev/null'; then
    pass "container /data/hermes/.env has FINANCE_BI_CATALOG_PATH"
  else
    warn "container /data/hermes/.env missing FINANCE_BI_* — run: bash scripts/sync-runtime-env.sh $PROFILE && restart"
  fi
else
  warn "container $CONTAINER not running; skipped runtime plugin checks"
fi

if [ "$FAIL" -ne 0 ]; then
  echo "check-finance-bi: FAILED"
  exit 1
fi
echo "check-finance-bi: OK"
exit 0
