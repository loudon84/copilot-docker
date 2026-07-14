#!/usr/bin/env bash
# Inject a Hermes profile-team expert pack (PRD v1.8).
# Usage: inject-expert-team.sh <instance> <expert>
#
# Stages into .backup/<ts>/staging, validates, then promotes atomically.
# On failure: non-zero exit, online files unchanged, staging retained.

set -euo pipefail

PROFILE="${1:?usage: inject-expert-team.sh <instance> <expert>}"
EXPERT="${2:?usage: inject-expert-team.sh <instance> <expert>}"

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$BASE_DIR/instances/$PROFILE/data/hermes"
TPL_BASE="$BASE_DIR/expert-templates/base"
TPL_EXPERT="$BASE_DIR/expert-templates/$EXPERT"
TEAM_YAML="$TPL_EXPERT/team.yaml"
MANIFEST_PY="$BASE_DIR/scripts/lib/team_manifest.py"
ENV_FILE="$BASE_DIR/instances/$PROFILE/.env"

# Allow tests to inject a fixture template root without polluting expert-templates/
if [ -n "${TEAM_TEMPLATE_ROOT:-}" ]; then
  TPL_EXPERT="$TEAM_TEMPLATE_ROOT"
  TEAM_YAML="$TPL_EXPERT/team.yaml"
fi

die() { echo "ERROR: $*" >&2; exit 1; }

[ -f "$TEAM_YAML" ] || die "team.yaml not found: $TEAM_YAML"
[ -d "$TPL_BASE" ] || die "base template missing: $TPL_BASE"
[ -f "$ENV_FILE" ] || die "missing env file: $ENV_FILE (run create-instance.sh first)"

# Prefer python3, fall back to python (Windows Git Bash / some hosts)
PYTHON=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  die "python3/python not found"
fi

mkdir -p "$DATA_DIR" "$DATA_DIR/.backup"
TS="$(date +%Y%m%d-%H%M%S)"
STAGING="$DATA_DIR/.backup/$TS/staging"
BACKUP_ID="$DATA_DIR/.backup/$TS"
mkdir -p "$STAGING" "$BACKUP_ID"

echo "[team] validating manifest..."
VALIDATE_JSON="$("$PYTHON" "$MANIFEST_PY" validate "$TEAM_YAML" --template-root "$TPL_EXPERT")"
echo "$VALIDATE_JSON" | "$PYTHON" -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('ok') else 1)" \
  || die "manifest validation failed: $VALIDATE_JSON"

RESOLVE_JSON="$("$PYTHON" "$MANIFEST_PY" resolve "$TEAM_YAML" --instance "$PROFILE" --template-root "$TPL_EXPERT" --hermes-home "$DATA_DIR")"
echo "$RESOLVE_JSON" | "$PYTHON" -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('ok') else 1)" \
  || die "manifest resolve failed: $RESOLVE_JSON"

