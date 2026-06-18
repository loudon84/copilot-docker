# 容器 Agent 文档产物归类与路径治理（v1.6）

> 对应 PRD：`prd/v1.6_hotfix_generate-path.md`

## 概述

所有 Hermes 容器实例在生成文件前必须按类型路由到正确目录，避免脚本、导出文件污染 Obsidian 知识库。

## 目录职责

| 目录 | 用途 |
|------|------|
| `workspace/materials` | 原始上传与外部下载资料 |
| `workspace/references` | 抽取后的引用材料 |
| `workspace/drafts` | 未定稿提纲、方案草稿 |
| `workspace/reports` | 未审核 Markdown 报告 |
| `workspace/exports` | 最终交付（docx/pdf/xlsx/pptx） |
| `workspace/artifacts` | HTML UI、图表、manifest |
| `workspace/scripts` | 生成的辅助脚本 |
| `workspace/runtime` | 运行态状态 |
| `workspace/tmp` | 临时文件 |
| `obsidian-vault/` | 仅长期 Markdown 知识 |
| `skills/` | Hermes skill 资产 |

## 策略文件

- 机器可读：`expert-templates/base/policies/document-routing.yaml` → 实例内 `/data/hermes/policies/document-routing.yaml`
- Agent 契约：`expert-templates/base/workspace/AGENTS.md`
- SOUL 规则：`expert-templates/base/SOUL.md`（各专家 SOUL 继承并扩展）

## MCP 配置

`config.yaml` 的 `mcp_servers` 必须同时包含：

- `workspace` → `/data/hermes/workspace`
- `obsidian_vault` → `/data/hermes/obsidian-vault`
- `gbrain`

由 `scripts/patch-config-runtime.sh` 或 `scripts/lib/patch_config_runtime.py` 自动合并。

## Skill

`system/document-output-router` 由 `scripts/install-blound-skills.sh` 安装，指导 Agent 在写文件前分类并生成 manifest。

## 运维命令

```bash
# 新建实例（自动 init 标准目录）
bash scripts/create-instance.sh writer 9601 writer

# 注入专家（目录与 create-instance 一致）
bash scripts/inject-expert.sh writer writer

# 单实例检查
bash scripts/check-document-routes.sh writer

# 全实例检查
bash scripts/check-document-routes.sh --all

# 修复：补目录、patch config、迁移 Obsidian 违规文件
bash scripts/repair-document-routes.sh writer --fix
bash scripts/repair-document-routes.sh --all --fix
```

## Obsidian 禁止扩展名

`.py` `.sh` `.js` `.ts` `.docx` `.pdf` `.xlsx` `.pptx` `.zip` `.tmp` `.log` 等不得写入 `obsidian-vault`。

## WebUI 约定

- 用户下载最终文件：优先 `workspace/exports`
- 工作过程文件：`workspace/drafts`、`workspace/reports`、`workspace/artifacts`
- Obsidian：仅知识库，非默认导出目录

## 相关脚本

| 脚本 | 作用 |
|------|------|
| `scripts/lib/init_hermes_dirs.sh` | 统一创建标准目录 |
| `scripts/lib/validate_document_routes.py` | 校验与 `--fix` 迁移 |
| `scripts/check-document-routes.sh` | 实例级检查封装 |
| `scripts/repair-document-routes.sh` | 目录修复 + config + 校验 |
