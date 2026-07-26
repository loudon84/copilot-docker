#!/usr/bin/env bash
# Validate bi-strategic-office expert package layout (PRD v1.11).
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --package-root)
      PACKAGE_ROOT="$2"
      shift 2
      ;;
    -h|--help)
      echo "usage: validate.sh [--package-root <dir>]"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

FAIL=0
pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; FAIL=1; }

require_file() {
  local rel="$1"
  if [[ -f "$PACKAGE_ROOT/$rel" ]]; then
    pass "file $rel"
  else
    fail "missing file $rel"
  fi
}

require_dir() {
  local rel="$1"
  if [[ -d "$PACKAGE_ROOT/$rel" ]]; then
    pass "dir $rel"
  else
    fail "missing dir $rel"
  fi
}

require_file "expert.yaml"
require_file "VERSION"
require_file "runtime/SOUL.md"
require_file "runtime/memories/MEMORY.md"
require_file "runtime/config.patch.yaml"
require_file "plugins/hermes-sqlbot-adapter/plugin.yaml"
require_file "plugins/hermes-sqlbot-adapter/requirements.txt"
require_file "config/sqlbot.example.env"
require_dir "plugins/hermes-sqlbot-adapter"
require_dir "runtime/skills"
require_dir "config"
require_dir "evaluations"

for script in install.sh post-start.sh update.sh validate.sh doctor.sh test.sh; do
  require_file "bin/$script"
  if [[ -f "$PACKAGE_ROOT/bin/$script" ]]; then
    if [[ -x "$PACKAGE_ROOT/bin/$script" ]]; then
      pass "executable bin/$script"
    else
      if [[ "$(uname -s 2>/dev/null || true)" == MINGW* ]] || [[ "$(uname -s 2>/dev/null || true)" == MSYS* ]] || [[ -n "${WINDIR:-}" ]]; then
        pass "bin/$script present (Windows: +x may be restored by git)"
      else
        fail "bin/$script not executable"
      fi
    fi
  fi
done

if [[ -d "$PACKAGE_ROOT/plugins/hermes-finance-bi-plugin" ]]; then
  fail "legacy hermes-finance-bi-plugin must be removed"
else
  pass "legacy plugin absent"
fi

if [[ -f "$PACKAGE_ROOT/.env" ]]; then
  fail "package must not contain .env"
else
  pass "no .env in package root"
fi

if find "$PACKAGE_ROOT" -type f \( -name '*.db' -o -name 'finance_bi.db' -o -name 'sqlbot_sessions.db' \) 2>/dev/null | grep -q .; then
  fail "package must not contain runtime state databases"
else
  pass "no state databases in package"
fi

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [[ -n "$PYTHON_BIN" ]]; then
  if "$PYTHON_BIN" "$PACKAGE_ROOT/lib/validate_manifest.py" --package-root "$PACKAGE_ROOT"; then
    pass "validate_manifest.py"
  else
    fail "validate_manifest.py"
  fi
else
  echo "WARN: python not found; skipped deep YAML validation"
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "validate.sh: FAILED"
  exit 1
fi
echo "validate.sh: OK"
exit 0