# Extract member ids and banks via Python
mapfile -t MEMBER_IDS < <(echo "$RESOLVE_JSON" | "$PYTHON" -c "
import sys, json
d = json.load(sys.stdin)
for m in d['manifest']['members']:
    print(m['id'])
")

# Backup existing identity files (root + members) before mutation
backup_if_exists() {
  local src="$1"
  local rel="$2"
  if [ -e "$src" ]; then
    mkdir -p "$BACKUP_ID/$(dirname "$rel")"
    cp -a "$src" "$BACKUP_ID/$rel"
  fi
}

PRESERVE_FULL_CONFIG=0
if [ -f "$DATA_DIR/config.yaml" ] && grep -qE '^(model|providers):' "$DATA_DIR/config.yaml" 2>/dev/null; then
  PRESERVE_FULL_CONFIG=1
  echo "[config] 检测到完整 root config（含 model/providers），将保留并仅合并 runtime 段"
fi

backup_if_exists "$DATA_DIR/SOUL.md" "SOUL.md"
backup_if_exists "$DATA_DIR/config.yaml" "config.yaml"
backup_if_exists "$DATA_DIR/memories" "memories"
backup_if_exists "$DATA_DIR/workspace/AGENTS.md" "workspace/AGENTS.md"
backup_if_exists "$DATA_DIR/team.yaml" "team.yaml"
backup_if_exists "$DATA_DIR/skills" "skills"
backup_if_exists "$DATA_DIR/plugins" "plugins"
for mid in "${MEMBER_IDS[@]}"; do
  backup_if_exists "$DATA_DIR/profiles/$mid" "profiles/$mid"
done

# --- Build staging tree (never mutate online until staging is complete) ---
echo "[team] building staging at $STAGING"

# Root: base then team root template
mkdir -p "$STAGING/root"
cp -R "$TPL_BASE/." "$STAGING/root/"
ROOT_TPL="$(echo "$RESOLVE_JSON" | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin)['manifest']['root']['template'])")"
cp -R "$TPL_EXPERT/$ROOT_TPL/." "$STAGING/root/"

# Named profiles
mkdir -p "$STAGING/profiles"
for mid in "${MEMBER_IDS[@]}"; do
  member_tpl="$(echo "$RESOLVE_JSON" | "$PYTHON" -c "
import sys, json
d = json.load(sys.stdin)
for m in d['manifest']['members']:
    if m['id'] == '$mid':
        print(m['template'])
        break
")"
  mkdir -p "$STAGING/profiles/$mid"
  cp -R "$TPL_BASE/." "$STAGING/profiles/$mid/"
  cp -R "$TPL_EXPERT/$member_tpl/." "$STAGING/profiles/$mid/"
done

# Shared context
SHARED_REL="$(echo "$RESOLVE_JSON" | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin)['manifest']['shared_context']['host_relative_path'])")"
mkdir -p "$STAGING/shared"
if [ -d "$TPL_EXPERT/shared" ]; then
  cp -R "$TPL_EXPERT/shared/." "$STAGING/shared/"
fi

# Team skills / plugins (installed on root)
mkdir -p "$STAGING/root/skills" "$STAGING/root/plugins"
if [ -d "$TPL_EXPERT/skills" ]; then
  cp -R "$TPL_EXPERT/skills/." "$STAGING/root/skills/"
fi
if [ -d "$TPL_EXPERT/plugins" ]; then
  cp -R "$TPL_EXPERT/plugins/." "$STAGING/root/plugins/"
fi

# Write resolved runtime team.yaml into staging (not active until promote)
echo "$RESOLVE_JSON" | "$PYTHON" -c "
import sys, json, yaml
from pathlib import Path
d = json.load(sys.stdin)
manifest = d['manifest']
Path(r'''$STAGING/team.yaml''').write_text(
    yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
    encoding='utf-8',
)
"

# Placeholder substitution in staging
HINDSIGHT_API_URL="http://hindsight.superic.com:8888"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
  HINDSIGHT_API_URL="${HINDSIGHT_API_URL:-http://hindsight.superic.com:8888}"
fi

substitute_placeholders() {
  local dir="$1"
  find "$dir" -type f \( -name '*.md' -o -name '*.yaml' -o -name '*.yml' -o -name '*.json' -o -name '.env' \) -print0 \
    | while IFS= read -r -d '' file; do
        sed -i.bak \
          -e "s|__PROFILE__|$PROFILE|g" \
          -e "s|__EXPERT__|$EXPERT|g" \
          -e "s|__HINDSIGHT_API_URL__|$HINDSIGHT_API_URL|g" \
          -e "s|__INSTANCE__|$PROFILE|g" \
          "$file"
        rm -f "${file}.bak"
      done
}

substitute_placeholders "$STAGING"

# Apply runtime patches inside staging configs
bank_for() {
  local pid="$1"
  echo "$RESOLVE_JSON" | "$PYTHON" -c "
import sys, json
print(json.load(sys.stdin)['manifest']['banks']['$pid'])
"
}

