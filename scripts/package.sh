#!/usr/bin/env bash
set -euo pipefail
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"
OUT_DIR="$BASE_DIR/dist"
mkdir -p "$OUT_DIR"
# Do not include instance data in default code package.
tar --exclude='./instances/*/data' --exclude='./dist' -czf "$OUT_DIR/hermes-agent-webui-obsidian-hindsight-kit-files.tar.gz" .
echo "$OUT_DIR/hermes-agent-webui-obsidian-hindsight-kit-files.tar.gz"
