#!/usr/bin/env bash
set -euo pipefail

# install-blound-skills.sh
#
# Purpose:
#   Merge default bundled skills installer and writer awesome skills installer.
#
# Usage:
#   bash scripts/install-blound-skills.sh writer
#   bash scripts/install-blound-skills.sh writer --no-awesome
#   bash scripts/install-blound-skills.sh writer --no-restart
#
# Assumptions:
#   - Host project root is /data/hermes or current working directory.
#   - Container name is hermes-<profile>, e.g. hermes-writer.
#   - Hermes home inside container is /data/hermes.
#   - WebUI / Hermes Python is /app/venv/bin/python.
#
# This script:
#   1. Backs up current /data/hermes/skills.
#   2. Copies bundled Hermes skills from the hermes-agent source inside the container.
#   3. Attempts to install selected awesome/community skills through Hermes CLI.
#   4. Installs Hermes-native local skills:
#      - hermes/create-skill
#      - ui/html-ui-artifact
#      - hermes/skill-audit
#   5. Fixes permissions.
#   6. Restarts the target container unless --no-restart is passed.

PROFILE="${1:-writer}"
shift || true

INSTALL_DEFAULT=1
INSTALL_AWESOME=1
INSTALL_LOCAL=1
RESTART_AFTER=1

while [ $# -gt 0 ]; do
  case "$1" in
    --no-default)
      INSTALL_DEFAULT=0
      ;;
    --no-awesome)
      INSTALL_AWESOME=0
      ;;
    --no-local)
      INSTALL_LOCAL=0
      ;;
    --no-restart)
      RESTART_AFTER=0
      ;;
    -h|--help)
      sed -n '1,80p' "$0"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1"
      exit 1
      ;;
  esac
  shift
done

CONTAINER="hermes-${PROFILE}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "ERROR: container not running: $CONTAINER"
  echo "Start it first:"
  echo "  cd $BASE_DIR"
  echo "  bash scripts/up-instance.sh $PROFILE"
  exit 1
fi

echo "Profile:          $PROFILE"
echo "Container:        $CONTAINER"
echo "Install default:  $INSTALL_DEFAULT"
echo "Install awesome:  $INSTALL_AWESOME"
echo "Install local:    $INSTALL_LOCAL"
echo "Restart after:    $RESTART_AFTER"
echo

docker exec -u root -i \
  -e INSTALL_DEFAULT="$INSTALL_DEFAULT" \
  -e INSTALL_AWESOME="$INSTALL_AWESOME" \
  -e INSTALL_LOCAL="$INSTALL_LOCAL" \
  "$CONTAINER" bash <<'EOS'
set -euo pipefail

export HERMES_HOME=/data/hermes
export HERMES_CONFIG_PATH=/data/hermes/config.yaml

echo "[0/6] Runtime info"
echo "user=$(id)"
echo "HERMES_HOME=$HERMES_HOME"
echo "HERMES_CONFIG_PATH=$HERMES_CONFIG_PATH"
echo

if [ -x /app/venv/bin/hermes ]; then
  hermes_cmd() { /app/venv/bin/hermes "$@"; }
else
  hermes_cmd() { /app/venv/bin/python -m hermes_cli.main "$@"; }
fi

RUN_UID="${WANTED_UID:-1000}"
RUN_GID="${WANTED_GID:-1000}"

mkdir -p /data/hermes/skills /data/hermes/workspace /data/hermes/backups

echo "[1/6] Backup current skills"
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP="/data/hermes/backups/skills-before-install-blound-${TS}.tar.gz"
if [ -d /data/hermes/skills ]; then
  tar czf "$BACKUP" -C /data/hermes skills || true
  echo "backup=$BACKUP"
else
  echo "No existing skills directory found."
fi
echo

