---
schema_version: workcopilot.skill.v1
id: sales-deal-assessment
name: 判断商机、评估客户、复盘机会、MEDDPICC 评估、看这个单能不能成。输出评分
version: 1.0.0
description: 判断商机、评估客户、复盘机会、MEDDPICC 评估、看这个单能不能成。输出评分、风险与下一步动作。
triggers:
- 判断商机、评估客户、复盘机会、MEDDPICC 评估、看这个单能不能成。输出评分
scope:
  includes:
  - 判断商机、评估客户、复盘机会、MEDDPICC 评估、看这个单能不能成。输出评分、风险与下一步动作。
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

判断商机、评估客户、复盘机会、MEDDPICC 评估、看这个单能不能成。输出评分、风险与下一步动作。

# 适用条件

当用户请求与「判断商机、评估客户、复盘机会、MEDDPICC 评估、看这个单能不能成。输出评分」相关的任务时使用本技能。

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

- 不把“可能下单”“感觉不错”当成强机会。
- 单线程客户（仅一个联系人）必须标为高风险。
- Economic Buyer 或 Decision Process 缺失时不得建议 Advance。
- 不编造客户预算、采购意图、竞品报价。
- 输出保存：`/data/hermes/workspace/reports/sale/deals/`。
- 可复用的成交/失败模式写入 Hindsight；审核后 battlecard 写入 Obsidian。

# 异常处理

- 关键条件缺失时先追问，不臆造。
- 外部数据不可用时明确说明限制。

# 禁止事项

- 不写入生产系统。
- 不泄露密钥、凭证或未授权数据。
- 不编造未标注的事实与来源。

# 引用资料

- 无额外引用（详见专家 SOUL 与工作区约定）
