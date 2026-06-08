#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-writer}"
CONTAINER="hermes-${PROFILE}"
REPO_URL="${SELF_EVOLUTION_REPO:-https://github.com/NousResearch/hermes-agent-self-evolution.git}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "ERROR: container not running: $CONTAINER"
  exit 1
fi

docker exec -u root -i -e SELF_EVOLUTION_REPO="$REPO_URL" "$CONTAINER" bash <<'EOS'
set -euo pipefail

mkdir -p /data/hermes/evolution /data/hermes/evolution/runs /data/hermes/evolution/reports

if [ ! -d /data/hermes/evolution/hermes-agent-self-evolution ]; then
  git clone "$SELF_EVOLUTION_REPO" /data/hermes/evolution/hermes-agent-self-evolution || {
    echo "WARN: clone failed. Set SELF_EVOLUTION_REPO to internal mirror in production."
    exit 0
  }
fi

cd /data/hermes/evolution/hermes-agent-self-evolution
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip setuptools wheel
pip install -e ".[dev]" || pip install -e .

cat > /data/hermes/evolution/README.md <<'MD'
# Hermes Self Evolution Runtime

Rules:

1. Do not run against production skills directly.
2. Generate candidate patches only.
3. Review diff manually.
4. Run `skill-audit` before merging.
5. Merge only into `/data/hermes/skills` after validation.
6. Keep run outputs under `/data/hermes/evolution/runs` and reports under `/data/hermes/evolution/reports`.
MD

chown -R "${WANTED_UID:-1000}:${WANTED_GID:-1000}" /data/hermes/evolution || true
EOS

echo "OK: self-evolution runtime installed for $PROFILE"
echo "NOTE: it is not enabled automatically and will not modify production skills."
