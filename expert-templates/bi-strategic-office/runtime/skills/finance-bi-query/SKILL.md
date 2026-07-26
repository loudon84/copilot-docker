---
name: finance-bi-query
description: 自然语言财务经营问数、筛选与下钻（经 SQLBot Adapter）。
version: 2.0.0
metadata:
  hermes:
    tags: [bi, query, sqlbot]
    category: finance-bi
---

# finance-bi-query

## 返回契约（强制）

`finance_bi_ask` / `finance_bi_followup` 返回标准化结构：

- `success`
- `query_id`
- `columns` / `rows` / `query.row_count`
- `query.sql`（只读 SQL，供复核）
- `warnings` / `meta`

**工具只交付表格数据集，不负责最终呈现。**  
不得改写工具返回的数字。不得把 SQLBot 密码、Token、`chat_id` 输出给用户。

## 工具选择

1. **新问题 / 换主题** → `finance_bi_ask`
   - 必填：`question`
   - 可选：`datasource_key`（配置别名，不要传 SQLBot 内部 datasource_id）
   - 可选：`response_mode`：`data_only` | `data_and_summary` | `chart`

2. **同一话题追问 / 下钻** → `finance_bi_followup`
   - 必填：`instruction`
   - Adapter 内部复用当前会话的 SQLBot 对话
   - 若返回 `QUERY_CONTEXT_NOT_FOUND`，先 `finance_bi_ask`

3. **解释最近一次查询（不重新取数）** → `finance_bi_explain`

4. **清除多轮上下文** → `finance_bi_reset`

## 问数要点

- 明确时间、主体、币种与口径。
- 含明确编号（凭证号/单据号/客户编号）时，必须写进 question/instruction。
- Adapter 若返回 `FILTER_NOT_PRESERVED` / `UNSAFE_SQL` / `DETAIL_QUERY_REQUIRES_FILTER`，停止分析并原样告知用户，不得绕过。
- 明细查询必须带有效过滤：精确编号、日期范围、客户或主体。
- **禁止** terminal / 手工 SQL / 直连数据库。

## 与分析 Skill 的分工

- 本 Skill：取数与工具选择。
- `sqlbot-query-review`：复核 SQL 与结果范围。
- `finance-performance-analysis`：基于 `rows` 做经营分析（不负责查库）。
