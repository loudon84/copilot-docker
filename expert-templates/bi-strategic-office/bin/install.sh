#!/usr/bin/env bash
# Install bi-strategic-office expert package into an instance (PRD v1.10 §14).
# Idempotent. Does NOT start containers or run pip inside containers.
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE=""
INSTANCE_DIR=""
DATA_DIR=""
REPO_ROOT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --instance-dir) INSTANCE_DIR="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --repo-root) REPO_ROOT="$2"; shift 2 ;;
    -h|--help)
      echo "usage: install.sh --profile <p> --instance-dir <d> --data-dir <d> --repo-root <d>"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

step_fail() {
  echo "ERROR: install failed at step: $*" >&2
  exit 1
}

[[ -n "$PROFILE" ]] || step_fail "missing --profile"
[[ -n "$INSTANCE_DIR" ]] || step_fail "missing --instance-dir"
[[ -n "$DATA_DIR" ]] || step_fail "missing --data-dir"
[[ -n "$REPO_ROOT" ]] || step_fail "missing --repo-root"

BASE_TPL="$REPO_ROOT/expert-templates/base"
[[ -d "$BASE_TPL" ]] || step_fail "base template not found: $BASE_TPL"
[[ -f "$PACKAGE_ROOT/expert.yaml" ]] || step_fail "expert.yaml missing in package"

PYTHON_BIN="$(command -v python3 || command -v python || true)"
[[ -n "$PYTHON_BIN" ]] || step_fail "python3/python required for config merge"

echo "[install] package=$PACKAGE_ROOT profile=$PROFILE"

# 1) Validate package
bash "$PACKAGE_ROOT/bin/validate.sh" --package-root "$PACKAGE_ROOT" \
  || step_fail "validate.sh"

# 2) Create runtime directories (never wipe existing state/uploads/exports)
mkdir -p \
  "$DATA_DIR" \
  "$DATA_DIR/finance-bi/semantic" \
  "$DATA_DIR/finance-bi/policies" \
  "$DATA_DIR/finance-bi/state" \
  "$DATA_DIR/finance-bi/cache" \
  "$DATA_DIR/workspace/uploads" \
  "$DATA_DIR/workspace/exports/bi" \
  "$DATA_DIR/workspace/drafts/bi" \
  "$DATA_DIR/workspace/reports/bi" \
  "$DATA_DIR/skills" \
  "$DATA_DIR/plugins" \
  "$DATA_DIR/policies" \
  "$DATA_DIR/tools" \
  "$DATA_DIR/mcp" \
  "$DATA_DIR/memories" \
  || step_fail "create runtime directories"

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$DATA_DIR/.backup/$TS"
mkdir -p "$BACKUP_DIR"

# 3) Backup template assets (not runtime user data)
backup_if_exists() {
  local rel="$1"
  if [[ -e "$DATA_DIR/$rel" ]]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$rel")"
    cp -a "$DATA_DIR/$rel" "$BACKUP_DIR/$rel" 2>/dev/null || true
  fi
}

backup_if_exists "SOUL.md"
backup_if_exists "config.yaml"
backup_if_exists "config.patch.yaml"
backup_if_exists "skills"
backup_if_exists "plugins/hermes-finance-bi-plugin"
backup_if_exists "finance-bi/semantic"
backup_if_exists "finance-bi/policies"
backup_if_exists "memories/MEMORY.md"
# Do NOT backup/touch: .env sessions logs workspace/uploads workspace/exports finance-bi/state finance-bi/cache

# Preserve user MEMORY.md if it already exists (user memory)
PRESERVE_USER_MEMORY=0
if [[ -f "$DATA_DIR/memories/MEMORY.md" ]]; then
  PRESERVE_USER_MEMORY=1
  cp "$DATA_DIR/memories/MEMORY.md" "$BACKUP_DIR/MEMORY.md.user" 2>/dev/null || true
fi

PRESERVE_FULL_CONFIG=0
if [[ -f "$DATA_DIR/config.yaml" ]] && grep -qE '^(model|providers):' "$DATA_DIR/config.yaml" 2>/dev/null; then
  PRESERVE_FULL_CONFIG=1
  echo "[install] detected existing config with model/providers — will deep-merge only"
fi

