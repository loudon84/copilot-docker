---
schema_version: workcopilot.skill.v1
id: sales-account-plan
name: 客户经营计划、QBR、客户复盘、续费扩展、客户地图、stakeholder ma
version: 1.0.0
description: 客户经营计划、QBR、客户复盘、续费扩展、客户地图、stakeholder mapping、Mutual Action Plan。
triggers:
- 客户经营计划、QBR、客户复盘、续费扩展、客户地图、stakeholder ma
scope:
  includes:
  - 客户经营计划、QBR、客户复盘、续费扩展、客户地图、stakeholder mapping、Mutual Action Plan。
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

客户经营计划、QBR、客户复盘、续费扩展、客户地图、stakeholder mapping、Mutual Action Plan。

# 适用条件

当用户请求与「客户经营计划、QBR、客户复盘、续费扩展、客户地图、stakeholder ma」相关的任务时使用本技能。

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

- 红色健康客户不得直接跑扩展动作；优先 stabilize / save plan。
- 单线程客户必须标为高风险。
- 所有扩展建议从客户价值角度表达，不强行推销。
- 不编造年采购额、合作历史、客户满意度。
- 输出保存：`/data/hermes/workspace/reports/sale/account-plan/`。
- 审核后的 account playbook 写入 `/data/hermes/obsidian-vault/60-Reports/Sales/Account/`。

# 异常处理

- 关键条件缺失时先追问，不臆造。
- 外部数据不可用时明确说明限制。

# 禁止事项

- 不写入生产系统。
- 不泄露密钥、凭证或未授权数据。
- 不编造未标注的事实与来源。

# 引用资料

- 无额外引用（详见专家 SOUL 与工作区约定）
