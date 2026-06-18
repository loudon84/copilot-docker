#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-sale}"
PORT="${2:-9602}"

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash "$BASE_DIR/scripts/create-instance.sh" "$PROFILE" "$PORT" sale
bash "$BASE_DIR/scripts/inject-expert.sh" "$PROFILE" sale

echo "Sale instance created:"
echo "  profile=$PROFILE"
echo "  port=$PORT"
echo "Start:"
echo "  bash scripts/up-instance.sh $PROFILE"
