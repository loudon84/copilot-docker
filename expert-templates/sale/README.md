# sale

企业销售助手：客户研究、线索甄别、销售发现、商机策略、提案准备、售前协调、管道复盘与销售辅导。

`SOUL.md` / `skills/**/SKILL.md` 说明正文为简体中文（工具名等标识可英文）。

## 能力边界

| 场景 | 是否负责 |
|------|----------|
| 客户研究、商机评估、提案、管道健康、销售辅导 | 是 |
| 财务分析、回款、账龄 | 否 → 见 `finance` |
| BI 取数、经营分析 | 否 → 见 `bi-strategic-office` |
| 长文 / PRD / 内容生产 | 否 → 见 `writer` |

## 模板结构

```text
expert-templates/sale/
├── SOUL.md
├── memories/
├── policies/sale-playbook.yaml
├── skills/sales/            # sales-discovery-brief, sales-deal-assessment, sales-proposal-brief 等
└── workspace/
```

## 创建与注入

```bash
# 创建实例（WebUI 9602，Gateway 29602）
bash scripts/create-instance.sh sale 9602 sale

# 重新注入（幂等）
bash scripts/inject-expert.sh sale sale
bash scripts/restart-instance.sh sale

# 校验模板与技能
bash scripts/check-sale-expert.sh sale
bash scripts/validate-expert-template.sh sale
```

## 访问

```text
WebUI:  http://服务器IP:9602
API:    http://服务器IP:29602
```

查看密码：

```bash
grep HERMES_WEBUI_PASSWORD instances/sale/.env
```

## 运行时要点

- 客户对外输出均为草稿，须人工审阅后方可发出。
- 库存、价格、交期、信用条款、法律条款须从授权系统或人员确认，不可臆造。
- 敏感客户信息保留在 `/data/hermes` 内。
- 文档路由遵循 `policies/document-routing.yaml` 与 `workspace/AGENTS.md`。
