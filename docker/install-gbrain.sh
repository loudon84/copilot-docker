#!/usr/bin/env bash
set -euo pipefail

INSTALL_GBRAIN="${INSTALL_GBRAIN:-1}"
GBRAIN_REPO="${GBRAIN_REPO:-http://git.superic.com/aiplatform/gbrain.git}"
GBRAIN_REF="${GBRAIN_REF:-master}"
BUN_VERSION="${BUN_VERSION:-bun-v1.2.15}"

if [ "$INSTALL_GBRAIN" != "1" ]; then
  echo "SKIP: INSTALL_GBRAIN=$INSTALL_GBRAIN"
  exit 0
fi

export BUN_INSTALL="${BUN_INSTALL:-/opt/bun}"
export PATH="$BUN_INSTALL/bin:/usr/local/bin:$PATH"

echo "== install bun =="
mkdir -p "$BUN_INSTALL"

if ! command -v bun >/dev/null 2>&1; then
  curl -fsSL https://bun.sh/install | bash -s -- "$BUN_VERSION"
fi

BUN_BIN="$(find "$BUN_INSTALL" /root/.bun /home/hermeswebui/.bun -type f -name bun 2>/dev/null | head -1 || true)"
test -n "$BUN_BIN"
chmod +x "$BUN_BIN"
ln -sf "$BUN_BIN" /usr/local/bin/bun

BUNX_BIN="$(find "$BUN_INSTALL" /root/.bun /home/hermeswebui/.bun -type f -name bunx 2>/dev/null | head -1 || true)"
if [ -n "$BUNX_BIN" ]; then
  chmod +x "$BUNX_BIN"
  ln -sf "$BUNX_BIN" /usr/local/bin/bunx
fi

command -v bun
bun --version

echo "== clone gbrain =="
rm -rf /opt/gbrain

if ! git clone --depth=1 --branch "$GBRAIN_REF" "$GBRAIN_REPO" /opt/gbrain; then
  echo "WARN: git clone with branch failed, fallback to default branch"
  git clone --depth=1 "$GBRAIN_REPO" /opt/gbrain
fi

test -f /opt/gbrain/package.json

cd /opt/gbrain

echo "== inspect package =="
node - <<'NODE'
const fs = require("fs");
const pkg = JSON.parse(fs.readFileSync("package.json", "utf8"));
console.log("name:", pkg.name);
console.log("bin:", JSON.stringify(pkg.bin || null, null, 2));
console.log("scripts:", JSON.stringify(pkg.scripts || null, null, 2));
NODE

echo "== install dependencies =="
export npm_config_legacy_peer_deps=true
export NPM_CONFIG_LEGACY_PEER_DEPS=true

npm config set legacy-peer-deps true

if [ -f package-lock.json ]; then
  npm ci --legacy-peer-deps || npm install --legacy-peer-deps
else
  npm install --legacy-peer-deps
fi

echo "== try install gbrain globally by npm =="
npm install -g . --legacy-peer-deps || echo "WARN: npm global install failed, will create wrapper fallback"

echo "== check global gbrain =="
if ! command -v gbrain >/dev/null 2>&1; then
  echo "WARN: npm did not create gbrain command, creating wrapper from package.json bin"

  BIN_REL="$(node - <<'NODE'
const fs = require("fs");
const pkg = JSON.parse(fs.readFileSync("package.json", "utf8"));
const bin = pkg.bin;
if (typeof bin === "string") {
  console.log(bin);
} else if (bin && bin.gbrain) {
  console.log(bin.gbrain);
} else if (bin && Object.keys(bin).length > 0) {
  console.log(bin[Object.keys(bin)[0]]);
}
NODE
)"

  test -n "$BIN_REL"
  BIN_ABS="/opt/gbrain/$BIN_REL"
  test -f "$BIN_ABS"

  cat > /usr/local/bin/gbrain <<EOF
#!/usr/bin/env bash
set -e
cd /opt/gbrain
export PATH="/opt/bun/bin:/usr/local/bin:\$PATH"
exec bun "$BIN_ABS" "\$@"
EOF

  chmod +x /usr/local/bin/gbrain
fi

echo "== final verify =="
command -v gbrain
ls -l "$(command -v gbrain)"
gbrain --help 2>&1 | head -80 || true

chmod -R a+rX /opt/bun /opt/gbrain

echo "OK: gbrain installed"
