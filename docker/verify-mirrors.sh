#!/usr/bin/env bash
set -euo pipefail

echo "== APT sources =="
grep -R "URIs:\|deb.debian.org\|mirrors." /etc/apt/sources.list /etc/apt/sources.list.d 2>/dev/null || true

echo "== pip config =="
python3 -m pip config list 2>/dev/null || true
echo "PIP_INDEX_URL=${PIP_INDEX_URL:-}"

echo "== uv config =="
echo "UV_DEFAULT_INDEX=${UV_DEFAULT_INDEX:-}"

echo "== npm config =="
npm config get registry 2>/dev/null || true
echo "NPM_CONFIG_REGISTRY=${NPM_CONFIG_REGISTRY:-}"
