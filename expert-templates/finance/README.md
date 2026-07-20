# finance

财务运营专家：财务分析、发票审阅、现金流摘要、付款风险说明与审计追溯写作。

`SOUL.md` / `workspace/AGENTS.md` / `skills/**/SKILL.md` 说明正文为简体中文（工具名等标识可英文）。

## 能力边界

| 场景 | 是否负责 |
|------|----------|
| 账户、账龄、回款、头寸、资金计划、财务运营 | 是 |
| BI 取数、经营分析、产品/客户/区域利润 | 否 → 见 `bi-strategic-office` |
| 长文 / PRD / 内容生产 | 否 → 见 `writer` |
| 企业销售、商机、提案 | 否 → 见 `sale` |

## 模板结构

```text
expert-templates/finance/
├── SOUL.md
├── memories/
├── skills/finance/          # ar-aging-review, cashflow-forecast, variance-analysis 等
└── workspace/AGENTS.md
```

## 创建与注入

```bash
# 创建实例（WebUI 8788，Gateway 28788）
bash scripts/create-instance.sh finance 8788 finance

# 重新注入（幂等）
bash scripts/inject-expert.sh finance finance
bash scripts/restart-instance.sh finance

# 校验模板结构
bash scripts/validate-expert-template.sh finance
```

## 访问

```text
WebUI:  http://服务器IP:8788
API:    http://服务器IP:28788
```

查看密码：

```bash
grep HERMES_WEBUI_PASSWORD instances/finance/.env
```

## 运行时目录

注入后工作区位于 `instances/finance/data/hermes/`：

| 产出 | 目录 |
|------|------|
| 银行流水、发票、原始数据 | `workspace/materials/finance` |
| 工作草稿 | `workspace/drafts/finance` |
| 审计 / 分析 Markdown（待审） | `workspace/reports/finance` |
| 最终 Excel/PDF | `workspace/exports/finance` |
| 审阅后的摘要归档 | `obsidian-vault/60-Reports` |

**禁止**将凭证、密钥、原始敏感交易明细写入 Obsidian。
