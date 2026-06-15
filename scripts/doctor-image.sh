#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:-hermes-agent-webui:latest}"

docker run --rm --entrypoint bash "$IMAGE" -lc '
set -e

echo "== image =="
cat /etc/os-release | head || true

echo "== python =="
/app/venv/bin/python -V

echo "== hermes-agent import =="
/app/venv/bin/python - <<PY
from run_agent import AIAgent
print("OK: AIAgent importable")
PY

echo "== bun =="
which bun
bun --version

echo "== gbrain =="
which gbrain
ls -l "$(which gbrain)"
gbrain --help 2>&1 | head -80

echo "== node/npm =="
which node
node -v
which npm
npm -v

echo "OK: image doctor passed"
'
