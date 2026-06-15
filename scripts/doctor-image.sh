#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:-hermes-agent-webui:latest}"

docker run --rm --entrypoint bash "$IMAGE" -lc '
set -e

echo "== python =="
/app/venv/bin/python -V

echo "== hermes-agent import =="
/app/venv/bin/python - <<PY
from run_agent import AIAgent
print("OK: AIAgent importable")
PY

echo "== gbrain =="
which gbrain
gbrain --help 2>&1 | head -80

echo "== filesystem mcp =="
which mcp-server-filesystem || true
which npx || true

echo "OK: image doctor passed"
'
