#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash scripts/clone-instance.sh <source_instance> <target_instance> <target_webui_port> [--copy-secrets] [--dry-run]

Examples:
  bash scripts/clone-instance.sh ceo-a ceo-b 8791
  bash scripts/clone-instance.sh ceo-a ceo-b 8791 --copy-secrets

Safety contract:
  - The target instance MUST NOT already exist.
  - Existing instances are never overwritten, repaired, merged, or upgraded by this command.
  - There is intentionally no --force / --overwrite option.
  - sessions, memories, logs, workspace documents, webui state, Hindsight data, backups and attachments are not cloned.
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

info() {
  echo "[clone] $*"
}

SOURCE="${1:-}"
TARGET="${2:-}"
PORT="${3:-}"

[ -n "$SOURCE" ] && [ -n "$TARGET" ] && [ -n "$PORT" ] || {
  usage
  exit 2
}

shift 3 || true

COPY_SECRETS=0
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --copy-secrets)
      COPY_SECRETS=1
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
  shift
done

if ! [[ "$SOURCE" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  die "invalid source instance name: $SOURCE"
fi
if ! [[ "$TARGET" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  die "invalid target instance name: $TARGET"
fi
if [ "$SOURCE" = "$TARGET" ]; then
  die "source and target must be different"
fi
if ! [[ "$PORT" =~ ^[1-9][0-9]{3}$ ]]; then
  die "target_webui_port must be a 4-digit number (1000-9999), got: $PORT"
fi

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_INSTANCE_DIR="$BASE_DIR/instances/$SOURCE"
SOURCE_DATA_DIR="$SOURCE_INSTANCE_DIR/data/hermes"
SOURCE_ENV="$SOURCE_INSTANCE_DIR/.env"

TARGET_INSTANCE_DIR="$BASE_DIR/instances/$TARGET"
TARGET_DATA_DIR="$TARGET_INSTANCE_DIR/data/hermes"
TARGET_ENV="$TARGET_INSTANCE_DIR/.env"

CREATE_SCRIPT="$BASE_DIR/scripts/create-instance.sh"
EXPORTER="$BASE_DIR/scripts/lib/clone_capability.py"
ENV_MERGER="$BASE_DIR/scripts/lib/clone_env.py"
REBINDER="$BASE_DIR/scripts/lib/rebind_clone_runtime.py"

[ -x "$CREATE_SCRIPT" ] || [ -f "$CREATE_SCRIPT" ] || die "missing create script: $CREATE_SCRIPT"
[ -f "$EXPORTER" ] || die "missing helper: $EXPORTER"
[ -f "$ENV_MERGER" ] || die "missing helper: $ENV_MERGER"
[ -f "$REBINDER" ] || die "missing helper: $REBINDER"

[ -d "$SOURCE_INSTANCE_DIR" ] || die "source instance not found: $SOURCE_INSTANCE_DIR"
[ -d "$SOURCE_DATA_DIR" ] || die "source Hermes data not found: $SOURCE_DATA_DIR"
[ -f "$SOURCE_ENV" ] || die "source env not found: $SOURCE_ENV"
[ -f "$SOURCE_DATA_DIR/config.yaml" ] || die "source config missing: $SOURCE_DATA_DIR/config.yaml"

# HARD GUARD: target must be completely absent before the clone starts.
if [ -e "$TARGET_INSTANCE_DIR" ]; then
  die "target instance already exists: $TARGET_INSTANCE_DIR. Clone is create-only and refuses initialized/existing instances."
fi

if docker inspect "hermes-$TARGET" >/dev/null 2>&1; then
  die "target container already exists: hermes-$TARGET. Clone is create-only."
fi

TARGET_GATEWAY_PORT=$((20000 + PORT))
for env_file in "$BASE_DIR"/instances/*/.env; do
  [ -f "$env_file" ] || continue
  existing_name="$(basename "$(dirname "$env_file")")"
  existing_webui="$(awk -F= '$1=="HERMES_WEBUI_PORT"{print substr($0,index($0,"=")+1); exit}' "$env_file")"
  existing_gateway="$(awk -F= '$1=="HERMES_GATEWAY_PORT"{print substr($0,index($0,"=")+1); exit}' "$env_file")"
  if [ "$existing_webui" = "$PORT" ]; then
    die "target WebUI port $PORT is already used by instance $existing_name"
  fi
  if [ "$existing_gateway" = "$TARGET_GATEWAY_PORT" ]; then
    die "target gateway port $TARGET_GATEWAY_PORT is already used by instance $existing_name"
  fi
done

LOCK_ROOT="$BASE_DIR/instances/.locks"
mkdir -p "$LOCK_ROOT"
LOCK_DIR="$LOCK_ROOT/clone-$TARGET.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  die "target clone lock already exists: $LOCK_DIR"
fi

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/hermes-clone-${SOURCE}-to-${TARGET}.XXXXXX")"
BUNDLE="$TMP_DIR/capability.tgz"
CREATED_TARGET=0
SUCCESS=0

cleanup() {
  rc=$?
  if [ "$SUCCESS" != "1" ] && [ "$CREATED_TARGET" = "1" ]; then
    echo "[clone] clone failed; removing newly-created target instance: $TARGET_INSTANCE_DIR" >&2
    rm -rf "$TARGET_INSTANCE_DIR"
  fi
  rm -rf "$TMP_DIR" "$LOCK_DIR"
  exit "$rc"
}
trap cleanup EXIT INT TERM

SOURCE_EXPERT="$(awk -F= '$1=="HERMES_EXPERT"{print substr($0,index($0,"=")+1); exit}' "$SOURCE_ENV")"
SOURCE_EXPERT="${SOURCE_EXPERT:-base}"

info "source=$SOURCE expert=$SOURCE_EXPERT"
info "target=$TARGET webui_port=$PORT"
info "exporting persistent capability plane (sessions/memory excluded)"

python3 "$EXPORTER" export \
  --source-root "$SOURCE_DATA_DIR" \
  --source-instance "$SOURCE" \
  --output "$BUNDLE"

if [ "$DRY_RUN" = "1" ]; then
  info "dry-run successful"
  python3 "$EXPORTER" inspect --archive "$BUNDLE"
  SUCCESS=1
  exit 0
fi

# The target did not exist before this script. create-instance.sh is used only as
# an internal bootstrap step to generate a clean target .env, empty state dirs,
# unique WebUI password/API key, and the baseline expert layout.
info "creating clean target instance skeleton"
bash "$CREATE_SCRIPT" "$TARGET" "$PORT" "$SOURCE_EXPERT"
CREATED_TARGET=1

[ -f "$TARGET_ENV" ] || die "target .env was not created"
[ -d "$TARGET_DATA_DIR" ] || die "target Hermes data directory was not created"

# Merge non-secret runtime switches from A into B while preserving B identity,
# ports, WebUI password, API server key, Hindsight bank and model name.
ENV_ARGS=()
if [ "$COPY_SECRETS" = "1" ]; then
  ENV_ARGS+=(--copy-secrets)
fi

python3 "$ENV_MERGER" \
  --source "$SOURCE_ENV" \
  --target "$TARGET_ENV" \
  "${ENV_ARGS[@]}"

info "applying capability bundle to clean target"
python3 "$EXPORTER" apply \
  --archive "$BUNDLE" \
  --target-root "$TARGET_DATA_DIR"

# Recreate standard empty runtime directories without copying source runtime data.
# shellcheck source=lib/init_hermes_dirs.sh
source "$BASE_DIR/scripts/lib/init_hermes_dirs.sh"
init_hermes_dirs "$TARGET_DATA_DIR"

seed_empty_memory() {
  local profile_root="$1"
  local profile_label="$2"
  mkdir -p "$profile_root/memories"
  if [ ! -f "$profile_root/memories/MEMORY.md" ]; then
    cp "$BASE_DIR/expert-templates/base/memories/MEMORY.md" "$profile_root/memories/MEMORY.md"
    sed -i \
      -e "s|__PROFILE__|$profile_label|g" \
      -e "s|__HINDSIGHT_API_URL__|${HINDSIGHT_API_URL:-http://hindsight.superic.com:8888}|g" \
      "$profile_root/memories/MEMORY.md"
  fi
  if [ ! -f "$profile_root/memories/USER.md" ]; then
    cp "$BASE_DIR/expert-templates/base/memories/USER.md" "$profile_root/memories/USER.md"
  fi
}

seed_empty_memory "$TARGET_DATA_DIR" "$TARGET"

if [ -d "$TARGET_DATA_DIR/profiles" ]; then
  while IFS= read -r profile_dir; do
    [ -d "$profile_dir" ] || continue
    init_hermes_dirs "$profile_dir"
    seed_empty_memory "$profile_dir" "$(basename "$profile_dir")"
  done < <(find "$TARGET_DATA_DIR/profiles" -mindepth 1 -maxdepth 1 -type d | sort)
fi

# Guarantee no session/history material survived target bootstrap or clone.
rm -rf "$TARGET_DATA_DIR/sessions/"* 2>/dev/null || true
rm -rf "$TARGET_DATA_DIR/logs/"* 2>/dev/null || true
rm -rf "$TARGET_DATA_DIR/checkpoints/"* 2>/dev/null || true
rm -rf "$TARGET_DATA_DIR/hindsight/"* 2>/dev/null || true

if [ -d "$TARGET_DATA_DIR/profiles" ]; then
  while IFS= read -r profile_dir; do
    [ -d "$profile_dir" ] || continue
    rm -rf "$profile_dir/sessions/"* 2>/dev/null || true
    rm -rf "$profile_dir/logs/"* 2>/dev/null || true
    rm -rf "$profile_dir/checkpoints/"* 2>/dev/null || true
    rm -rf "$profile_dir/hindsight/"* 2>/dev/null || true
  done < <(find "$TARGET_DATA_DIR/profiles" -mindepth 1 -maxdepth 1 -type d | sort)
fi

# Runtime rebinding is mandatory. In particular, copied configs must not keep
# Hindsight bank IDs that point back to source instance A.
HINDSIGHT_API_URL="$(awk -F= '$1=="HINDSIGHT_API_URL"{print substr($0,index($0,"=")+1); exit}' "$TARGET_ENV")"
HINDSIGHT_API_URL="${HINDSIGHT_API_URL:-http://hindsight.superic.com:8888}"

python3 "$REBINDER" \
  --hermes-root "$TARGET_DATA_DIR" \
  --source-instance "$SOURCE" \
  --target-instance "$TARGET" \
  --hindsight-api-url "$HINDSIGHT_API_URL"

# Sync the newly generated B runtime env after the merge/rebind.
bash "$BASE_DIR/scripts/sync-runtime-env.sh" "$TARGET"

# Ensure B owns its own external memory namespace even if source had a custom bank.
python3 "$REBINDER" \
  --hermes-root "$TARGET_DATA_DIR" \
  --source-instance "$SOURCE" \
  --target-instance "$TARGET" \
  --hindsight-api-url "$HINDSIGHT_API_URL" \
  --verify-only

# Clone lifecycle marker. The guard is based on target non-existence, so this
# marker is audit metadata, not a bypassable authorization flag.
python3 - "$TARGET_INSTANCE_DIR/.instance-clone.json" "$SOURCE" "$TARGET" "$SOURCE_EXPERT" "$COPY_SECRETS" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path, source, target, expert, copy_secrets = sys.argv[1:]
payload = {
    "schema_version": "1.0",
    "lifecycle": "initialized",
    "created_by": "clone-instance.sh",
    "source_instance": source,
    "target_instance": target,
    "expert": expert,
    "sessions_cloned": False,
    "memories_cloned": False,
    "secrets_cloned": copy_secrets == "1",
    "created_at": datetime.now(timezone.utc).isoformat(),
}
Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

chown -R 1000:1000 "$TARGET_DATA_DIR" 2>/dev/null || true
chmod -R u+rwX,g+rwX "$TARGET_DATA_DIR" 2>/dev/null || true
chmod 600 "$TARGET_ENV" 2>/dev/null || true

SUCCESS=1

info "clone completed"
echo "  source: $SOURCE"
echo "  target: $TARGET"
echo "  expert: $SOURCE_EXPERT"
echo "  WebUI:  http://127.0.0.1:$PORT"
echo "  next:   bash scripts/up-instance.sh $TARGET"
echo "  verify: bash scripts/check-agent-api.sh $TARGET"
echo
echo "IMPORTANT: clone-instance.sh will now refuse this target forever because instances/$TARGET exists."
