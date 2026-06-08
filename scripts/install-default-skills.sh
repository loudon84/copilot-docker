#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:?usage: install-default-skills.sh <profile>}"
CONTAINER="hermes-${PROFILE}"

docker exec -u root -it "$CONTAINER" bash -lc '
set -euo pipefail

SRC=""

for d in \
  /opt/hermes-agent/skills \
  /opt/hermes/skills \
  /.hermes/hermes-agent/skills \
  /home/hermeswebui/.hermes/hermes-agent/skills
do
  if [ -d "$d" ] && find "$d" -name SKILL.md | grep -q .; then
    SRC="$d"
    break
  fi
done

[ -n "$SRC" ] || { echo "ERROR: bundled skills source not found"; exit 1; }

DST="/data/hermes/skills"
mkdir -p "$DST"

SRC="$SRC" DST="$DST" /app/venv/bin/python - <<PY
import os
import shutil
from pathlib import Path

src = Path(os.environ["SRC"])
dst = Path(os.environ["DST"])

def copy_missing(s: Path, d: Path):
    if s.is_dir():
        d.mkdir(parents=True, exist_ok=True)
        for child in s.iterdir():
            copy_missing(child, d / child.name)
    else:
        if not d.exists():
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)

for child in src.iterdir():
    copy_missing(child, dst / child.name)
PY

RUN_UID="${WANTED_UID:-1000}"
RUN_GID="${WANTED_GID:-1000}"

chown -R "$RUN_UID:$RUN_GID" "$DST"
find "$DST" -type d -exec chmod 750 {} \;
find "$DST" -type f -exec chmod 640 {} \;

echo "OK: default bundled skills installed"
find "$DST" -name SKILL.md | wc -l