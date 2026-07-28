---
schema_version: workcopilot.skill.v1
id: sales-outbound-sequence
name: 开发客户、写销售邮件、外呼脚本、多触点 sequence、针对某客户的触达计划。
version: 1.0.0
description: 开发客户、写销售邮件、外呼脚本、多触点 sequence、针对某客户的触达计划。邮件为草稿，不直接发送。
triggers:
- 开发客户、写销售邮件、外呼脚本、多触点 sequence、针对某客户的触达计划。
scope:
  includes:
  - 开发客户、写销售邮件、外呼脚本、多触点 sequence、针对某客户的触达计划。邮件为草稿，不直接发送。
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

开发客户、写销售邮件、外呼脚本、多触点 sequence、针对某客户的触达计划。邮件为草稿，不直接发送。

# 适用条件

当用户请求与「开发客户、写销售邮件、外呼脚本、多触点 sequence、针对某客户的触达计划。」相关的任务时使用本技能。

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

- 不生成垃圾群发文案；必须有具体触达理由。
- 所有 customer-facing 内容标记为草稿，不直接发送。
- 尊重退订和拒绝；不承诺价格、库存、交期。
- 不编造客户案例或合作关系。
- 输出保存：`/data/hermes/workspace/drafts/sale/outbound/`。
- 可复用的 sequence 模板、行业开场话术（审核后）写入 Obsidian。

# 异常处理

- 关键条件缺失时先追问，不臆造。
- 外部数据不可用时明确说明限制。

# 禁止事项

- 不写入生产系统。
- 不泄露密钥、凭证或未授权数据。
- 不编造未标注的事实与来源。

# 引用资料

- 无额外引用（详见专家 SOUL 与工作区约定）
