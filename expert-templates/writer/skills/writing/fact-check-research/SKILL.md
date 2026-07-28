---
schema_version: workcopilot.skill.v1
id: fact-check-research
name: 对写作中涉及的事实、数据、政策、竞品、产品版本进行核查标注
version: 1.0.0
description: 对写作中涉及的事实、数据、政策、竞品、产品版本进行核查标注。
triggers:
- 对写作中涉及的事实、数据、政策、竞品、产品版本进行核查标注。
scope:
  includes:
  - 对写作中涉及的事实、数据、政策、竞品、产品版本进行核查标注。
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

对写作中涉及的事实、数据、政策、竞品、产品版本进行核查标注。

# 适用条件

当用户请求与「对写作中涉及的事实、数据、政策、竞品、产品版本进行核查标注」相关的任务时使用本技能。

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

- 不编造事实、数据、客户名称、来源。
- 不确定内容标注“需要确认”。
- 输出必须包含可沉淀到 Hindsight 的长期偏好或事实口径建议。
- 适合沉淀为知识资产的内容必须给出 Obsidian 保存路径建议。

# 异常处理

- 关键条件缺失时先追问，不臆造。
- 外部数据不可用时明确说明限制。

# 禁止事项

- 不写入生产系统。
- 不泄露密钥、凭证或未授权数据。
- 不编造未标注的事实与来源。

# 引用资料

- 无额外引用（详见专家 SOUL 与工作区约定）
