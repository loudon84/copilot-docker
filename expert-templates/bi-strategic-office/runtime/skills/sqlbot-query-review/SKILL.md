---
name: sqlbot-query-review
description: 复核 SQLBot 生成的 SQL、筛选条件与结果范围，发现偏差时停止分析。
version: 1.0.0
metadata:
  hermes:
    tags: [bi, sqlbot, review]
    category: finance-bi
---

# sqlbot-query-review

## 职责

在经营分析或正式报告前，复核最近一次 `finance_bi_*` 返回：

1. SQL 是否只读（SELECT / WITH）。
2. 用户明确编号/过滤是否出现在 SQL 与结果中。
3. 时间范围、主体、客户是否符合问题意图。
4. 结果是否混入无关凭证或全局前 N 行。
5. `warnings` 与截断信息是否已向用户说明。

## 动作

- 需要 SQL/口径细节时调用 `finance_bi_explain`（不重新查库）。
- 发现问题：停止分析，原样引用工具 `error.code` / `warnings`，请用户澄清或改问。
- 不得绕过 Adapter 安全错误再次取数。
- 不得修改 `rows` 中的原始数字。