# 4) Lay base template (selective — avoid wiping runtime dirs)
# Copy base files without removing finance-bi/state etc.
copy_tree_overlay() {
  local src="$1"
  local dst="$2"
  [[ -d "$src" ]] || return 0
  # Use tar-like portable approach via find+cp
  (
    cd "$src"
    find . -type f ! -path './.git/*' ! -name '.env' 2>/dev/null
  ) | while IFS= read -r rel; do
    rel="${rel#./}"
    [[ -z "$rel" ]] && continue
    # Never overwrite protected runtime paths from base overlay
    case "$rel" in
      finance-bi/state/*|finance-bi/cache/*|workspace/uploads/*|workspace/exports/*|sessions/*|logs/*|.env)
        continue
        ;;
    esac
    mkdir -p "$dst/$(dirname "$rel")"
    cp "$src/$rel" "$dst/$rel"
  done
}

echo "[install] overlay base template"
copy_tree_overlay "$BASE_TPL" "$DATA_DIR" || step_fail "overlay base"

# If we preserved full config, restore it before merge
if [[ "$PRESERVE_FULL_CONFIG" = "1" ]] && [[ -f "$BACKUP_DIR/config.yaml" ]]; then
  cp "$BACKUP_DIR/config.yaml" "$DATA_DIR/config.yaml"
fi

# Restore user MEMORY.md after base overlay (base ships a default MEMORY.md)
if [[ "$PRESERVE_USER_MEMORY" = "1" ]] && [[ -f "$BACKUP_DIR/MEMORY.md.user" ]]; then
  mkdir -p "$DATA_DIR/memories"
  cp "$BACKUP_DIR/MEMORY.md.user" "$DATA_DIR/memories/MEMORY.md"
  echo "[install] restored user MEMORY.md after base overlay"
fi

# Ensure config.yaml exists (from base)
if [[ ! -f "$DATA_DIR/config.yaml" ]]; then
  if [[ -f "$BASE_TPL/config.yaml" ]]; then
    cp "$BASE_TPL/config.yaml" "$DATA_DIR/config.yaml"
  else
    step_fail "no config.yaml available"
  fi
fi

# 5) Install runtime assets from package
echo "[install] install SOUL.md"
cp "$PACKAGE_ROOT/runtime/SOUL.md" "$DATA_DIR/SOUL.md" || step_fail "SOUL.md"

echo "[install] install MEMORY.md (default only if missing)"
mkdir -p "$DATA_DIR/memories"
if [[ "$PRESERVE_USER_MEMORY" = "1" ]]; then
  echo "[install] preserving existing user MEMORY.md"
else
  cp "$PACKAGE_ROOT/runtime/memories/MEMORY.md" "$DATA_DIR/memories/MEMORY.md" || step_fail "MEMORY.md"
fi
if [[ -f "$PACKAGE_ROOT/runtime/memories/USER.md" ]] && [[ ! -f "$DATA_DIR/memories/USER.md" ]]; then
  cp "$PACKAGE_ROOT/runtime/memories/USER.md" "$DATA_DIR/memories/USER.md"
fi

echo "[install] install skills"
mkdir -p "$DATA_DIR/skills"
# Remove previous package skill dirs that we manage, then copy fresh
for skill_dir in "$PACKAGE_ROOT/runtime/skills"/*; do
  [[ -d "$skill_dir" ]] || continue
  name="$(basename "$skill_dir")"
  rm -rf "$DATA_DIR/skills/$name"
  cp -R "$skill_dir" "$DATA_DIR/skills/$name" || step_fail "skill $name"
done

echo "[install] install plugin"
PLUGIN_SRC="$PACKAGE_ROOT/plugins/hermes-finance-bi-plugin"
PLUGIN_DST="$DATA_DIR/plugins/hermes-finance-bi-plugin"
mkdir -p "$DATA_DIR/plugins"
rm -rf "$PLUGIN_DST"
mkdir -p "$PLUGIN_DST"
cp -R "$PLUGIN_SRC/." "$PLUGIN_DST/" || step_fail "plugin copy"
# Drop noise from installed plugin
rm -rf "$PLUGIN_DST/tests" "$PLUGIN_DST/__pycache__" 2>/dev/null || true
find "$PLUGIN_DST" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

# 6) Sync semantic + policies
bash "$PACKAGE_ROOT/bin/sync-semantic-catalog.sh" \
  --profile "$PROFILE" \
  --instance-dir "$INSTANCE_DIR" \
  --data-dir "$DATA_DIR" \
  --package-root "$PACKAGE_ROOT" \
  || step_fail "sync-semantic-catalog"

# Also keep a copy of config.patch.yaml for reference
cp "$PACKAGE_ROOT/runtime/config.patch.yaml" "$DATA_DIR/config.patch.yaml"

# 7) Deep-merge config.patch.yaml
echo "[install] merge config.patch.yaml"
"$PYTHON_BIN" "$PACKAGE_ROOT/lib/merge_yaml.py" \
  --config "$DATA_DIR/config.yaml" \
  --patch "$PACKAGE_ROOT/runtime/config.patch.yaml" \
  --inplace \
  --enable-plugin "hermes-finance-bi-plugin" \
  --enable-toolset "finance-bi" \
  || step_fail "merge_yaml"

# Placeholder substitution for __PROFILE__ / __EXPERT__ (skip protected files)
EXPERT_ID="bi-strategic-office"
find "$DATA_DIR" -type f \( -name '*.md' -o -name '*.yaml' -o -name '*.json' \) \
  ! -path '*/finance-bi/state/*' \
  ! -path '*/finance-bi/cache/*' \
  ! -path '*/workspace/uploads/*' \
  ! -path '*/workspace/exports/*' \
  ! -path '*/sessions/*' \
  ! -path '*/.backup/*' \
  -print0 2>/dev/null | while IFS= read -r -d '' file; do
  if grep -q '__PROFILE__\|__EXPERT__\|__HINDSIGHT_API_URL__' "$file" 2>/dev/null; then
    # portable in-place sed
    if sed --version >/dev/null 2>&1; then
      sed -i "s|__PROFILE__|$PROFILE|g; s|__EXPERT__|$EXPERT_ID|g; s|__HINDSIGHT_API_URL__|http://hindsight.superic.com:8888|g" "$file"
    else
      sed -i '' "s|__PROFILE__|$PROFILE|g; s|__EXPERT__|$EXPERT_ID|g; s|__HINDSIGHT_API_URL__|http://hindsight.superic.com:8888|g" "$file" 2>/dev/null \
        || sed -i "s|__PROFILE__|$PROFILE|g; s|__EXPERT__|$EXPERT_ID|g; s|__HINDSIGHT_API_URL__|http://hindsight.superic.com:8888|g" "$file"
    fi
  fi
done

# 8) Idempotent FINANCE_BI_* env placeholders on instance .env (never overwrite secrets blindly)
INSTANCE_ENV="$INSTANCE_DIR/.env"
if [[ -f "$INSTANCE_ENV" ]]; then
  ensure_env() {
    local key="$1"
    local val="$2"
    if ! grep -qE "^${key}=" "$INSTANCE_ENV" 2>/dev/null; then
      printf '%s=%s\n' "$key" "$val" >> "$INSTANCE_ENV"
    fi
  }
  upsert_env() {
    local key="$1"
    local val="$2"
    if grep -qE "^${key}=" "$INSTANCE_ENV" 2>/dev/null; then
      if sed --version >/dev/null 2>&1; then
        sed -i -E "s|^${key}=.*|${key}=${val}|" "$INSTANCE_ENV"
      else
        sed -i.bak -E "s|^${key}=.*|${key}=${val}|" "$INSTANCE_ENV" && rm -f "${INSTANCE_ENV}.bak"
      fi
    else
      printf '%s=%s\n' "$key" "$val" >> "$INSTANCE_ENV"
    fi
  }
  ensure_env "FINANCE_BI_DSN" ""
  ensure_env "FINANCE_BI_DIALECT" "mssql"
  ensure_env "FINANCE_BI_TDS_VERSION" "7.0"
  upsert_env "FINANCE_BI_CHARSET" "cp936"
  ensure_env "FINANCE_BI_CATALOG_PATH" "/data/hermes/finance-bi/semantic"
  ensure_env "FINANCE_BI_POLICY_PATH" "/data/hermes/finance-bi/policies"
  ensure_env "FINANCE_BI_ALLOWED_SCHEMAS" "dbo,bi_finance,bi_sales"
  ensure_env "FINANCE_BI_ALLOWED_ENTITIES" ""
  ensure_env "FINANCE_BI_DEFAULT_CURRENCY" "HKD"
  ensure_env "FINANCE_BI_TIMEZONE" "Asia/Hong_Kong"
  ensure_env "FINANCE_BI_QUERY_TIMEOUT_SECONDS" "30"
  ensure_env "FINANCE_BI_DEFAULT_LIMIT" "200"
  ensure_env "FINANCE_BI_HARD_LIMIT" "5000"
  ensure_env "FINANCE_BI_STATE_DB" "/data/hermes/finance-bi/state/finance_bi.db"
  ensure_env "FINANCE_BI_EXPORT_DIR" "/data/hermes/workspace/exports/bi"
  upsert_env "FINANCE_BI_MASK_SENSITIVE" "false"
  ensure_env "FINANCE_BI_REVEAL_FILTERED_SENSITIVE" "true"
  echo "[install] FINANCE_BI_* placeholders ensured in $INSTANCE_ENV"
else
  echo "WARN: instance .env missing at $INSTANCE_ENV — skipped FINANCE_BI_* placeholders"
fi

# Sync runtime env if helper exists (optional, non-fatal)
if [[ -f "$REPO_ROOT/scripts/sync-runtime-env.sh" ]]; then
  bash "$REPO_ROOT/scripts/sync-runtime-env.sh" "$PROFILE" 2>/dev/null || true
fi

# 9) Write package-state (only on full success)
"$PYTHON_BIN" "$PACKAGE_ROOT/lib/package_state.py" write \
  --data-dir "$DATA_DIR" \
  --package-root "$PACKAGE_ROOT" \
  || step_fail "package_state write"

# Permissions best-effort
chmod 600 "$INSTANCE_ENV" 2>/dev/null || true
chown -R 1000:1000 "$DATA_DIR" 2>/dev/null || true

echo "OK: installed bi-strategic-office into $PROFILE ($DATA_DIR)"
echo "Next: bash scripts/up-instance.sh $PROFILE"
exit 0
