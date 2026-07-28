---
schema_version: workcopilot.skill.v1
id: sales-proposal-brief
name: 写方案、销售方案、客户建议书、proposal、投标草稿、报价说明。不编造价格、
version: 1.0.0
description: 写方案、销售方案、客户建议书、proposal、投标草稿、报价说明。不编造价格、交期与案例。
triggers:
- 写方案、销售方案、客户建议书、proposal、投标草稿、报价说明。不编造价格、
scope:
  includes:
  - 写方案、销售方案、客户建议书、proposal、投标草稿、报价说明。不编造价格、交期与案例。
  excludes:
  - 写入生产系统
  - 泄露密钥
  - 输出未标注的编造事实
inputs:
  required: []
  optional: []
outputs:
  format: structured-markdown
tool_requirements: []
connector_requirements: []
permissions:
  access_mode: read-only
  data_classification: internal
---

# 技能目标

写方案、销售方案、客户建议书、proposal、投标草稿、报价说明。不编造价格、交期与案例。

# 适用条件

当用户请求与「写方案、销售方案、客户建议书、proposal、投标草稿、报价说明。不编造价格、」相关的任务时使用本技能。

# 前置检查

- 确认任务目标与输入材料是否齐全。
- 确认不需要写入外部生产系统。

# 执行流程

1. 澄清目标、受众与约束。
2. 基于可用上下文完成分析或写作。
3. 按输出要求交付，并标注不确定项。

# 工具调用规则

- 仅使用专家权限允许的工具。
- 默认只读；不得越权调用。

# 输出要求

- 不编造价格、交期、库存、客户案例、原厂关系。
- 所有 customer-facing 内容标记为「草稿，发送前需人工确认」。
- Markdown 草稿进入 `/data/hermes/workspace/drafts/sale/proposals/`。
- 最终 docx/pdf 经人工审核后进入 `/data/hermes/workspace/exports/sale/`。
- 审核后的 win themes 可沉淀至 `/data/hermes/obsidian-vault/60-Reports/Sales`。

# 异常处理

- 关键条件缺失时先追问，不臆造。
- 外部数据不可用时明确说明限制。

# 禁止事项

- 不写入生产系统。
- 不泄露密钥、凭证或未授权数据。
- 不编造未标注的事实与来源。

# 引用资料

- 无额外引用（详见专家 SOUL 与工作区约定）
