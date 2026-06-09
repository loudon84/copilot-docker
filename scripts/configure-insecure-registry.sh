#!/usr/bin/env bash
# 将本地 Registry 地址写入 Docker daemon insecure-registries 并重启 Docker
#
# 注意：需要 sudo 权限；所有需要 push/pull 的 Docker 主机均需执行。
#
# 用法：
#   sudo bash scripts/configure-insecure-registry.sh

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

LOCAL_REGISTRY_ENV="$BASE_DIR/local-registry.env"
if [ -f "$LOCAL_REGISTRY_ENV" ]; then
  # shellcheck disable=SC1090
  set -a
  source "$LOCAL_REGISTRY_ENV"
  set +a
  echo "[config] loaded $LOCAL_REGISTRY_ENV"
else
  echo "WARN: $LOCAL_REGISTRY_ENV 不存在，使用默认值" >&2
fi

LOCAL_REGISTRY_HOST="${LOCAL_REGISTRY_HOST:-192.168.102.247}"
LOCAL_REGISTRY_PORT="${LOCAL_REGISTRY_PORT:-9900}"
REGISTRY_ADDR="${LOCAL_REGISTRY_HOST}:${LOCAL_REGISTRY_PORT}"

DAEMON_JSON="/etc/docker/daemon.json"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: 需要 root 权限，请使用: sudo bash $0" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker 未安装" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 未安装，无法合并 daemon.json" >&2
  exit 1
fi

echo "[config] 添加 insecure registry: $REGISTRY_ADDR"

python3 - "$DAEMON_JSON" "$REGISTRY_ADDR" <<'PY'
import json
import os
import sys

path, addr = sys.argv[1], sys.argv[2]

data = {}
if os.path.isfile(path):
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
        if content:
            data = json.loads(content)

insecure = data.get("insecure-registries", [])
if not isinstance(insecure, list):
    insecure = []

if addr not in insecure:
    insecure.append(addr)
    data["insecure-registries"] = insecure

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"[write] 已更新 {path}")
else:
    print(f"[skip] {addr} 已在 insecure-registries 中")
PY

echo "[restart] 重启 Docker..."
if command -v systemctl >/dev/null 2>&1; then
  systemctl restart docker
else
  service docker restart
fi

echo
echo "========================================"
echo "Docker insecure registry 配置完成"
echo "========================================"
echo
echo "当前 Insecure Registries:"
docker info 2>/dev/null | sed -n '/Insecure Registries:/,/^[^ ]/p' | head -20 || true
echo
echo "验证: curl http://${REGISTRY_ADDR}/v2/_catalog"
echo
