#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:?usage: inject-expert.sh <profile> <expert>}"
EXPERT="${2:?usage: inject-expert.sh <profile> <expert>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$BASE_DIR/instances/$PROFILE/data/hermes"
TPL_BASE="$BASE_DIR/expert-templates/base"
TPL_EXPERT="$BASE_DIR/expert-templates/$EXPERT"
[ -d "$TPL_EXPERT" ] || { echo "Expert template not found: $EXPERT"; exit 1; }

# Team expert pack: delegate to inject-expert-team.sh (PRD v1.8)
if [ -f "$TPL_EXPERT/team.yaml" ]; then
  exec bash "$BASE_DIR/scripts/inject-expert-team.sh" "$PROFILE" "$EXPERT"
fi

mkdir -p "$DATA_DIR" "$DATA_DIR/.backup"
TS="$(date +%Y%m%d-%H%M%S)"

PRESERVE_FULL_CONFIG=0
if [ -f "$DATA_DIR/config.yaml" ] && grep -qE '^(model|providers):' "$DATA_DIR/config.yaml" 2>/dev/null; then
  PRESERVE_FULL_CONFIG=1
  mkdir -p "$DATA_DIR/.backup/$TS"
  cp "$DATA_DIR/config.yaml" "$DATA_DIR/.backup/$TS/config.yaml"
  echo "[config] 检测到完整 config（含 model/providers），将保留并仅合并 runtime 段"
fi

for f in SOUL.md memories/MEMORY.md memories/USER.md hindsight/config.json workspace/AGENTS.md; do
  [ -f "$DATA_DIR/$f" ] && mkdir -p "$DATA_DIR/.backup/$TS/$(dirname "$f")" && cp "$DATA_DIR/$f" "$DATA_DIR/.backup/$TS/$f"
done

if [ "$PRESERVE_FULL_CONFIG" = "0" ]; then
  [ -f "$DATA_DIR/config.yaml" ] && mkdir -p "$DATA_DIR/.backup/$TS" && cp "$DATA_DIR/config.yaml" "$DATA_DIR/.backup/$TS/config.yaml"
fi

for d in skills tools plugins mcp policies skill-bundles gbrain; do
  if [ -d "$DATA_DIR/$d" ]; then
    mkdir -p "$DATA_DIR/.backup/$TS"
    cp -a "$DATA_DIR/$d" "$DATA_DIR/.backup/$TS/$d"
  fi
done

cp -R "$TPL_BASE/." "$DATA_DIR/"
cp -R "$TPL_EXPERT/." "$DATA_DIR/"

if [ "$PRESERVE_FULL_CONFIG" = "1" ]; then
  cp "$DATA_DIR/.backup/$TS/config.yaml" "$DATA_DIR/config.yaml"
fi

find "$DATA_DIR" -type f \( -name '*.md' -o -name '*.yaml' -o -name '*.json' -o -name '.env' \) -print0 | while IFS= read -r -d '' file; do
  if [ "$PRESERVE_FULL_CONFIG" = "1" ] && [ "$file" = "$DATA_DIR/config.yaml" ]; then
    continue
  fi
  sed -i "s|__PROFILE__|$PROFILE|g; s|__EXPERT__|$EXPERT|g; s|__HINDSIGHT_API_URL__|http://hindsight.superic.com:8888|g" "$file"
done

bash "$BASE_DIR/scripts/patch-config-runtime.sh" "$PROFILE"

# Deep-merge config.patch.yaml if present (preserve model/providers)
if [ -f "$DATA_DIR/config.patch.yaml" ] && [ -f "$DATA_DIR/config.yaml" ]; then
  PYTHON_BIN="$(command -v python3 || command -v python || true)"
  if [ -n "$PYTHON_BIN" ]; then
    "$PYTHON_BIN" "$BASE_DIR/scripts/lib/merge_config_patch.py" \
      --config "$DATA_DIR/config.yaml" \
      --patch "$DATA_DIR/config.patch.yaml" \
      --inplace || true
  else
    echo "[config] WARN: python not found; skipped config.patch merge"
  fi
fi

# shellcheck source=lib/init_hermes_dirs.sh
source "$BASE_DIR/scripts/lib/init_hermes_dirs.sh"
init_hermes_dirs "$DATA_DIR"

