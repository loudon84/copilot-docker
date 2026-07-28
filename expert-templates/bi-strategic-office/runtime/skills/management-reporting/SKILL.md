---
schema_version: workcopilot.skill.v1
id: management-reporting
name: 管理层财务分析报告编排与导出
version: 1.0.0
description: 管理层财务分析报告编排与导出。
triggers:
- 管理层财务分析报告编排与导出。
scope:
  includes:
  - 管理层财务分析报告编排与导出。
  excludes:
  - 写入生产系统
  - 泄露密钥
  - 执行非只读 SQL
  - 修改 ERP
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

管理层财务分析报告编排与导出。

# 适用条件

当用户请求与「管理层财务分析报告编排与导出」相关的任务时使用本技能。

# 前置检查

- 确认任务目标与输入材料是否齐全。
- 确认外部连接器可用（如已声明）。
- 确认不需要写入外部生产系统。

# 执行流程

1. 澄清目标、范围与约束。
2. 按工具调用规则获取只读数据或进行编排。
3. 按输出要求交付，并标注不确定项。

# 工具调用规则

- 仅使用专家权限允许的工具：无强制工具。
- 默认只读；不得越权调用。
- 连接器不可用时停止猜测并说明限制。

# 输出要求

- 按专家 SOUL 与权限策略执行

# 异常处理

- 关键条件缺失时先追问，不臆造。
- 连接器或数据源不可用时明确说明并给出可重试建议。

# 禁止事项

- 不写入生产系统 / ERP。
- 不泄露密钥、凭证、Token、chat_id。
- 不执行非只读 SQL，不绕过 Adapter 安全护栏。

# 引用资料

- 详见专家 SOUL、GUIDE 与工作区约定
