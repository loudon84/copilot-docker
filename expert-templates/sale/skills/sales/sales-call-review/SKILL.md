---
schema_version: workcopilot.skill.v1
id: sales-call-review
name: 复盘电话记录、会议纪要、销售聊天记录，提供销售辅导与 CRM 更新建议。聚焦 1
version: 1.0.0
description: 复盘电话记录、会议纪要、销售聊天记录，提供销售辅导与 CRM 更新建议。聚焦 1–3 个改进点。
triggers:
- 复盘电话记录、会议纪要、销售聊天记录，提供销售辅导与 CRM 更新建议。聚焦 1
scope:
  includes:
  - 复盘电话记录、会议纪要、销售聊天记录，提供销售辅导与 CRM 更新建议。聚焦 1–3 个改进点。
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

复盘电话记录、会议纪要、销售聊天记录，提供销售辅导与 CRM 更新建议。聚焦 1–3 个改进点。

# 适用条件

当用户请求与「复盘电话记录、会议纪要、销售聊天记录，提供销售辅导与 CRM 更新建议。聚焦 1」相关的任务时使用本技能。

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

- 基于具体语句和行为反馈，不做人身评价。
- 每次只聚焦 1–3 个最高价值改进点。
- 输出可执行的练习动作，而非空泛批评。
- 不编造通话中未出现的内容。
- 输出保存：`/data/hermes/workspace/reports/sale/coaching/`。
- 可复用的 coaching 模式、常见失误模式写入 Hindsight。

# 异常处理

- 关键条件缺失时先追问，不臆造。
- 外部数据不可用时明确说明限制。

# 禁止事项

- 不写入生产系统。
- 不泄露密钥、凭证或未授权数据。
- 不编造未标注的事实与来源。

# 引用资料

- 无额外引用（详见专家 SOUL 与工作区约定）
