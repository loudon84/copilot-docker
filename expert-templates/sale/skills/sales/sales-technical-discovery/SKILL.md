---
schema_version: workcopilot.skill.v1
id: sales-technical-discovery
name: 售前技术问题、产品规格确认、Demo 计划、POC 范围、技术异议处理。替代料需
version: 1.0.0
description: 售前技术问题、产品规格确认、Demo 计划、POC 范围、技术异议处理。替代料需 FAE/工程确认。
triggers:
- 售前技术问题、产品规格确认、Demo 计划、POC 范围、技术异议处理。替代料需
scope:
  includes:
  - 售前技术问题、产品规格确认、Demo 计划、POC 范围、技术异议处理。替代料需 FAE/工程确认。
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

售前技术问题、产品规格确认、Demo 计划、POC 范围、技术异议处理。替代料需 FAE/工程确认。

# 适用条件

当用户请求与「售前技术问题、产品规格确认、Demo 计划、POC 范围、技术异议处理。替代料需」相关的任务时使用本技能。

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

- 技术回答必须可追溯到规格书、产品资料或已知事实。
- 替代料建议必须标记为「需 FAE/工程确认」，不直接确认等价性。
- POC 必须有明确的 pass/fail criteria。
- 不做未验证的技术承诺；不编造认证、参数、兼容性。
- 参数不全时先输出澄清清单，不直接推荐具体型号。
- 输出保存：`/data/hermes/workspace/reports/sale/technical/` 或 `/data/hermes/workspace/drafts/sale/`。
- 审核后的技术 battlecard 写入 Obsidian `80-Product-Spec` 或 `60-Reports/Sales`。

# 异常处理

- 关键条件缺失时先追问，不臆造。
- 外部数据不可用时明确说明限制。

# 禁止事项

- 不写入生产系统。
- 不泄露密钥、凭证或未授权数据。
- 不编造未标注的事实与来源。

# 引用资料

- 无额外引用（详见专家 SOUL 与工作区约定）
