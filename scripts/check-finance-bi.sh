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

# plugins.enabled opt-in (required for Hermes to load the plugin)
if [ -f "$DATA_DIR/config.yaml" ]; then
  if grep -qE 'hermes-finance-bi-plugin' "$DATA_DIR/config.yaml" \
    && grep -A20 -E '^plugins:' "$DATA_DIR/config.yaml" | grep -q 'hermes-finance-bi-plugin'; then
    pass "config.yaml plugins.enabled includes hermes-finance-bi-plugin"
  else
    fail "config.yaml missing plugins.enabled: hermes-finance-bi-plugin (Hermes 默认不加载未 enable 的插件)"
    warn "修复: python3 scripts/lib/enable_finance_bi_plugin.py --config instances/$PROFILE/data/hermes/config.yaml"
    warn "或: docker exec -it $CONTAINER hermes plugins enable hermes-finance-bi-plugin"
  fi
  # If platform_toolsets is a restrictive allow-list, finance-bi must be listed
  if grep -qE '^platform_toolsets:' "$DATA_DIR/config.yaml"; then
    if grep -A40 -E '^platform_toolsets:' "$DATA_DIR/config.yaml" | grep -qE 'finance-bi'; then
      pass "platform_toolsets includes finance-bi"
    else
      fail "platform_toolsets 存在但未包含 finance-bi（白名单会挡住工具）"
      warn "修复: python3 scripts/lib/enable_finance_bi_plugin.py --config instances/$PROFILE/data/hermes/config.yaml && restart"
    fi
  fi
else
  fail "config.yaml missing"
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
# Load as a package (submodule_search_locations) so nested modules resolve;
# __init__.py itself uses absolute imports after sys.path bootstrap.
spec = importlib.util.spec_from_file_location(
    "hermes_finance_bi_plugin",
    plugin / "__init__.py",
    submodule_search_locations=[str(plugin)],
)
mod = importlib.util.module_from_spec(spec)
sys.modules["hermes_finance_bi_plugin"] = mod
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

  # Hermes CLI rejects pipes/non-TTY ("requires an interactive terminal").
  # Doctor primary check: plugin register() importable in container.
  # Optional secondary: fake a TTY via `script` then scan output.
  if docker exec "$CONTAINER" bash -lc '
      export PYTHONPATH=/data/hermes/plugins/hermes-finance-bi-plugin
      /app/venv/bin/python - <<EOF
import importlib.util
import sys
from pathlib import Path
plugin = Path("/data/hermes/plugins/hermes-finance-bi-plugin")
sys.path.insert(0, str(plugin))
spec = importlib.util.spec_from_file_location(
    "hermes_finance_bi_plugin",
    plugin / "__init__.py",
    submodule_search_locations=[str(plugin)],
)
mod = importlib.util.module_from_spec(spec)
sys.modules["hermes_finance_bi_plugin"] = mod
spec.loader.exec_module(mod)
assert callable(mod.register)
print("container_register_ok")
EOF
    '; then
    pass "plugin register() importable in container"
  else
    fail "plugin not importable in container"
  fi

  # Optional CLI listing with fake TTY (script). Do not pipe hermes stdout directly.
  CLI_OUT="$(
    docker exec "$CONTAINER" bash -lc '
      if command -v script >/dev/null 2>&1; then
        script -qfc "hermes tools --summary" /dev/null 2>/dev/null || true
        script -qfc "hermes plugins list" /dev/null 2>/dev/null || true
      else
        # last resort: allocate TTY from docker (may still fail under capture)
        true
      fi
    ' 2>/dev/null || true
  )"
  if echo "$CLI_OUT" | grep -qiE 'finance_bi_ask|finance-bi|hermes-finance-bi'; then
    pass "Hermes CLI lists finance-bi tools (via script TTY)"
  else
    warn "Hermes CLI listing skipped/unavailable (tools 需交互终端；插件 import 已通过即可)"
    warn "人工确认: docker exec -it $CONTAINER hermes tools --summary"
    warn "或: docker exec $CONTAINER bash -lc 'script -qfc \"hermes tools --summary\" /dev/null' | grep finance_bi"
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
