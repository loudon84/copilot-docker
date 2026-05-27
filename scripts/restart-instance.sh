#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:?usage: restart-instance.sh <profile>}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"
docker compose --env-file "instances/$PROFILE/.env" -p "hermes-$PROFILE" restart
