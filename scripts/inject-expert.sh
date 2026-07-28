#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:?usage: inject-expert.sh <profile> <expert>}"
EXPERT="${2:?usage: inject-expert.sh <profile> <expert>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$BASE_DIR/instances/$PROFILE/data/hermes"
TPL_BASE="$BASE_DIR/expert-templates/base"
TPL_EXPERT="$BASE_DIR/expert-templates/$EXPERT"
[ -d "$TPL_EXPERT" ] || { echo "Expert template not found: $EXPERT"; exit 1; }

# Expert Factory v2: structure validation before inject
if [ -f "$BASE_DIR/scripts/expert/expert" ]; then
  if ! bash "$BASE_DIR/scripts/expert/expert" validate "$TPL_EXPERT" --level structure --format text; then
    echo "ERROR: expert structure validation failed for $EXPERT"
    exit 1
  fi
  if [ -f "$TPL_EXPERT/expert.yaml" ] && grep -q 'workcopilot.expert.v1' "$TPL_EXPERT/expert.yaml" 2>/dev/null; then
    echo "[expert-factory] using workcopilot.expert.v1 manifest for $EXPERT"
  else
    echo "[expert-factory] WARN: legacy expert template (no workcopilot.expert.v1); continuing inject"
  fi
fi

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

USE_MANIFEST_INJECT=0
if [ -f "$TPL_EXPERT/expert.yaml" ] && grep -q 'workcopilot.expert.v1' "$TPL_EXPERT/expert.yaml" 2>/dev/null; then
  USE_MANIFEST_INJECT=1
fi

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ "$USE_MANIFEST_INJECT" = "1" ] && [ -n "$PYTHON_BIN" ]; then
  echo "[expert-factory] precise inject from workcopilot.expert.v1 manifest"
  # base already copied; inject only declares overlay assets (pass empty base to avoid double)
  "$PYTHON_BIN" "$BASE_DIR/scripts/lib/inject_from_manifest.py" \
    --template "$TPL_EXPERT" \
    --data-dir "$DATA_DIR" \
    || { echo "ERROR: manifest inject failed"; exit 1; }
  # Re-apply base was done above; inject_from_manifest without --base only overlays expert assets.
  # But we need base first then overlay — call again is wrong if inject includes base.
  # Current inject_from_manifest without --base only copies expert assets; good.
else
  if [ "$USE_MANIFEST_INJECT" = "1" ]; then
    echo "[expert-factory] WARN: python missing; falling back to full template copy"
  fi
  cp -R "$TPL_EXPERT/." "$DATA_DIR/"
fi

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

# BI strategic office: semantic catalog + legacy plugin warn (v1.9); v2 prefers sqlbot adapter via manifest
if [ "$EXPERT" = "bi-strategic-office" ] || [ -d "$TPL_EXPERT/semantic" ]; then
  if [ -d "$TPL_EXPERT/semantic" ]; then
    bash "$BASE_DIR/scripts/sync-bi-semantic-catalog.sh" "$PROFILE" "$EXPERT" || true
  fi
  if [ -d "$DATA_DIR/plugins/hermes-sqlbot-adapter" ]; then
    echo "[bi] sqlbot adapter present via manifest inject"
    PYTHON_BIN="$(command -v python3 || command -v python || true)"
    if [ -n "$PYTHON_BIN" ] && [ -f "$DATA_DIR/config.yaml" ]; then
      "$PYTHON_BIN" "$BASE_DIR/scripts/lib/enable_finance_bi_plugin.py" \
        --config "$DATA_DIR/config.yaml" \
        --plugin hermes-sqlbot-adapter \
        --toolset finance-bi 2>/dev/null \
        || echo "[bi] WARN: could not enable hermes-sqlbot-adapter in config.yaml"
    fi
    mkdir -p \
      "$DATA_DIR/sqlbot-adapter/state" \
      "$DATA_DIR/sqlbot-adapter/audit" \
      "$DATA_DIR/workspace/exports/bi" \
      "$DATA_DIR/workspace/uploads"
  else
    PLUGIN_SRC="$BASE_DIR/asset-bundles/hermes-finance-bi-plugin"
    PLUGIN_DST="$DATA_DIR/plugins/hermes-finance-bi-plugin"
    if [ -d "$PLUGIN_SRC" ] && [ -f "$PLUGIN_SRC/plugin.yaml" ]; then
      mkdir -p "$PLUGIN_DST"
      cp -R "$PLUGIN_SRC/." "$PLUGIN_DST/"
      rm -rf "$PLUGIN_DST/tests" 2>/dev/null || true
      echo "[bi] WARN: installed legacy hermes-finance-bi-plugin (prefer hermes-sqlbot-adapter)"
    else
      echo "[bi] WARN: neither sqlbot adapter nor legacy finance-bi plugin found"
    fi
  fi
fi

# Connector slot bind-check (warn only)
if [ -f "$TPL_EXPERT/expert.yaml" ] && grep -q 'connector_slots:' "$TPL_EXPERT/expert.yaml" 2>/dev/null; then
  INSTANCE_ENV="$BASE_DIR/instances/$PROFILE/.env"
  if [ -f "$BASE_DIR/scripts/expert/expert" ]; then
    if [ -f "$INSTANCE_ENV" ]; then
      bash "$BASE_DIR/scripts/expert/expert" bind-check "$TPL_EXPERT" \
        --env-file "$INSTANCE_ENV" --format text \
        || echo "[expert-factory] WARN: connector bind-check reported missing env keys"
    else
      bash "$BASE_DIR/scripts/expert/expert" bind-check "$TPL_EXPERT" --format text \
        || true
    fi
  fi
fi

chmod 600 "$DATA_DIR/.env" 2>/dev/null || true
bash "$BASE_DIR/scripts/sync-runtime-env.sh" "$PROFILE" 2>/dev/null || true
echo "Injected expert '$EXPERT' into instance '$PROFILE'"
