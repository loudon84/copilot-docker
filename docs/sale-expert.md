# Sale 销售专家包

PRD v1.7 交付的 `sale` 专家模板，供 Hermes Agent 作为企业内部销售人员智能体使用。

## 快速开始

```bash
bash scripts/create-sale-instance.sh sale 9602
bash scripts/up-instance.sh sale
```

或分步：

```bash
bash scripts/create-instance.sh sale 9602 sale
bash scripts/inject-expert.sh sale sale
bash scripts/up-instance.sh sale
bash scripts/restart-instance.sh sale
```

访问：`http://<server-ip>:9602`

验收：

```bash
bash scripts/check-sale-expert.sh sale
```

## 专家包结构

```text
expert-templates/sale/
├── SOUL.md
├── memories/
│   ├── MEMORY.md
│   └── USER.md
├── policies/
│   └── sale-playbook.yaml
├── workspace/
│   └── sale/
│       └── README.md
└── skills/
    └── sales/
        ├── sales-discovery-brief/
        ├── sales-deal-assessment/
        ├── sales-outbound-sequence/
        ├── sales-proposal-brief/
        ├── sales-account-plan/
        ├── sales-pipeline-health/
        ├── sales-technical-discovery/
        └── sales-call-review/
```

`sale` 不自带 `config.yaml`，注入时继承 `expert-templates/base` 的 runtime（Hindsight、workspace MCP、obsidian-vault、gbrain）。

## 文档路由

| 内容 | 目录 |
|------|------|
| 客户原始文件、RFQ、BOM、CRM 导出 | `workspace/materials/sale` |
| 抽取的客户事实与会议摘要 | `workspace/references/sale` |
| 邮件草稿、话术、方案草稿 | `workspace/drafts/sale` |
| 商机评估、account plan、pipeline 报告 | `workspace/reports/sale` |
| 审核后的 docx/pdf 等交付物 | `workspace/exports/sale` |
| 仪表盘、HTML 表单 | `workspace/artifacts/sale` |
| 审核后的销售知识 | `obsidian-vault/60-Reports/Sales` |

客户敏感原始资料**不得**写入 Obsidian。对外话术必须标记为「草稿，发送前需人工确认」。

## 核心 Skills

| Skill | 用途 |
|-------|------|
| `sales-discovery-brief` | 客户拜访/电话前的发现问题清单 |
| `sales-deal-assessment` | MEDDPICC 商机评估 |
| `sales-outbound-sequence` | 外呼/邮件多触点 sequence |
| `sales-proposal-brief` | 方案与 proposal 草稿 |
| `sales-account-plan` | 客户经营、QBR、扩展计划 |
| `sales-pipeline-health` | Pipeline 健康与预测复盘 |
| `sales-technical-discovery` | 售前技术发现、Demo、POC |
| `sales-call-review` | 通话/会议复盘与辅导 |

## 示例提示词

1. 帮我针对 XX 公司做一个销售开发计划，目标是推荐我们的 IC 物料替代方案。
2. 这是客户当前沟通记录，帮我判断这个商机能不能进入重点跟进。
3. 根据客户需求，帮我生成一份销售方案草稿。
4. 帮我分析这个月 pipeline 健康情况。
5. 帮我为客户 A 做一个 QBR 和续费扩展计划。
6. 帮我做一个客户拜访前的 discovery brief。
7. 请按 MEDDPICC 评估这个商机。
8. 帮我写一封发给客户的报价跟进邮件。
9. 客户想找 STM32 替代料，但没有提供完整参数。帮我准备销售发现问题。
10. 根据这段会议纪要，帮我做销售通话复盘和辅导建议。

## 安全边界

以下内容必须经人工或授权系统确认，Agent 不得编造或承诺：

- 价格、库存、交期、账期、信用额度
- 法律条款、质量保证、产品等价性
- 客户案例、原厂关系、产品认证

## 相关文档

- PRD：[prd/v1.7_add-expert-sale.md](../prd/v1.7_add-expert-sale.md)
- 文档路由：[docs/document-routing.md](document-routing.md)
- 部署：[README_DEPLOY.md](../README_DEPLOY.md)
