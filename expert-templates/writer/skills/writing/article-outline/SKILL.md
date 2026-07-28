---
schema_version: workcopilot.skill.v1
id: article-outline
name: 生成文章大纲、标题方向、核心观点和内容风险点
version: 1.0.0
description: 生成文章大纲、标题方向、核心观点和内容风险点。
triggers:
- 生成文章大纲、标题方向、核心观点和内容风险点。
scope:
  includes:
  - 生成文章大纲、标题方向、核心观点和内容风险点。
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

生成文章大纲、标题方向、核心观点和内容风险点。

# 适用条件

当用户请求与「生成文章大纲、标题方向、核心观点和内容风险点」相关的任务时使用本技能。

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
