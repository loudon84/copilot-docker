---
schema_version: workcopilot.skill.v1
id: finance-bi-query
name: 自然语言财务经营问数、筛选与下钻（经 SQLBot Adapter）
version: 2.0.0
description: 自然语言财务经营问数、筛选与下钻（经 SQLBot Adapter）。
triggers:
- 自然语言财务经营问数、筛选与下钻（经 SQLBot Adapter）。
scope:
  includes:
  - 自然语言财务经营问数、筛选与下钻（经 SQLBot Adapter）。
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
tool_requirements:
- finance_bi_ask
- finance_bi_followup
- finance_bi_explain
- finance_bi_reset
- finance_bi_connection_test
connector_requirements:
- finance-query
permissions:
  access_mode: read-only
  data_classification: confidential
---

# 技能目标

自然语言财务经营问数、筛选与下钻（经 SQLBot Adapter）。

# 适用条件

当用户请求与「自然语言财务经营问数、筛选与下钻（经 SQLBot Adapter）」相关的任务时使用本技能。

# 前置检查

- 确认任务目标与输入材料是否齐全。
- 确认外部连接器可用（如已声明）。
- 确认不需要写入外部生产系统。

# 执行流程

1. 澄清目标、范围与约束。
2. 按工具调用规则获取只读数据或进行编排。
3. 按输出要求交付，并标注不确定项。

# 工具调用规则

- 仅使用专家权限允许的工具：finance_bi_ask, finance_bi_followup, finance_bi_explain, finance_bi_reset, finance_bi_connection_test。
- 默认只读；不得越权调用。
- 连接器不可用时停止猜测并说明限制。

# 输出要求

- `success`
- `query_id`
- `columns` / `rows` / `query.row_count`
- `query.sql`（只读 SQL，供复核）
- `warnings` / `meta`
- 必填：`question`
- 可选：`datasource_key`（配置别名，不要传 SQLBot 内部 datasource_id）
- 可选：`response_mode`：`data_only` | `data_and_summary` | `chart`
- 必填：`instruction`
- Adapter 内部复用当前会话的 SQLBot 对话
- 若返回 `QUERY_CONTEXT_NOT_FOUND`，先 `finance_bi_ask`
- 明确时间、主体、币种与口径。

# 异常处理

- 关键条件缺失时先追问，不臆造。
- 连接器或数据源不可用时明确说明并给出可重试建议。

# 禁止事项

- 不写入生产系统 / ERP。
- 不泄露密钥、凭证、Token、chat_id。
- 不执行非只读 SQL，不绕过 Adapter 安全护栏。

# 引用资料

- 详见专家 SOUL、GUIDE 与工作区约定
