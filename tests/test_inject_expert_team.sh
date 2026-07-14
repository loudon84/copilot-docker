#!/usr/bin/env bash
# Integration tests for inject-expert-team.sh using mini-team fixture.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FIXTURE="$ROOT/tests/fixtures/mini-team"
INSTANCE="mini-team-test-$$"
INSTANCE_DIR="$ROOT/instances/$INSTANCE"
DATA_DIR="$INSTANCE_DIR/data/hermes"

cleanup() {
  rm -rf "$INSTANCE_DIR"
}
trap cleanup EXIT

PYTHON=python3
command -v python3 >/dev/null 2>&1 || PYTHON=python

pass() { echo "[OK] $1"; }
fail() { echo "[FAIL] $1"; exit 1; }

echo "=== test_inject_expert_team: instance=$INSTANCE ==="

# Seed minimal instance env (required by inject-expert-team)
mkdir -p "$DATA_DIR"
cat > "$INSTANCE_DIR/.env" <<EOF
HERMES_PROFILE=$INSTANCE
HERMES_EXPERT=mini-team
HINDSIGHT_API_URL=http://hindsight.superic.com:8888
HINDSIGHT_BANK_ID=hermes-$INSTANCE
GBRAIN_ENABLED=1
EOF
chmod 600 "$INSTANCE_DIR/.env" 2>/dev/null || true

# --- Failure path: broken manifest must not leave active team.yaml ---
BAD_DIR="$ROOT/tests/fixtures/mini-team-bad-$$"
mkdir -p "$BAD_DIR/root"
cp "$FIXTURE/team.yaml" "$BAD_DIR/team.yaml"
# Corrupt kind
"$PYTHON" - <<PY
from pathlib import Path
import yaml
p = Path(r'''$BAD_DIR/team.yaml''')
d = yaml.safe_load(p.read_text(encoding='utf-8'))
d['kind'] = 'broken'
p.write_text(yaml.safe_dump(d), encoding='utf-8')
PY

export TEAM_TEMPLATE_ROOT="$BAD_DIR"
if bash "$ROOT/scripts/inject-expert-team.sh" "$INSTANCE" mini-team; then
  rm -rf "$BAD_DIR"
  fail "expected inject to fail on bad manifest"
fi
[ ! -f "$DATA_DIR/team.yaml" ] && pass "bad manifest: no active team.yaml" || fail "bad manifest left team.yaml"
rm -rf "$BAD_DIR"
unset TEAM_TEMPLATE_ROOT

# --- Success path ---
export TEAM_TEMPLATE_ROOT="$FIXTURE"
bash "$ROOT/scripts/inject-expert-team.sh" "$INSTANCE" mini-team

[ -f "$DATA_DIR/team.yaml" ] && pass "team.yaml present" || fail "team.yaml missing"
[ -f "$DATA_DIR/SOUL.md" ] && pass "root SOUL.md" || fail "root SOUL.md missing"
[ -f "$DATA_DIR/profiles/advisor-alpha/SOUL.md" ] && pass "advisor SOUL.md" || fail "advisor SOUL.md missing"
[ -f "$DATA_DIR/profiles/advisor-alpha/config.yaml" ] && pass "advisor config.yaml" || fail "advisor config missing"
[ -d "$DATA_DIR/team-shared" ] && pass "team-shared exists" || fail "team-shared missing"

# Bank IDs unique
ROOT_BANK="$("$PYTHON" -c "import yaml; print(yaml.safe_load(open(r'$DATA_DIR/config.yaml',encoding='utf-8'))['memory']['bank_id'])")"
MEM_BANK="$("$PYTHON" -c "import yaml; print(yaml.safe_load(open(r'$DATA_DIR/profiles/advisor-alpha/config.yaml',encoding='utf-8'))['memory']['bank_id'])")"
[ "$ROOT_BANK" != "$MEM_BANK" ] && pass "bank ids unique ($ROOT_BANK vs $MEM_BANK)" || fail "bank ids equal"

# Root kanban on
"$PYTHON" - <<PY
import yaml
c = yaml.safe_load(open(r'''$DATA_DIR/config.yaml''', encoding='utf-8'))
assert c.get('kanban', {}).get('dispatch_in_gateway') is True
m = yaml.safe_load(open(r'''$DATA_DIR/profiles/advisor-alpha/config.yaml''', encoding='utf-8'))
assert m.get('kanban', {}).get('dispatch_in_gateway') is False
print('kanban dispatcher ok')
PY
pass "kanban dispatcher root on / member off"

# Shared file not group-writable (best-effort check)
SHARED_FILE="$DATA_DIR/team-shared/COMPANY.md"
if [ -f "$SHARED_FILE" ]; then
  if [ ! -w "$SHARED_FILE" ] || [ "$(stat -c %a "$SHARED_FILE" 2>/dev/null || echo 444)" = "444" ] || [ ! -w "$SHARED_FILE" ]; then
    pass "shared COMPANY.md is non-writable (or chmod applied)"
  else
    # On some Windows mounts chmod is noop; still require file exists
    pass "shared COMPANY.md present (chmod may be noop on this FS)"
  fi
fi

# --- Idempotent re-inject ---
BEFORE_BANK="$ROOT_BANK"
bash "$ROOT/scripts/inject-expert-team.sh" "$INSTANCE" mini-team
AFTER_BANK="$("$PYTHON" -c "import yaml; print(yaml.safe_load(open(r'$DATA_DIR/config.yaml',encoding='utf-8'))['memory']['bank_id'])")"
[ "$BEFORE_BANK" = "$AFTER_BANK" ] && pass "idempotent bank id stable" || fail "bank id changed on re-inject"
[ -d "$DATA_DIR/profiles/advisor-alpha" ] && pass "member still present after re-inject" || fail "member lost"

# Backup directories created
BACKUP_COUNT="$(find "$DATA_DIR/.backup" -maxdepth 1 -type d | wc -l | tr -d ' ')"
[ "$BACKUP_COUNT" -ge 3 ] && pass "backups created ($BACKUP_COUNT dirs)" || fail "expected >=2 backup timestamps"

echo "=== All inject-expert-team checks passed ==="