if [ "$INSTALL_DEFAULT" = "1" ]; then
  echo "[2/6] Install bundled Hermes default skills"

  SRC=""

  for d in \
    /opt/hermes-agent/skills \
    /opt/hermes/skills \
    /.hermes/hermes-agent/skills \
    /home/hermeswebui/.hermes/hermes-agent/skills \
    /app/hermes-agent/skills
  do
    if [ -d "$d" ] && find "$d" -name SKILL.md | grep -q .; then
      SRC="$d"
      break
    fi
  done

  if [ -z "$SRC" ]; then
    echo "WARN: bundled skills source not found."
    echo "Checked:"
    echo "  /opt/hermes-agent/skills"
    echo "  /opt/hermes/skills"
    echo "  /.hermes/hermes-agent/skills"
    echo "  /home/hermeswebui/.hermes/hermes-agent/skills"
    echo "  /app/hermes-agent/skills"
  else
    DST="/data/hermes/skills"
    echo "Bundled source: $SRC"
    echo "Target skills:   $DST"

    SRC="$SRC" DST="$DST" /app/venv/bin/python - <<'PY'
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

print("OK: bundled skills copied without overwriting existing files")
PY
  fi
else
  echo "[2/6] Skip bundled default skills"
fi

echo

if [ "$INSTALL_AWESOME" = "1" ]; then
  echo "[3/6] Install selected awesome/community skills"

  hermes_cmd skills list >/tmp/hermes-skills-before.txt 2>&1 || true

  install_skill() {
    local id="$1"
    echo
    echo ">>> install skill: $id"
    if hermes_cmd skills install "$id" --force; then
      echo "OK: $id"
    else
      echo "WARN: install failed or blocked by scanner: $id"
    fi
  }

  # Skill creator: create / optimize / audit skills.
  install_skill "anthropics/skills/skills/skill-creator"

  # HTML / frontend / artifact direction.
  install_skill "anthropics/skills/skills/web-artifacts-builder"
  install_skill "anthropics/skills/skills/theme-factory"
  install_skill "anthropics/skills/skills/frontend-design"

  # Document production for writer profile.
  install_skill "anthropics/skills/skills/pptx"
  install_skill "anthropics/skills/skills/pdf"
  install_skill "anthropics/skills/skills/docx"
  install_skill "anthropics/skills/skills/xlsx"

  # Web testing / MCP builder for future Hermes WebUI and Agent extensions.
  install_skill "anthropics/skills/skills/webapp-testing"
  install_skill "anthropics/skills/skills/mcp-builder"

else
  echo "[3/6] Skip awesome/community skills"
fi

echo

if [ "$INSTALL_LOCAL" = "1" ]; then
  echo "[4/6] Install Hermes-native local skills"

  mkdir -p /data/hermes/skills/hermes/create-skill
  cat > /data/hermes/skills/hermes/create-skill/SKILL.md <<'SKILL'
---
name: create-skill
description: Create or update Hermes Agent skills inside /data/hermes/skills. Use when the user asks to create a new skill, convert a workflow into a skill, optimize an existing SKILL.md, or make a reusable capability for this Hermes profile.
version: 1.0.0
category: hermes
---

# Hermes Create Skill

This skill creates, updates, and validates Hermes Agent skills for the current profile.

## Target Runtime

- Hermes home: `/data/hermes`
- Skills root: `/data/hermes/skills`
- Preferred structure: `/data/hermes/skills/<category>/<skill-name>/SKILL.md`
- Optional resources:
  - `scripts/`
  - `references/`
  - `assets/`
  - `examples/`
  - `evals/`

## Required Output

When creating a skill, always produce files on disk, not only text in chat.

Minimum file:

```text
/data/hermes/skills/<category>/<skill-name>/SKILL.md
```

Required frontmatter:

```yaml
---
name: <skill-name>
description: <clear activation condition and capability>
version: 1.0.0
category: <category>
---
```

## Creation Workflow

1. Clarify these fields if missing:
   - skill name
   - category
   - user goal
   - activation condition
   - expected input
   - expected output
   - allowed tools
   - forbidden actions
   - examples

2. Normalize the skill name:
   - lowercase
   - use `-`
   - only `[a-z0-9-]`
   - no spaces
   - no Chinese characters in folder name

3. Create directory:

```bash
mkdir -p /data/hermes/skills/<category>/<skill-name>
```

