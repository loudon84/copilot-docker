---
name: finance-performance-analysis
description: 产品/客户/区域利润与同比环比差异分析。
version: 1.1.0
metadata:
  hermes:
    tags: [bi, performance]
    category: finance-bi
---

# finance-performance-analysis

基于 finance-bi（SQLBot Adapter）查询结果做经营分析。

## 负责

- 同比环比
- 利润变化
- 客户贡献 / 产品贡献
- 异常归因
- 管理层摘要

## 不负责

- 查询数据库
- 生成或执行 SQL
- 修改工具返回的原始数字

区分数据事实、计算结果、业务推断、待确认事项。
