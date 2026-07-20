---
name: finance-bi-query
description: 自然语言财务经营问数、筛选与下钻。
version: 1.0.0
metadata:
  hermes:
    tags: [bi, query]
    category: finance-bi
---

# finance-bi-query

1. 用 finance_bi_catalog_search 确认可用指标/维度。
2. 用 finance_bi_ask 发起查询。
3. 后续筛选/下钻用 finance_bi_followup（传入 base_query_id）。
4. 需要导出时用 finance_bi_export_result。
