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
