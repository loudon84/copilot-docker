#!/usr/bin/env bash
# Validate expert template structure.
set -euo pipefail

EXPERT="${1:?usage: validate-expert-template.sh <expert>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TPL="$BASE_DIR/expert-templates/$EXPERT"

fail() { echo "FAIL: $*"; exit 1; }
pass() { echo "PASS: $*"; }

[ -d "$TPL" ] || fail "template not found: $TPL"
[ -f "$TPL/SOUL.md" ] || fail "missing SOUL.md"
pass "SOUL.md"

# 正文须简体中文；禁止 Form Feed 等控制字符（见 .cursor/rules/expert-template-docs.mdc §0）
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  fail "python3/python required for expert doc char check"
fi
# 业务模板强制简体中文正文；base/default 由 checker 内部跳过中文硬要求
ZH_FLAG=()
case "$EXPERT" in
  base|default) ;;
  *) ZH_FLAG=(--require-zh) ;;
esac
"$PY" "$BASE_DIR/scripts/lib/check_expert_doc_chars.py" "$TPL" "${ZH_FLAG[@]}" || fail "expert doc language/char check"

if [ -f "$TPL/team.yaml" ]; then
  pass "team.yaml present (profile team)"
  [ -d "$TPL/root" ] || fail "team template missing root/"
  [ -d "$TPL/profiles" ] || fail "team template missing profiles/"
else
  pass "single-expert template"
fi

if [ "$EXPERT" = "bi-strategic-office" ] || [ -d "$TPL/semantic" ]; then
  [ -d "$TPL/semantic/datasets" ] || fail "BI template missing semantic/datasets"
  [ -d "$TPL/semantic/metrics" ] || fail "BI template missing semantic/metrics"
  [ -d "$TPL/skills/bi-office-orchestration" ] || fail "missing bi-office-orchestration skill"
  [ -f "$TPL/config.patch.yaml" ] || fail "missing config.patch.yaml"
  [ -d "$TPL/policies" ] || fail "missing policies/"
  PLUGIN="$BASE_DIR/asset-bundles/hermes-finance-bi-plugin"
  [ -f "$PLUGIN/plugin.yaml" ] || fail "missing asset-bundles/hermes-finance-bi-plugin/plugin.yaml"
  [ -f "$PLUGIN/__init__.py" ] || fail "missing plugin __init__.py"
  pass "BI template + plugin bundle structure"
fi

echo "OK: validate-expert-template $EXPERT"
