#!/usr/bin/env bash
# 从旧版完整 config.yaml 导入到 instance，并自动补齐 memory / gbrain 等 runtime 段。
#
# 用法：
#   bash scripts/import-legacy-config.sh <profile> [legacy-config-path]
#
# 示例：
#   bash scripts/import-legacy-config.sh huang-xiaoqi instance/config.yaml

set -euo pipefail

PROFILE="${1:?usage: import-legacy-config.sh <profile> [legacy-config-path]}"
LEGACY_CONFIG="${2:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/instance/config.yaml}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$BASE_DIR/instances/$PROFILE/data/hermes/config.yaml"

if [ ! -f "$LEGACY_CONFIG" ]; then
  echo "ERROR: legacy config not found: $LEGACY_CONFIG" >&2
  exit 1
fi

if [ ! -f "$BASE_DIR/instances/$PROFILE/.env" ]; then
  echo "ERROR: instance not found: $PROFILE (先 create-instance)" >&2
  exit 1
fi

mkdir -p "$(dirname "$TARGET")"
TS="$(date +%Y%m%d-%H%M%S)"
if [ -f "$TARGET" ]; then
  mkdir -p "$BASE_DIR/instances/$PROFILE/data/hermes/.backup/$TS"
  cp "$TARGET" "$BASE_DIR/instances/$PROFILE/data/hermes/.backup/$TS/config.yaml"
fi

cp "$LEGACY_CONFIG" "$TARGET"
bash "$BASE_DIR/scripts/patch-config-runtime.sh" "$PROFILE"

echo "OK: imported legacy config → $TARGET"
echo "     runtime sections (memory / mcp_servers / gbrain / curator / security / terminal) 已合并"