# Root patch
bash "$BASE_DIR/scripts/patch-config-runtime.sh" "$PROFILE" \
  --config "$STAGING/root/config.yaml" \
  --profile-home /data/hermes \
  --workspace-path /data/hermes/workspace \
  --vault-path /data/hermes/obsidian-vault \
  --gbrain-home /data/hermes/gbrain \
  --hindsight-bank-id "$(bank_for default)" \
  --kanban-dispatcher on \
  --enable-delegation 1

# Preserve root model/providers if requested
if [ "$PRESERVE_FULL_CONFIG" = "1" ] && [ -f "$BACKUP_ID/config.yaml" ]; then
  "$PYTHON" - <<PY
import yaml
from pathlib import Path
online = yaml.safe_load(Path(r'''$BACKUP_ID/config.yaml''').read_text(encoding='utf-8')) or {}
staged = yaml.safe_load(Path(r'''$STAGING/root/config.yaml''').read_text(encoding='utf-8')) or {}
for key in ('model', 'providers'):
    if key in online:
        staged[key] = online[key]
Path(r'''$STAGING/root/config.yaml''').write_text(
    yaml.safe_dump(staged, allow_unicode=True, sort_keys=False),
    encoding='utf-8',
)
print('[config] restored model/providers onto staged root config')
PY
fi

for mid in "${MEMBER_IDS[@]}"; do
  # Preserve per-member model/providers if present
  MEMBER_PRESERVE=0
  if [ -f "$DATA_DIR/profiles/$mid/config.yaml" ] && grep -qE '^(model|providers):' "$DATA_DIR/profiles/$mid/config.yaml" 2>/dev/null; then
    MEMBER_PRESERVE=1
    cp "$DATA_DIR/profiles/$mid/config.yaml" "$BACKUP_ID/profiles/$mid/config.yaml.full" 2>/dev/null || true
  fi

  bash "$BASE_DIR/scripts/patch-config-runtime.sh" "$PROFILE" \
    --config "$STAGING/profiles/$mid/config.yaml" \
    --profile-home "/data/hermes/profiles/$mid" \
    --workspace-path "/data/hermes/profiles/$mid/workspace" \
    --vault-path "/data/hermes/profiles/$mid/obsidian-vault" \
    --gbrain-home "/data/hermes/profiles/$mid/gbrain" \
    --hindsight-bank-id "$(bank_for "$mid")" \
    --kanban-dispatcher off \
    --enable-delegation 0

  if [ "$MEMBER_PRESERVE" = "1" ]; then
    "$PYTHON" - <<PY
import yaml
from pathlib import Path
online = yaml.safe_load(Path(r'''$DATA_DIR/profiles/$mid/config.yaml''').read_text(encoding='utf-8')) or {}
staged = yaml.safe_load(Path(r'''$STAGING/profiles/$mid/config.yaml''').read_text(encoding='utf-8')) or {}
for key in ('model', 'providers'):
    if key in online:
        staged[key] = online[key]
# Also inherit root model/providers when member has none
root = yaml.safe_load(Path(r'''$STAGING/root/config.yaml''').read_text(encoding='utf-8')) or {}
for key in ('model', 'providers'):
    if key not in staged and key in root:
        staged[key] = root[key]
Path(r'''$STAGING/profiles/$mid/config.yaml''').write_text(
    yaml.safe_dump(staged, allow_unicode=True, sort_keys=False),
    encoding='utf-8',
)
PY
  else
    # Inherit root model/providers for new members
    "$PYTHON" - <<PY
import yaml
from pathlib import Path
staged = yaml.safe_load(Path(r'''$STAGING/profiles/$mid/config.yaml''').read_text(encoding='utf-8')) or {}
root = yaml.safe_load(Path(r'''$STAGING/root/config.yaml''').read_text(encoding='utf-8')) or {}
changed = False
for key in ('model', 'providers'):
    if key not in staged and key in root:
        staged[key] = root[key]
        changed = True