# BI strategic office: semantic catalog, plugin, env placeholders (PRD v1.9)
if [ "$EXPERT" = "bi-strategic-office" ] || [ -d "$TPL_EXPERT/semantic" ]; then
  bash "$BASE_DIR/scripts/sync-bi-semantic-catalog.sh" "$PROFILE" "$EXPERT"
  PLUGIN_SRC="$BASE_DIR/asset-bundles/hermes-finance-bi-plugin"
  PLUGIN_DST="$DATA_DIR/plugins/hermes-finance-bi-plugin"
  if [ -d "$PLUGIN_SRC" ] && [ -f "$PLUGIN_SRC/plugin.yaml" ]; then
    mkdir -p "$PLUGIN_DST"
    # copy plugin source (exclude tests noise optional)
    cp -R "$PLUGIN_SRC/." "$PLUGIN_DST/"
    rm -rf "$PLUGIN_DST/tests" 2>/dev/null || true
    echo "[bi] installed plugin -> $PLUGIN_DST"
  else
    echo "[bi] WARN: plugin bundle missing: $PLUGIN_SRC"
  fi

  # Hermes plugins are opt-in: must appear in config.yaml plugins.enabled
  PYTHON_BIN="$(command -v python3 || command -v python || true)"
  if [ -n "$PYTHON_BIN" ] && [ -f "$DATA_DIR/config.yaml" ]; then
    "$PYTHON_BIN" "$BASE_DIR/scripts/lib/enable_finance_bi_plugin.py" \
      --config "$DATA_DIR/config.yaml" \
      --plugin hermes-finance-bi-plugin \
      --toolset finance-bi || echo "[bi] WARN: failed to enable plugin in config.yaml"
  else
    echo "[bi] WARN: could not enable plugin in config (missing python or config.yaml)"
  fi
  mkdir -p \
    "$DATA_DIR/finance-bi/state" \
    "$DATA_DIR/workspace/exports/bi" \
    "$DATA_DIR/workspace/drafts/bi" \
    "$DATA_DIR/workspace/reports/bi"

  INSTANCE_ENV="$BASE_DIR/instances/$PROFILE/.env"
  if [ -f "$INSTANCE_ENV" ]; then
    ensure_env() {
      local key="$1"
      local val="$2"
      if ! grep -qE "^${key}=" "$INSTANCE_ENV" 2>/dev/null; then
        printf '%s=%s\n' "$key" "$val" >> "$INSTANCE_ENV"
      fi
    }
    ensure_env "FINANCE_BI_DSN" ""
    ensure_env "FINANCE_BI_DIALECT" "mssql"
    ensure_env "FINANCE_BI_TDS_VERSION" "7.0"
    ensure_env "FINANCE_BI_CATALOG_PATH" "/data/hermes/finance-bi/semantic"
    ensure_env "FINANCE_BI_POLICY_PATH" "/data/hermes/finance-bi/policies"
    ensure_env "FINANCE_BI_ALLOWED_SCHEMAS" "dbo,bi_finance,bi_sales"
    ensure_env "FINANCE_BI_ALLOWED_ENTITIES" ""
    # 空=不按 OU 裁剪。若需限制主体，填真实 ou_code，如 101,104（不是 HK01）
    ensure_env "FINANCE_BI_DEFAULT_CURRENCY" "HKD"
    ensure_env "FINANCE_BI_TIMEZONE" "Asia/Hong_Kong"
    ensure_env "FINANCE_BI_QUERY_TIMEOUT_SECONDS" "30"
    ensure_env "FINANCE_BI_DEFAULT_LIMIT" "200"
    ensure_env "FINANCE_BI_HARD_LIMIT" "5000"
    ensure_env "FINANCE_BI_STATE_DB" "/data/hermes/finance-bi/state/finance_bi.db"
    ensure_env "FINANCE_BI_EXPORT_DIR" "/data/hermes/workspace/exports/bi"
  fi

  CONTAINER="hermes-$PROFILE"
  if docker inspect "$CONTAINER" >/dev/null 2>&1; then
    if [ -f "$PLUGIN_DST/requirements.txt" ]; then
      docker cp "$PLUGIN_DST/requirements.txt" "$CONTAINER:/tmp/hermes-finance-bi-requirements.txt"
      docker exec -u root "$CONTAINER" bash -lc '
        /app/venv/bin/python -m pip install -r /tmp/hermes-finance-bi-requirements.txt
        chown -R 1000:1000 /app/venv
      ' || echo "[bi] WARN: pip install finance-bi requirements failed"
    fi
  fi
fi

chmod 600 "$DATA_DIR/.env" 2>/dev/null || true
bash "$BASE_DIR/scripts/sync-runtime-env.sh" "$PROFILE" 2>/dev/null || true
echo "Injected expert '$EXPERT' into instance '$PROFILE'"