4. Write `SKILL.md`.

5. If needed, create:
   - `references/README.md`
   - `examples/example-1.md`
   - `scripts/validate.py`

6. Validate:
   - `SKILL.md` exists
   - frontmatter has `name` and `description`
   - description states when the skill should be used
   - no secrets are embedded
   - no destructive commands are included unless explicitly required

7. Return:
   - skill path
   - slash command name
   - usage examples
   - restart/new-session instruction if WebUI does not refresh immediately

## Security Rules

- Never embed API keys, passwords, tokens, or private URLs in `SKILL.md`.
- Do not create skills that run destructive shell commands by default.
- For business users, prefer read/write under `/data/hermes/workspace` and `/data/hermes/obsidian-vault`.
- Any skill that calls external APIs must list required environment variables.
- Any skill with scripts must avoid interactive prompts.

## Example User Commands

- “创建一个合同审阅 skill，输出审阅清单和风险等级。”
- “把这个写作流程沉淀成 skill。”
- “优化 article-draft 的 SKILL.md，让触发更准确。”
- “创建一个能生成 HTML 表单的 skill。”
SKILL

  mkdir -p /data/hermes/skills/ui/html-ui-artifact/scripts
  cat > /data/hermes/skills/ui/html-ui-artifact/SKILL.md <<'SKILL'
---
name: html-ui-artifact
description: Generate self-contained interactive HTML UI artifacts for Hermes WebUI tasks. Use when the user asks for HTML UI, interactive forms, dashboards, cards, calculators, visual reports, or agent output that should be opened as a web page.
version: 1.0.0
category: ui
---

# HTML UI Artifact

This skill creates self-contained interactive HTML UI files for Hermes Agent.

## Output Contract

Always create a real `.html` file under:

```text
/data/hermes/workspace/artifacts/
```

Recommended filename:

```text
/data/hermes/workspace/artifacts/<yyyyMMdd-HHmmss>-<slug>.html
```

Then return:

```markdown
已生成 HTML UI:
- 文件: `/data/hermes/workspace/artifacts/<file>.html`
- 用途: <short purpose>
- 交互能力: <buttons/forms/tables/charts/local state>
```

## Technical Requirements

The generated HTML must be:

- Single-file HTML.
- No external CDN by default.
- No remote JavaScript.
- No external tracking.
- No embedded secrets.
- Uses inline CSS and inline JavaScript.
- Can run by opening the file directly in a browser.
- Business text should support Chinese.
- Layout should be responsive.
- Use semantic HTML.
- Use accessible labels for form fields and buttons.

## UI Types

Use this skill for:

- interactive article brief form
- PRD generator form
- content calendar dashboard
- finance report viewer
- task review checklist
- approval card
- agent run status panel
- knowledge base search mock UI
- comparison tables
- lightweight calculators

## Implementation Pattern

For each artifact:

1. Create `/data/hermes/workspace/artifacts` if missing.
2. Generate HTML with:
   - header
   - main content region
   - controls
   - output panel
   - local state if needed
3. Use vanilla JavaScript unless user explicitly asks for React.
4. Keep the artifact independent from Hermes WebUI internals.
5. If the user wants future integration with Hermes WebUI, also output an `artifact_contract` block in Markdown:

```yaml
artifact_contract:
  type: html_ui
  file: /data/hermes/workspace/artifacts/<file>.html
  title: <title>
  description: <description>
  inputs:
    - name: <field>
      type: <text|select|number|textarea>
  actions:
    - id: <action-id>
      label: <label>
```

## Security Rules

- Do not include remote scripts.
- Do not submit forms to external URLs.
- Do not read local files.
- Do not attempt to access cookies, tokens, or browser storage outside the artifact.
- Do not include business secrets in the HTML.
- Use demo/mock data unless the user explicitly provides data.

## Example User Commands

