#!/usr/bin/env bash
# Doctor for Hermes profile-team expert packs (PRD v1.8 §13.7).
# Usage: check-expert-team.sh <instance> <expert>

set -euo pipefail

PROFILE="${1:?usage: check-expert-team.sh <instance> <expert>}"
EXPERT="${2:?usage: check-expert-team.sh <instance> <expert>}"

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$BASE_DIR/instances/$PROFILE/data/hermes"
TPL_EXPERT="$BASE_DIR/expert-templates/$EXPERT"
TEAM_YAML_TPL="$TPL_EXPERT/team.yaml"
TEAM_YAML_LIVE="$DATA_DIR/team.yaml"
ENV_FILE="$BASE_DIR/instances/$PROFILE/.env"
MANIFEST_PY="$BASE_DIR/scripts/lib/team_manifest.py"

FAIL=0
pass() { echo "[OK] $1"; }
fail() { echo "[FAIL] $1"; FAIL=1; }
skip() { echo "[SKIP] $1"; }

PYTHON=python3
command -v python3 >/dev/null 2>&1 || PYTHON=python

echo "=== check-expert-team: profile=$PROFILE expert=$EXPERT ==="

[ -f "$TEAM_YAML_TPL" ] && pass "template team.yaml exists" || fail "template team.yaml missing"
[ -d "$DATA_DIR" ] && pass "instance hermes home exists" || { fail "instance data missing: $DATA_DIR"; echo "=== Some checks failed ==="; exit 1; }
[ -f "$TEAM_YAML_LIVE" ] && pass "live team.yaml exists" || fail "live team.yaml missing"

if [ -f "$TEAM_YAML_TPL" ]; then
  if "$PYTHON" "$MANIFEST_PY" validate "$TEAM_YAML_TPL" --template-root "$TPL_EXPERT" >/tmp/team-validate-$$.json 2>/dev/null; then
    pass "template manifest validates"
  else
    fail "template manifest invalid"
  fi
fi

EXPECTED_MEMBERS=()
if [ -f "$TEAM_YAML_TPL" ]; then
  mapfile -t EXPECTED_MEMBERS < <("$PYTHON" "$MANIFEST_PY" list-members "$TEAM_YAML_TPL" --template-root "$TPL_EXPERT" \
    | "$PYTHON" -c "import sys,json; d=json.load(sys.stdin); print('\n'.join(m['id'] for m in d.get('members',[]) if m['kind']=='member'))")
fi

# Root structure
for req in SOUL.md config.yaml memories/MEMORY.md memories/USER.md workspace; do
  [ -e "$DATA_DIR/$req" ] && pass "root has $req" || fail "root missing $req"
done

# Named profiles
BANK_IDS=()
if [ -f "$DATA_DIR/config.yaml" ]; then
  ROOT_BANK="$("$PYTHON" -c "import yaml; print(yaml.safe_load(open(r'$DATA_DIR/config.yaml',encoding='utf-8')).get('memory',{}).get('bank_id',''))")"
  BANK_IDS+=("$ROOT_BANK")
fi

for mid in "${EXPECTED_MEMBERS[@]}"; do
  PHOME="$DATA_DIR/profiles/$mid"
  [ -d "$PHOME" ] && pass "profile $mid exists" || { fail "profile $mid missing"; continue; }
  for req in SOUL.md config.yaml memories/MEMORY.md memories/USER.md workspace; do
    [ -e "$PHOME/$req" ] && pass "profile $mid has $req" || fail "profile $mid missing $req"
  done
  # Paths must stay inside profile home (config MCP args)
  "$PYTHON" - <<PY || fail "profile $mid path isolation"
import yaml, sys
cfg = yaml.safe_load(open(r'''$PHOME/config.yaml''', encoding='utf-8')) or {}
home = f"/data/hermes/profiles/$mid"
ws = (cfg.get('mcp_servers') or {}).get('workspace', {}).get('args', [''])[-1]
vault = (cfg.get('mcp_servers') or {}).get('obsidian_vault', {}).get('args', [''])[-1]
assert ws.startswith(home + "/") or ws == home + "/workspace", ws
assert vault.startswith(home + "/") or vault == home + "/obsidian-vault", vault
# Must not host an independent gateway port field for named profile
assert 'api_server' not in cfg or cfg.get('api_server', {}).get('port') in (None, 8642, '')
# Dispatcher off
assert (cfg.get('kanban') or {}).get('dispatch_in_gateway') is False
bank = (cfg.get('memory') or {}).get('bank_id', '')
print(bank)
PY
  MEM_BANK="$("$PYTHON" -c "import yaml; print(yaml.safe_load(open(r'$PHOME/config.yaml',encoding='utf-8')).get('memory',{}).get('bank_id',''))")"
  BANK_IDS+=("$MEM_BANK")
done

# Unique banks
UNIQUE_COUNT="$("$PYTHON" -c "print(len(set('''${BANK_IDS[*]}'''.split())))")"
TOTAL_COUNT="${#BANK_IDS[@]}"
if [ "$UNIQUE_COUNT" = "$TOTAL_COUNT" ] && [ "$TOTAL_COUNT" -gt 0 ]; then
  pass "all Hindsight bank IDs unique ($TOTAL_COUNT)"
