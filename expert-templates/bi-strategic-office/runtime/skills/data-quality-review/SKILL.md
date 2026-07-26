---
name: data-quality-review
description: 查询结果数据质量与口径一致性检查。
version: 1.1.0
metadata:
  hermes:
    tags: [bi, quality]
    category: finance-bi
---

# data-quality-review

正式输出前复核主体、时间、币种、聚合粒度与 `warnings`。

优先结合 `sqlbot-query-review` 与 `finance_bi_explain`。若 Adapter 返回安全错误或截断警告，必须在结论中显式说明。
