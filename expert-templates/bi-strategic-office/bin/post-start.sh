#!/usr/bin/env bash
# Post-start initialization for bi-strategic-office (PRD v1.10 §15).
# Runs after container is up. Does NOT stop the container on failure.
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE=""
INSTANCE_DIR=""
DATA_DIR=""
REPO_ROOT=""
CONTAINER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --instance-dir) INSTANCE_DIR="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --repo-root) REPO_ROOT="$2"; shift 2 ;;
    --container) CONTAINER="$2"; shift 2 ;;
    -h|--help)
      echo "usage: post-start.sh --profile <p> --instance-dir <d> --data-dir <d> --repo-root <d> --container <name>"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

fail() {
  echo "ERROR: post-start failed: $*" >&2
  echo "Hint: bash \"$PACKAGE_ROOT/bin/doctor.sh\" --profile \"$PROFILE\" --container \"$CONTAINER\"" >&2
  echo "Hint: container left running; fix then re-run up-instance or post-start" >&2
  exit 1
}

[[ -n "$PROFILE" ]] || fail "missing --profile"
[[ -n "$DATA_DIR" ]] || fail "missing --data-dir"
[[ -n "$CONTAINER" ]] || fail "missing --container"

echo "[post-start] profile=$PROFILE container=$CONTAINER"

# 1) Container running
STATE="$(docker inspect --format '{{.State.Status}}' "$CONTAINER" 2>/dev/null || echo missing)"
[[ "$STATE" == "running" ]] || fail "container not running (state=$STATE)"

# 2) /data/hermes mounted
if ! docker exec "$CONTAINER" bash -lc 'test -d /data/hermes'; then
  fail "/data/hermes not mounted in container"
fi

PLUGIN_HOST="$DATA_DIR/plugins/hermes-finance-bi-plugin"
REQ_FILE="$PLUGIN_HOST/requirements.txt"
[[ -f "$REQ_FILE" ]] || fail "requirements.txt missing at $REQ_FILE"

# 3) Install Python deps with hash dedupe
HASH_FILE="$DATA_DIR/finance-bi/.requirements.sha256"
mkdir -p "$DATA_DIR/finance-bi"
NEW_HASH=""
if command -v sha256sum >/dev/null 2>&1; then
  NEW_HASH="$(sha256sum "$REQ_FILE" | awk '{print $1}')"
elif command -v shasum >/dev/null 2>&1; then
  NEW_HASH="$(shasum -a 256 "$REQ_FILE" | awk '{print $1}')"
else
  NEW_HASH="$(python -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$REQ_FILE")"
fi

NEED_PIP=1
if [[ -f "$HASH_FILE" ]]; then
  OLD_HASH="$(tr -d ' \n\r' < "$HASH_FILE" || true)"
  if [[ "$OLD_HASH" == "$NEW_HASH" ]]; then
    echo "[post-start] requirements hash unchanged — skip pip install"
    NEED_PIP=0
  fi
fi

if [[ "$NEED_PIP" = "1" ]]; then
  echo "[post-start] installing plugin requirements into /app/venv"
  docker cp "$REQ_FILE" "$CONTAINER:/tmp/hermes-finance-bi-requirements.txt" \
    || fail "docker cp requirements"
  docker exec -u root "$CONTAINER" bash -lc '
    set -euo pipefail
    /app/venv/bin/python -m pip install -r /tmp/hermes-finance-bi-requirements.txt
    chown -R 1000:1000 /app/venv
  ' || fail "pip install finance-bi requirements"
  printf '%s\n' "$NEW_HASH" > "$HASH_FILE"
  echo "[post-start] wrote $HASH_FILE"
fi

# 4) Plugin directory permissions
docker exec -u root "$CONTAINER" bash -lc '
  chown -R 1000:1000 /data/hermes/plugins/hermes-finance-bi-plugin 2>/dev/null || true
  chmod -R u+rwX,g+rwX /data/hermes/plugins/hermes-finance-bi-plugin 2>/dev/null || true
' || true

# 5) Enable plugin via hermes CLI when available (config already merged at install)
docker exec -u hermeswebui -e HERMES_HOME=/data/hermes "$CONTAINER" bash -lc '
  if [ -x /app/venv/bin/hermes ]; then
    if command -v script >/dev/null 2>&1; then
      script -qfc "/app/venv/bin/hermes plugins enable hermes-finance-bi-plugin" /dev/null 2>/dev/null || true
    else
      /app/venv/bin/hermes plugins enable hermes-finance-bi-plugin 2>/dev/null || true
    fi
  fi
' || true

# 6) Check plugin / toolset listing
CLI_OUT="$(
  docker exec -u hermeswebui -e HERMES_HOME=/data/hermes "$CONTAINER" bash -lc '
    if command -v script >/dev/null 2>&1 && [ -x /app/venv/bin/hermes ]; then
      script -qfc "/app/venv/bin/hermes plugins list" /dev/null 2>/dev/null || true
      script -qfc "/app/venv/bin/hermes tools --summary" /dev/null 2>/dev/null || true
    fi
  ' 2>/dev/null || true
)"

if echo "$CLI_OUT" | grep -qiE 'hermes-finance-bi-plugin|finance-bi|Finance-Bi|finance_bi'; then
  echo "[post-start] PASS: plugin/toolset visible in hermes CLI"
else
  echo "WARN: hermes CLI listing did not clearly show finance-bi; continuing with doctor"
fi

# 7) Semantic catalog path
docker exec "$CONTAINER" bash -lc 'test -d /data/hermes/finance-bi/semantic/datasets' \
  || fail "semantic catalog missing in container"

# 8) State dir writable
docker exec "$CONTAINER" bash -lc '
  test -d /data/hermes/finance-bi/state && touch /data/hermes/finance-bi/state/.write_probe && rm -f /data/hermes/finance-bi/state/.write_probe
' || fail "finance-bi/state not writable"

# 9) Doctor
bash "$PACKAGE_ROOT/bin/doctor.sh" \
  --profile "$PROFILE" \
  --instance-dir "${INSTANCE_DIR:-}" \
  --data-dir "$DATA_DIR" \
  --container "$CONTAINER" \
  || fail "doctor.sh"

echo "OK: post-start complete for $PROFILE"
exit 0