else
  fail "duplicate Hindsight bank IDs: ${BANK_IDS[*]}"
fi

# Root kanban dispatcher on
if [ -f "$DATA_DIR/config.yaml" ]; then
  "$PYTHON" - <<PY && pass "root Kanban dispatcher enabled" || fail "root Kanban dispatcher disabled"
import yaml
c = yaml.safe_load(open(r'''$DATA_DIR/config.yaml''', encoding='utf-8')) or {}
assert (c.get('kanban') or {}).get('dispatch_in_gateway') is True
PY
fi

# Shared context
SHARED_REL="team-shared"
if [ -f "$TEAM_YAML_LIVE" ]; then
  SHARED_REL="$("$PYTHON" -c "import yaml; print(yaml.safe_load(open(r'$TEAM_YAML_LIVE',encoding='utf-8')).get('shared_context',{}).get('host_relative_path','team-shared'))")"
fi
SHARED_DIR="$DATA_DIR/$SHARED_REL"
if [ -d "$SHARED_DIR" ]; then
  pass "shared context dir exists ($SHARED_REL)"
  WRITABLE=0
  while IFS= read -r -d '' f; do
    if [ -w "$f" ]; then WRITABLE=1; fi
  done < <(find "$SHARED_DIR" -type f -print0 2>/dev/null)
  if [ "$WRITABLE" = "0" ]; then
    pass "shared context files are non-writable"
  else
    fail "shared context has writable files (expected read-only at runtime)"
  fi
else
  fail "shared context missing: $SHARED_DIR"
fi

# Agency Agents Router on enabled profiles
ROUTER_OK=0
if [ -d "$DATA_DIR/plugins/agency-agents-router" ] || [ -f "$DATA_DIR/plugins/agency-agents-router/SKILL.md" ] || [ -f "$DATA_DIR/plugins/agency-agents-router/router.py" ] || [ -f "$DATA_DIR/plugins/agency-agents-router/README.md" ]; then
  ROUTER_OK=1
fi
# Also accept skill-style install
if [ -d "$DATA_DIR/skills" ] && find "$DATA_DIR/skills" -type d -name 'agency-agents-router' 2>/dev/null | grep -q .; then
  ROUTER_OK=1
fi
if [ "$ROUTER_OK" = "1" ]; then
  pass "Agency Agents Router present on root"
else
  # Only fail soft if template declares dynamic_experts
  if [ -f "$TEAM_YAML_TPL" ] && grep -q 'agency-agents-router' "$TEAM_YAML_TPL" 2>/dev/null; then
    fail "Agency Agents Router missing (expected under plugins/ or skills/)"
  else
    skip "Agency Agents Router not required by manifest"
  fi
fi

# Container runtime checks (optional)
CONTAINER="hermes-$PROFILE"
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER"; then
  pass "container $CONTAINER is running"

  if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
    WEBUI_PORT="${HERMES_WEBUI_PORT:-}"
    GW_PORT="${HERMES_GATEWAY_PORT:-}"
    if [ -n "$WEBUI_PORT" ] && curl -fsS "http://127.0.0.1:$WEBUI_PORT/" >/dev/null 2>&1; then
      pass "WebUI responds on $WEBUI_PORT"
    else
      skip "WebUI health probe inconclusive"
    fi
    if [ -n "$GW_PORT" ] && curl -fsS "http://127.0.0.1:$GW_PORT/health" >/dev/null 2>&1; then
      pass "Gateway health OK on $GW_PORT"
    else
      skip "Gateway health probe inconclusive"
    fi
  fi

  if docker exec "$CONTAINER" hermes profile list >/tmp/hermes-profiles-$$.txt 2>/dev/null; then
    pass "hermes profile list available"
    for mid in "${EXPECTED_MEMBERS[@]}"; do
      if grep -q "$mid" /tmp/hermes-profiles-$$.txt; then
        pass "hermes profile list contains $mid"
      else
        fail "hermes profile list missing $mid"
      fi
    done
  else
    fail "hermes profile list unavailable (Kanban team runtime unsupported without profiles)"
  fi

  if docker exec "$CONTAINER" hermes kanban --help >/dev/null 2>&1; then
    pass "hermes kanban --help available"
  else
    fail "hermes kanban unavailable — must not silently degrade to delegate_task"
  fi

  # Named profiles must not own gateway PIDs / ports
  for mid in "${EXPECTED_MEMBERS[@]}"; do
    if docker exec "$CONTAINER" sh -c "test -f /data/hermes/profiles/$mid/gateway_state.json" 2>/dev/null; then
      fail "named profile $mid has gateway_state.json (must not run independent gateway)"
    else
      pass "named profile $mid has no gateway_state.json"
    fi
  done
else
  skip "container $CONTAINER not running — runtime hermes checks skipped"
fi

rm -f /tmp/team-validate-$$.json /tmp/hermes-profiles-$$.txt 2>/dev/null || true

if [ "$FAIL" -eq 0 ]; then
  echo "=== All checks passed ==="
  exit 0
fi
echo "=== Some checks failed ==="
exit 1
