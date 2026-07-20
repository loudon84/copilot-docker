# writer

中文写作与内容生产专家：长文撰写、PRD 生成、技术报告、IC 材料审阅、文章草稿与溯源写作。

`SOUL.md` / `workspace/AGENTS.md` / `skills/**/SKILL.md` 说明正文为简体中文（工具名等标识可英文）。

## 能力边界

| 场景 | 是否负责 |
|------|----------|
| 长文 / PRD / 技术报告 / 文章草稿 | 是 |
| 财务分析、回款、账龄 | 否 → 见 `finance` |
| 企业销售、商机、提案 | 否 → 见 `sale` |
| BI 取数、经营分析 | 否 → 见 `bi-strategic-office` |

## 模板结构

```text
expert-templates/writer/
├── SOUL.md
├── memories/
├── skills/writing/          # article-outline, article-draft, article-polish, fact-check-research 等
├── workspace/AGENTS.md
└── obsidian-vault/30-Templates/
```

## 创建与注入

```bash
# 创建实例（WebUI 8787，Gateway 28787）
bash scripts/create-instance.sh writer 8787 writer

# 重新注入（幂等）
bash scripts/inject-expert.sh writer writer
bash scripts/restart-instance.sh writer

# 校验模板结构
bash scripts/validate-expert-template.sh writer
```

## 访问

```text
WebUI:  http://服务器IP:8787
API:    http://服务器IP:28787
```

查看密码：

```bash
grep HERMES_WEBUI_PASSWORD instances/writer/.env
```

## 运行时目录

注入后工作区位于 `instances/writer/data/hermes/`：

| 产出 | 目录 |
|------|------|
| 原始素材 | `workspace/materials` |
| 大纲与草稿 | `workspace/drafts` |
| 待审阅 Markdown 报告 | `workspace/reports` |
| 最终交付物（docx/pdf/xlsx/pptx） | `workspace/exports` |
| 审阅后的 IC 规格 Markdown | `obsidian-vault/80-Product-Spec` |
