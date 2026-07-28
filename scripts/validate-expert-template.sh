#!/usr/bin/env bash
# Validate expert template — delegates to Expert Factory CLI (v2.0).
# v1 experts: full validation; legacy experts: structure + doc checks (warnings for secrets).
set -euo pipefail

EXPERT="${1:?usage: validate-expert-template.sh <expert>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TPL="$BASE_DIR/expert-templates/$EXPERT"

if [ ! -d "$TPL" ]; then
  echo "FAIL: template not found: $TPL"
  exit 1
fi

LEVEL="full"
if [ -f "$TPL/expert.yaml" ] && grep -q 'workcopilot.expert.v1' "$TPL/expert.yaml" 2>/dev/null; then
  LEVEL="full"
else
  # Legacy / package manifests: structure is the compatibility gate
  LEVEL="structure"
fi

exec bash "$BASE_DIR/scripts/expert/expert" validate "$TPL" --level "$LEVEL" --format text
