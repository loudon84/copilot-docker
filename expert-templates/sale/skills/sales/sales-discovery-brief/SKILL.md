---
schema_version: workcopilot.skill.v1
id: sales-discovery-brief
name: '准备客户电话、客户拜访、需求调研、客户问题清单、销售发现问题（SPIN/Gap '
version: 1.0.0
description: 准备客户电话、客户拜访、需求调研、客户问题清单、销售发现问题（SPIN/Gap Selling）。先发现再建议，不直接 pitch。
triggers:
- '准备客户电话、客户拜访、需求调研、客户问题清单、销售发现问题（SPIN/Gap '
scope:
  includes:
  - 准备客户电话、客户拜访、需求调研、客户问题清单、销售发现问题（SPIN/Gap Selling）。先发现再建议，不直接 pitch。
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

准备客户电话、客户拜访、需求调研、客户问题清单、销售发现问题（SPIN/Gap Selling）。先发现再建议，不直接 pitch。

# 适用条件

当用户请求与「准备客户电话、客户拜访、需求调研、客户问题清单、销售发现问题（SPIN/Gap 」相关的任务时使用本技能。

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

- 不直接 pitch 产品或方案。
- 先发现，再建议。
- 用客户行业和场景语言，避免泛化营销话术。
- 标记信息缺口与需人工确认项。
- 不编造客户意图、预算、决策链。
- 输出保存建议：`/data/hermes/workspace/reports/sale/discovery/` 或 `/data/hermes/workspace/drafts/sale/`。
- 审核后可沉淀的发现框架、行业问题库写入 `/data/hermes/obsidian-vault/60-Reports/Sales`。

# 异常处理

- 关键条件缺失时先追问，不臆造。
- 外部数据不可用时明确说明限制。

# 禁止事项

- 不写入生产系统。
- 不泄露密钥、凭证或未授权数据。
- 不编造未标注的事实与来源。

# 引用资料

- 无额外引用（详见专家 SOUL 与工作区约定）