- “生成一个文章选题表单 HTML UI。”
- “用 HTML 生成一个写作任务看板，可以本地交互。”
- “输出一个财务报告审阅 dashboard。”
- “把这个 PRD 流程做成交互式 HTML 页面。”
SKILL

  cat > /data/hermes/skills/ui/html-ui-artifact/scripts/new_artifact.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "artifact"

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--slug", default="")
    parser.add_argument("--out-dir", default="/data/hermes/workspace/artifacts")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = slugify(args.slug or args.title)
    path = out_dir / f"{stamp}-{slug}.html"

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{args.title}</title>
  <style>
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f6f3ee;
      color: #1f2933;
    }}
    main {{
      max-width: 960px;
      margin: 40px auto;
      padding: 24px;
      background: #fff;
      border: 1px solid #e5dfd6;
      border-radius: 16px;
    }}
    button {{
      border: 0;
      border-radius: 10px;
      padding: 10px 14px;
      cursor: pointer;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{args.title}</h1>
    <p>这是 Hermes Agent 生成的交互式 HTML UI artifact。</p>
    <button onclick="document.getElementById('result').textContent = new Date().toLocaleString()">运行交互</button>
    <pre id="result"></pre>
  </main>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
    print(path)

if __name__ == "__main__":
    main()
PY

  chmod +x /data/hermes/skills/ui/html-ui-artifact/scripts/new_artifact.py

  mkdir -p /data/hermes/skills/hermes/skill-audit
  cat > /data/hermes/skills/hermes/skill-audit/SKILL.md <<'SKILL'
---
name: skill-audit
description: Audit installed Hermes skills for structure, activation description quality, missing SKILL.md files, unsafe commands, secrets, and maintainability issues.
version: 1.0.0
category: hermes
---

# Skill Audit

Use this skill to inspect `/data/hermes/skills` and produce a concise audit report.

## Audit Checks

- Count all `SKILL.md` files.
- Detect folders without `SKILL.md`.
- Validate YAML frontmatter.
- Confirm each skill has `name` and `description`.
- Detect overly broad descriptions.
- Detect possible secrets:
  - API keys
  - tokens
  - passwords
  - private endpoints
- Detect destructive commands:
  - `rm -rf`
  - `sudo`
  - `mkfs`
  - `dd if=`
  - unrestricted `chmod -R 777`
- Detect scripts that require interactive prompts.

## Output

Return:

- total skills
- invalid skills
- risky skills
- recommended fixes
- exact file paths
SKILL

else
  echo "[4/6] Skip Hermes-native local skills"
fi

echo

echo "[5/6] Fix permissions"
chown -R "$RUN_UID:$RUN_GID" /data/hermes/skills /data/hermes/workspace /data/hermes/backups || true
find /data/hermes/skills -type d -exec chmod 750 {} \;
find /data/hermes/skills -type f -exec chmod 640 {} \;
find /data/hermes/skills -path "*/scripts/*" -type f \( -name "*.py" -o -name "*.sh" \) -exec chmod 750 {} \;

echo

echo "[6/6] Report"
echo "Installed SKILL.md count:"
find /data/hermes/skills -name SKILL.md | wc -l

echo
echo "Top skill categories:"
find /data/hermes/skills -mindepth 1 -maxdepth 1 -type d -printf "%f\n" | sort || true

echo
echo "Key installed skills:"
find /data/hermes/skills -path "*/SKILL.md" | grep -E 'skill-creator|create-skill|html-ui-artifact|web-artifacts|theme-factory|frontend|pptx|pdf|docx|xlsx|webapp-testing|mcp-builder|skill-audit' | sort || true

echo
echo "OK: install-blound-skills finished"
EOS

if [ "$RESTART_AFTER" = "1" ]; then
  echo
  echo "Restart container: $CONTAINER"
  docker restart "$CONTAINER" >/dev/null
  echo "Container restarted."
else
  echo
  echo "Skip restart. Restart manually when needed:"
  echo "  docker restart $CONTAINER"
fi

echo
echo "Verify:"
echo "  docker exec -it $CONTAINER bash -lc 'find /data/hermes/skills -name SKILL.md | wc -l'"
echo "  docker logs --tail=100 $CONTAINER"
echo
echo "If WebUI does not refresh the skills list, create a new chat session or refresh the page."
