#!/usr/bin/env bash
set -euo pipefail

USE_CN_MIRRORS="${USE_CN_MIRRORS:-1}"
APT_MIRROR="${APT_MIRROR:-https://mirrors.aliyun.com/debian}"

echo "[apt-mirror] USE_CN_MIRRORS=${USE_CN_MIRRORS}"
echo "[apt-mirror] APT_MIRROR=${APT_MIRROR}"

if [ "${USE_CN_MIRRORS}" != "1" ]; then
  echo "[apt-mirror] CN mirrors disabled. Keep default Debian sources."
  exit 0
fi

if [ -f /etc/apt/sources.list.d/debian.sources ]; then
  sed -i "s|http://deb.debian.org/debian|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources || true
  sed -i "s|https://deb.debian.org/debian|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources || true
fi

if [ -f /etc/apt/sources.list ]; then
  sed -i "s|http://deb.debian.org/debian|${APT_MIRROR}|g" /etc/apt/sources.list || true
  sed -i "s|https://deb.debian.org/debian|${APT_MIRROR}|g" /etc/apt/sources.list || true
fi

echo "[apt-mirror] Effective apt sources:"
grep -R "URIs:\|deb.debian.org\|mirrors." /etc/apt/sources.list /etc/apt/sources.list.d 2>/dev/null || true
