#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-writer}"
CONTAINER="hermes-${PROFILE}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "ERROR: container not running: $CONTAINER"
  exit 1
fi

docker exec -u root -i "$CONTAINER" bash <<'EOS'
set -euo pipefail

export HERMES_HOME=/data/hermes
export HERMES_CONFIG_PATH=/data/hermes/config.yaml
export GBRAIN_HOME="${GBRAIN_HOME:-/data/hermes/gbrain}"
export GBRAIN_VAULT="${GBRAIN_VAULT:-/data/hermes/obsidian-vault}"

mkdir -p \
  "$GBRAIN_HOME" \
  "$GBRAIN_VAULT" \
  /data/hermes/mcp \
  /data/hermes/skill-bundles \
  /data/hermes/backups \
  /data/hermes/obsidian-vault/40-Skills \
  /data/hermes/obsidian-vault/50-Memory \
  /data/hermes/obsidian-vault/70-Brain \
  /data/hermes/obsidian-vault/80-Product-Spec

if [ ! -f "$GBRAIN_VAULT/INDEX.md" ]; then
  cat > "$GBRAIN_VAULT/INDEX.md" <<'MD'
# Hermes Obsidian Vault

## Directory Contract

- 00-Inbox: temporary inputs
- 10-Articles: article drafts
- 20-Research: research notes
- 30-Templates: reusable templates
- 40-Skills: skill design and audit notes
- 50-Memory: durable agent operating notes
- 60-Reports: generated reports
- 70-Brain: GBrain summaries and sync notes
- 80-Product-Spec: IC datasheet Markdown outputs
- 90-Archive: archived materials
MD
fi

if command -v gbrain >/dev/null 2>&1; then
  cd /data/hermes
  gbrain init --pglite || true
  gbrain import "$GBRAIN_VAULT" || true
else
  echo "WARN: gbrain command not found. Check Dockerfile INSTALL_GBRAIN or set internal GBRAIN_REPO mirror."
fi

/app/venv/bin/python - <<'PY'
import os
from pathlib import Path
try:
    import yaml
except Exception:
    raise SystemExit('PyYAML not installed in /app/venv')

config_path = Path('/data/hermes/config.yaml')
data = {}
if config_path.exists():
    loaded = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    if isinstance(loaded, dict):
        data = loaded

profile = os.environ.get('HERMES_PROFILE', 'default')
hindsight_api = os.environ.get('HINDSIGHT_API_URL', 'http://hindsight.superic.com:8888')
hindsight_bank = os.environ.get('HINDSIGHT_BANK_ID', f'hermes-{profile}')
gbrain_enabled = os.environ.get('GBRAIN_ENABLED', '1') not in ('0', 'false', 'False')
gbrain_command = os.environ.get('GBRAIN_COMMAND', '/usr/local/bin/gbrain')

data['memory'] = {
    'provider': 'hindsight',
    'mode': 'local_external',
    'api_url': hindsight_api,
    'bank_id': hindsight_bank,
}

mcp = data.setdefault('mcp_servers', {})
mcp.setdefault('obsidian_vault', {
    'command': 'npx',
    'args': ['-y', '@modelcontextprotocol/server-filesystem', '/data/hermes/obsidian-vault'],
    'enabled': True,
    'tools': {'resources': True, 'prompts': False},
})
mcp.setdefault('gbrain', {
    'command': gbrain_command,
    'args': [],
    'enabled': gbrain_enabled,
    'tools': {'resources': True, 'prompts': False},
})

aux = data.setdefault('auxiliary', {})
aux.setdefault('curator', {
    'enabled': True,
    'interval_days': 7,
    'archive_unused_after_days': 45,
    'protect_bundled_skills': True,
    'protect_hub_skills': True,
})

security = data.setdefault('security', {})
security.setdefault('website_blocklist', {
    'enabled': True,
    'domains': ['169.254.169.254']
})

terminal = data.setdefault('terminal', {})
terminal['backend'] = 'docker'
terminal.setdefault('docker_forward_env', [])
terminal.setdefault('env_passthrough', [])

config_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding='utf-8')
print('OK: config.yaml updated for memory, obsidian_vault MCP, gbrain MCP, curator, security and terminal')
PY

chown -R "${WANTED_UID:-1000}:${WANTED_GID:-1000}" /data/hermes || true
EOS

docker restart "$CONTAINER" >/dev/null
echo "OK: brain runtime initialized for $PROFILE"
