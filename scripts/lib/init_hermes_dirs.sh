#!/usr/bin/env bash
# 统一创建 /data/hermes 标准目录结构（PRD v1.7 document-routing）
#
# 用法:
#   source scripts/lib/init_hermes_dirs.sh
#   init_hermes_dirs "/path/to/instances/<profile>/data/hermes"

init_hermes_dirs() {
  local DATA_DIR="${1:?usage: init_hermes_dirs <data_dir>}"

  mkdir -p \
    "$DATA_DIR" \
    "$DATA_DIR/workspace" \
    "$DATA_DIR/workspace/materials" \
    "$DATA_DIR/workspace/references" \
    "$DATA_DIR/workspace/drafts" \
    "$DATA_DIR/workspace/reports" \
    "$DATA_DIR/workspace/exports" \
    "$DATA_DIR/workspace/artifacts" \
    "$DATA_DIR/workspace/scripts" \
    "$DATA_DIR/workspace/runtime" \
    "$DATA_DIR/workspace/tmp" \
    "$DATA_DIR/obsidian-vault" \
    "$DATA_DIR/obsidian-vault/00-Inbox" \
    "$DATA_DIR/obsidian-vault/10-Articles" \
    "$DATA_DIR/obsidian-vault/20-Research" \
    "$DATA_DIR/obsidian-vault/30-Templates" \
    "$DATA_DIR/obsidian-vault/40-Skills" \
    "$DATA_DIR/obsidian-vault/50-Memory" \
    "$DATA_DIR/obsidian-vault/60-Reports" \
    "$DATA_DIR/obsidian-vault/60-Reports/Sales" \
    "$DATA_DIR/workspace/materials/sale" \
    "$DATA_DIR/workspace/references/sale" \
    "$DATA_DIR/workspace/drafts/sale" \
    "$DATA_DIR/workspace/reports/sale" \
    "$DATA_DIR/workspace/exports/sale" \
    "$DATA_DIR/workspace/artifacts/sale" \
    "$DATA_DIR/obsidian-vault/70-Brain" \
    "$DATA_DIR/obsidian-vault/80-Product-Spec" \
    "$DATA_DIR/obsidian-vault/90-Archive" \
    "$DATA_DIR/skills" \
    "$DATA_DIR/skill-inbox" \
    "$DATA_DIR/tools" \
    "$DATA_DIR/plugins" \
    "$DATA_DIR/mcp" \
    "$DATA_DIR/policies" \
    "$DATA_DIR/logs" \
    "$DATA_DIR/sessions" \
    "$DATA_DIR/memories" \
    "$DATA_DIR/gbrain" \
    "$DATA_DIR/hindsight" \
    "$DATA_DIR/backups" \
    "$DATA_DIR/webui" \
    "$DATA_DIR/webui/attachments" \
    "$DATA_DIR/evolution/runs" \
    "$DATA_DIR/evolution/reports" \
    "$DATA_DIR/skill-bundles" \
    "$DATA_DIR/attachments"
}
