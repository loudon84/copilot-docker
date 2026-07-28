---
schema_version: workcopilot.skill.v1
id: ap-pressure-review
name: 分析应付压力、付款计划和短期资金缺口
version: 1.0.0
description: 分析应付压力、付款计划和短期资金缺口。
triggers:
- 分析应付压力、付款计划和短期资金缺口。
scope:
  includes:
  - 分析应付压力、付款计划和短期资金缺口。
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

分析应付压力、付款计划和短期资金缺口。

# 适用条件

当用户请求与「分析应付压力、付款计划和短期资金缺口」相关的任务时使用本技能。

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

- 区分事实、假设、预测、判断。
- 实时数据以 ERP/CRM/银行/MCP 工具为准。
- 不执行付款、不改账、不审批、不输出最终税务/审计/法律结论。
- 适合沉淀的制度口径、报告模板、历史案例写入 Obsidian。
- 长期有效的分析口径、风险偏好、复盘结论写入 Hindsight。

# 异常处理

- 关键条件缺失时先追问，不臆造。
- 外部数据不可用时明确说明限制。

# 禁止事项

- 不写入生产系统。
- 不泄露密钥、凭证或未授权数据。
- 不编造未标注的事实与来源。

# 引用资料

- 无额外引用（详见专家 SOUL 与工作区约定）
