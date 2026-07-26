#!/usr/bin/env bash
# Run expert-package tests.
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUITE="${1:-unit}"

PYTHON_BIN="$(command -v python3 || command -v python || true)"
[[ -n "$PYTHON_BIN" ]] || { echo "ERROR: python required" >&2; exit 1; }

cd "$PACKAGE_ROOT"

case "$SUITE" in
  unit)
    "$PYTHON_BIN" -m pytest tests/unit -q
    ;;
  security)
    "$PYTHON_BIN" -m pytest tests/security -q
    ;;
  integration)
    "$PYTHON_BIN" -m pytest tests/integration -q
    ;;
  all)
    "$PYTHON_BIN" -m pytest tests/unit tests/security tests/deployment tests/integration -q
    ;;
  validate)
    bash "$PACKAGE_ROOT/bin/validate.sh"
    bash "$PACKAGE_ROOT/bin/doctor.sh" --package-only
    ;;
  *)
    echo "usage: test.sh [unit|security|integration|all|validate]"
    exit 1
    ;;
esac