if changed:
    Path(r'''$STAGING/profiles/$mid/config.yaml''').write_text(
        yaml.safe_dump(staged, allow_unicode=True, sort_keys=False),
        encoding='utf-8',
    )
PY
  fi
done

# Structure check on staging before promote
structure_ok=1
for req in SOUL.md config.yaml memories/MEMORY.md memories/USER.md workspace/AGENTS.md; do
  [ -f "$STAGING/root/$req" ] || { echo "ERROR: staging root missing $req" >&2; structure_ok=0; }
done
for mid in "${MEMBER_IDS[@]}"; do
  for req in SOUL.md config.yaml memories/MEMORY.md memories/USER.md workspace/AGENTS.md; do
    [ -f "$STAGING/profiles/$mid/$req" ] || { echo "ERROR: staging profile $mid missing $req" >&2; structure_ok=0; }
  done
done
[ -f "$STAGING/team.yaml" ] || { echo "ERROR: staging missing team.yaml" >&2; structure_ok=0; }
[ "$structure_ok" = "1" ] || die "staging structure validation failed (staging retained at $STAGING)"

# --- Promote staging to online ---
echo "[team] promoting staging → online"

# shellcheck source=lib/init_hermes_dirs.sh
source "$BASE_DIR/scripts/lib/init_hermes_dirs.sh"

# Root files (exclude team.yaml until end so we never leave a half-active manifest)
rsync -a --exclude 'team.yaml' "$STAGING/root/" "$DATA_DIR/" 2>/dev/null || {
  # fallback without rsync
  cp -R "$STAGING/root/." "$DATA_DIR/"
}

# Named profiles
mkdir -p "$DATA_DIR/profiles"
for mid in "${MEMBER_IDS[@]}"; do
  mkdir -p "$DATA_DIR/profiles/$mid"
  cp -R "$STAGING/profiles/$mid/." "$DATA_DIR/profiles/$mid/"
  init_hermes_dirs "$DATA_DIR/profiles/$mid"
done

# Shared context (read-only for runtime)
mkdir -p "$DATA_DIR/$SHARED_REL"
# Re-inject: unlock previous read-only shared files so copy can overwrite
find "$DATA_DIR/$SHARED_REL" -type f -exec chmod u+w {} + 2>/dev/null || true
cp -R "$STAGING/shared/." "$DATA_DIR/$SHARED_REL/"
# Files: read-only for all; keep directory owner-writable for re-inject
find "$DATA_DIR/$SHARED_REL" -type f -exec chmod a=r {} + 2>/dev/null || true
chmod u+rwx "$DATA_DIR/$SHARED_REL" 2>/dev/null || true
find "$DATA_DIR/$SHARED_REL" -mindepth 1 -type d -exec chmod u+rwx,go+rx {} + 2>/dev/null || true

# Kanban board dir
mkdir -p "$DATA_DIR/kanban"
init_hermes_dirs "$DATA_DIR"

# CEO decision paths
mkdir -p \
  "$DATA_DIR/workspace/reports/ceo/decisions" \
  "$DATA_DIR/obsidian-vault/60-Reports/CEO-Decisions"

# Activate resolved team.yaml last
cp "$STAGING/team.yaml" "$DATA_DIR/team.yaml"

# Mark staging complete
echo "promoted_at=$TS" > "$STAGING/.promoted"

bash "$BASE_DIR/scripts/sync-runtime-env.sh" "$PROFILE" 2>/dev/null || true

echo "Injected expert team '$EXPERT' into instance '$PROFILE'"
echo "  members: ${MEMBER_IDS[*]}"
echo "  shared:  $DATA_DIR/$SHARED_REL (read-only files)"
echo "  backup:  $BACKUP_ID"
echo "  staging: $STAGING"
