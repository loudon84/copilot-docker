---
schema_version: workcopilot.skill.v1
id: sales-pipeline-health
name: 分析 pipeline 表、CRM 导出、销售漏斗、预测与主管复盘。识别 sta
version: 1.0.0
description: 分析 pipeline 表、CRM 导出、销售漏斗、预测与主管复盘。识别 stalled、underqualified、single-threaded
  商机。
triggers:
- 分析 pipeline 表、CRM 导出、销售漏斗、预测与主管复盘。识别 sta
scope:
  includes:
  - 分析 pipeline 表、CRM 导出、销售漏斗、预测与主管复盘。识别 stalled、underqualified、single-threaded 商机。
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

分析 pipeline 表、CRM 导出、销售漏斗、预测与主管复盘。识别 stalled、underqualified、single-threaded 商机。

# 适用条件

当用户请求与「分析 pipeline 表、CRM 导出、销售漏斗、预测与主管复盘。识别 sta」相关的任务时使用本技能。

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

- 数据不足必须明确标记，不强行预测。
- 不输出单一预测值；必须给区间或分类。
- 不接受「感觉很好」的商机判断。
- 过期未更新商机标红。
- 原始 pipeline 文件应在 `/data/hermes/workspace/materials/sale/`。
- 分析报告保存：`/data/hermes/workspace/reports/sale/pipeline/`。
- 可复用的 pipeline review 口径写入 Hindsight。

# 异常处理

- 关键条件缺失时先追问，不臆造。
- 外部数据不可用时明确说明限制。

# 禁止事项

- 不写入生产系统。
- 不泄露密钥、凭证或未授权数据。
- 不编造未标注的事实与来源。

# 引用资料

- 无额外引用（详见专家 SOUL 与工作区约定）
