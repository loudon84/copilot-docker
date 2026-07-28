---
schema_version: workcopilot.skill.v1
id: example-skill
name: 独立技能模板
version: 1.0.0
description: 可复用的独立 Skill 脚手架。
triggers:
  - 示例
scope:
  includes:
    - 示例任务
  excludes:
    - 写入生产系统
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

完成独立技能任务。

# 适用条件

用户提出相关请求。

# 前置检查

确认输入齐全。

# 执行流程

1. 澄清目标
2. 产出结果

# 工具调用规则

仅使用允许的工具。

# 输出要求

使用简体中文。

# 异常处理

缺少条件时追问。

# 禁止事项

不写入生产系统。

# 引用资料

- 无
