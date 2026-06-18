#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-sale}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TPL_DIR="$BASE_DIR/expert-templates/sale"
DATA_DIR="$BASE_DIR/instances/$PROFILE/data/hermes"
ROUTING="$BASE_DIR/expert-templates/base/policies/document-routing.yaml"

FAIL=0
pass() { echo "[OK] $1"; }
fail() { echo "[FAIL] $1"; FAIL=1; }

echo "=== check-sale-expert: profile=$PROFILE ==="

[ -d "$TPL_DIR" ] && pass "expert-templates/sale exists" || fail "expert-templates/sale missing"
[ -f "$TPL_DIR/SOUL.md" ] && pass "SOUL.md exists" || fail "SOUL.md missing"
[ -f "$TPL_DIR/memories/MEMORY.md" ] && pass "memories/MEMORY.md exists" || fail "memories/MEMORY.md missing"
[ -f "$TPL_DIR/policies/sale-playbook.yaml" ] && pass "policies/sale-playbook.yaml exists" || fail "policies/sale-playbook.yaml missing"

SKILL_COUNT="$(find "$TPL_DIR/skills/sales" -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')"
if [ "${SKILL_COUNT:-0}" -ge 8 ]; then
  pass "sales skills count >= 8 ($SKILL_COUNT)"
else
  fail "sales skills count < 8 ($SKILL_COUNT)"
fi

if grep -q 'expert_defaults:' "$ROUTING" && grep -A20 'expert_defaults:' "$ROUTING" | grep -q 'sale:'; then
  pass "document-routing.yaml contains expert_defaults.sale"
else
  fail "document-routing.yaml missing expert_defaults.sale"
fi

if [ -d "$DATA_DIR" ]; then
  [ -f "$DATA_DIR/policies/sale-playbook.yaml" ] && pass "instance sale-playbook.yaml exists" || fail "instance sale-playbook.yaml missing"
  [ -d "$DATA_DIR/skills/sales" ] && pass "instance skills/sales exists" || fail "instance skills/sales missing"
  for d in materials/sale references/sale drafts/sale reports/sale exports/sale artifacts/sale; do
    [ -d "$DATA_DIR/workspace/$d" ] && pass "workspace/$d exists" || fail "workspace/$d missing"
  done
  [ -d "$DATA_DIR/obsidian-vault/60-Reports/Sales" ] && pass "obsidian 60-Reports/Sales exists" || fail "obsidian 60-Reports/Sales missing"
else
  echo "[SKIP] instance $DATA_DIR not found (template-only check)"
fi

if [ "$FAIL" -eq 0 ]; then
  echo "=== All checks passed ==="
  exit 0
fi

echo "=== Some checks failed ==="
exit 1
