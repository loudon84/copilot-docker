---
name: data-quality-review
description: 查询结果数据质量与口径一致性检查。
version: 1.0.0
metadata:
  hermes:
    tags: [bi, quality]
    category: finance-bi
---

# data-quality-review

正式输出前调用 finance_bi_validate_result，检查主体、时间、币种、聚合粒度与警告。
