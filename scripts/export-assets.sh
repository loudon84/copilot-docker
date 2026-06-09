#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:?usage: export-assets.sh <source_profile> <bundle_name> [--migrate-agent-tools]}"
BUNDLE="${2:?usage: export-assets.sh <source_profile> <bundle_name> [--migrate-agent-tools]}"
MIGRATE_AGENT_TOOLS=0

shift 2 || true
while [ $# -gt 0 ]; do
  case "$1" in
    --migrate-agent-tools) MIGRATE_AGENT_TOOLS=1 ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
  shift
done

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER="hermes-$PROFILE"
OUT_DIR="$BASE_DIR/asset-bundles/$BUNDLE"
TMP_DIR="/tmp/hermes-asset-export-$BUNDLE"
INCLUDE_FILE="$BASE_DIR/asset-bundles/$BUNDLE/agent-tools.include"
INCLUDE_TMP=""

docker inspect "$CONTAINER" >/dev/null 2>&1 || {
  echo "ERROR: container not found: $CONTAINER"
  exit 1
}

if [ -f "$INCLUDE_FILE" ]; then
  INCLUDE_TMP="$(mktemp)"
  cp "$INCLUDE_FILE" "$INCLUDE_TMP"
fi

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

if [ "$MIGRATE_AGENT_TOOLS" = "1" ]; then
  if [ -n "$INCLUDE_TMP" ] && [ -f "$INCLUDE_TMP" ]; then
    docker cp "$INCLUDE_TMP" "$CONTAINER:/tmp/agent-tools.include"
    docker exec "$CONTAINER" bash -lc '
set -e
mkdir -p /data/hermes/tools
while IFS= read -r item || [ -n "$item" ]; do
  case "$item" in
    ""|\#*) continue ;;
  esac
  if [ -e "/opt/hermes-agent/tools/$item" ]; then
    cp -a "/opt/hermes-agent/tools/$item" "/data/hermes/tools/" || true
  else
    echo "WARN: agent tool not found: $item"
  fi
done < /tmp/agent-tools.include
'
  else
    echo "WARN: --migrate-agent-tools set but $INCLUDE_FILE not found; skipping migration"
  fi
fi

[ -n "$INCLUDE_TMP" ] && rm -f "$INCLUDE_TMP"

docker exec "$CONTAINER" bash -lc "
set -e
rm -rf '$TMP_DIR'
mkdir -p '$TMP_DIR'

for d in skills tools plugins mcp policies skill-bundles gbrain; do
  if [ -d /data/hermes/\$d ]; then
    cp -a /data/hermes/\$d '$TMP_DIR/' || true
  fi
done

cd '$TMP_DIR'
tar czf /tmp/data-hermes-assets.tgz .
"

docker cp "$CONTAINER:/tmp/data-hermes-assets.tgz" "$OUT_DIR/data-hermes-assets.tgz"

if tar tzf "$OUT_DIR/data-hermes-assets.tgz" \
  | grep -E '(^|/)tools/tools($|/)|(^|/)plugins/plugins($|/)' >/dev/null 2>&1; then
  echo "ERROR: invalid nested tools/plugins path detected in bundle"
  rm -f "$OUT_DIR/data-hermes-assets.tgz"
  exit 1
fi

docker exec "$CONTAINER" bash -lc "/app/venv/bin/python -m pip freeze" > "$OUT_DIR/pip-freeze.txt" || true

cat > "$OUT_DIR/requirements.txt" <<'EOF'
# Add minimum Python dependencies required by this bundle.
# Do not paste full pip-freeze unless the bundle really needs it.
EOF

cat > "$OUT_DIR/npm-global.txt" <<'EOF'
# Add npm global packages required by this bundle, one per line.
EOF

cat > "$OUT_DIR/apt-packages.txt" <<'EOF'
# Add apt packages required by this bundle.
# These are not installed automatically by import-assets.sh.
# Put system packages into Dockerfile for production images.
EOF

cat > "$OUT_DIR/verify.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

echo "== verify bundle paths =="
ls -la /data/hermes/skills 2>/dev/null || true
ls -la /data/hermes/tools 2>/dev/null || true
ls -la /data/hermes/plugins 2>/dev/null || true
ls -la /data/hermes/mcp 2>/dev/null || true

echo "== python =="
/app/venv/bin/python - <<'PY'
print("python ok")
PY
EOF
chmod +x "$OUT_DIR/verify.sh"

cat > "$OUT_DIR/manifest.json" <<EOF
{
  "schema_version": "1.0",
  "bundle": "$BUNDLE",
  "source_profile": "$PROFILE",
  "source_container": "$CONTAINER",
  "asset_archive": "data-hermes-assets.tgz",
  "python_deps_file": "requirements.txt",
  "npm_deps_file": "npm-global.txt",
  "apt_deps_file": "apt-packages.txt",
  "exported_at": "$(date -Iseconds)",
  "include": [
    "skills",
    "tools",
    "plugins",
    "mcp",
    "policies",
    "skill-bundles",
    "gbrain"
  ],
  "exclude": [
    ".env",
    "config.yaml",
    "memories",
    "sessions",
    "logs",
    "webui",
    "workspace",
    "obsidian-vault",
    "hindsight",
    "backups"
  ],
  "notes": "Do not include secrets, personal memory, sessions, logs, workspace files, or Hindsight bank config."
}
EOF

cat > "$OUT_DIR/README.md" <<EOF
# $BUNDLE

Source profile: $PROFILE  
Source container: $CONTAINER

## Import

\`\`\`bash
bash scripts/import-assets.sh <target_profile> $BUNDLE --restart
\`\`\`

## Verify

\`\`\`bash
docker exec -it hermes-<target_profile> bash /tmp/hermes-bundle-verify.sh
\`\`\`
EOF

echo "OK: exported bundle to $OUT_DIR"
